# Tooltip: If you have x2 collections of objects with the same names, this will copy the materials and face assignments from the objects in the first collection to the objects in the second collection. Supports stripping namespaces, custom prefixes, and custom suffixes before name matching.
import bpy

class CopyMaterialsOperator(bpy.types.Operator):
    """Copy Materials from Source to Target Collection"""
    bl_idname = "object.copy_materials"
    bl_label = "Copy Materials Between Collections"
    bl_options = {'REGISTER', 'UNDO'}

    # These functions are used to update the drop-down list of collections
    def get_collections(self, context):
        items = [(coll.name, coll.name, "") for coll in bpy.data.collections]
        return items

    source_collection: bpy.props.EnumProperty(
        name="Source Collection",
        description="Collection to copy materials from",
        items=get_collections
    )

    target_collection: bpy.props.EnumProperty(
        name="Target Collection",
        description="Collection to copy materials to",
        items=get_collections
    )

    strip_prefix: bpy.props.StringProperty(
        name="Strip Prefix",
        description="Optional prefix to ignore when matching names (e.g. 'CHR_'). Applied to both collections.",
        default=""
    )

    strip_suffix: bpy.props.StringProperty(
        name="Strip Suffix",
        description="Optional suffix to ignore when matching names (e.g. '_LO'). Applied to both collections.",
        default=""
    )

    def execute(self, context):
        source_collection = bpy.data.collections.get(self.source_collection)
        target_collection = bpy.data.collections.get(self.target_collection)

        if not source_collection or not target_collection:
            self.report({'ERROR'}, f"Either {self.source_collection} or {self.target_collection} is not found!")
            return {'CANCELLED'}

        copy_materials_from_source_to_target(
            source_collection, target_collection,
            strip_prefix=self.strip_prefix,
            strip_suffix=self.strip_suffix
        )
        self.report({'INFO'}, f"Materials copied from {self.source_collection} to {self.target_collection}.")
        return {'FINISHED'}

    def invoke(self, context, event):
        return context.window_manager.invoke_props_dialog(self)


def get_base_name(name, strip_prefix="", strip_suffix=""):
    """
    Strips (in order):
      1. Namespace prefix  - everything up to and including ':' (automatic)
      2. User prefix       - e.g. 'CHR_'
      3. User suffix       - e.g. '_LO'
      4. Numeric suffix    - e.g. '.001'

    Examples (prefix='CHR_', suffix='_LO'):
      'NS:CHR_Body_LO.001' -> 'Body'
      'CHR_Body_LO'        -> 'Body'
      'Body.001'           -> 'Body'
      'Body'               -> 'Body'
    """
    # 1. Strip namespace prefix (everything up to and including ':')
    if ":" in name:
        name = name.split(":", 1)[1]
    # 2. Strip user-supplied prefix
    if strip_prefix and name.startswith(strip_prefix):
        name = name[len(strip_prefix):]
    # 3. Strip user-supplied suffix (before numeric suffix so order is predictable)
    if strip_suffix and name.endswith(strip_suffix):
        name = name[:-len(strip_suffix)]
    # 4. Strip numeric Blender duplicate suffix (.001, .002, etc.)
    if "." in name and name.split(".")[-1].isdigit():
        name = ".".join(name.split(".")[:-1])
    return name


def copy_materials_from_source_to_target(source_collection, target_collection, strip_prefix="", strip_suffix=""):
    """
    Copies material slots AND per-face material assignments from objects in the
    source collection to matching objects in the target collection.

    Name matching strips (automatically) namespace prefixes and Blender numeric
    suffixes, plus any user-supplied strip_prefix / strip_suffix strings.
    """
    unmatched_objects = []

    for source_obj in source_collection.objects:
        if source_obj.type != 'MESH':
            continue

        base_name = get_base_name(source_obj.name, strip_prefix, strip_suffix)
        found_match = False

        for target_obj in target_collection.objects:
            if target_obj.type != 'MESH':
                continue
            if get_base_name(target_obj.name, strip_prefix, strip_suffix) != base_name:
                continue

            source_mesh = source_obj.data
            target_mesh = target_obj.data

            # --- Sync material slots ---
            target_mesh.materials.clear()
            for mat in source_mesh.materials:
                target_mesh.materials.append(mat)

            # --- Sync per-face material assignments ---
            # Only needed when there are multiple material slots; with a single
            # slot every face is implicitly index 0 regardless of face count.
            if len(source_mesh.materials) > 1:
                src_polys = source_mesh.polygons
                tgt_polys = target_mesh.polygons
                src_count = len(src_polys)
                tgt_count = len(tgt_polys)

                if src_count != tgt_count:
                    print(
                        f"  WARNING: '{source_obj.name}' has {src_count} faces but "
                        f"'{target_obj.name}' has {tgt_count} faces. "
                        f"Copying face assignments up to the shorter count; "
                        f"any extra target faces keep their current index."
                    )

                copy_count = min(src_count, tgt_count)
                if copy_count > 0:
                    # Read source indices
                    src_indices = [0] * src_count
                    src_polys.foreach_get("material_index", src_indices)

                    # foreach_set requires an array exactly equal to the full
                    # polygon count of the target mesh - partial writes aren't
                    # supported. So we read the existing target indices first,
                    # overlay only the faces we're copying, then write it all back.
                    tgt_indices = [0] * tgt_count
                    tgt_polys.foreach_get("material_index", tgt_indices)
                    tgt_indices[:copy_count] = src_indices[:copy_count]
                    tgt_polys.foreach_set("material_index", tgt_indices)
                    target_mesh.update()

            # --- Sync UV layers ---
            # UV data is stored per-loop (one (u,v) pair per loop). We read the
            # full flat float array and write it to the matching layer on target,
            # creating the layer first if it doesn't exist yet.
            src_loop_count = len(source_mesh.loops)
            tgt_loop_count = len(target_mesh.loops)

            for src_uv_layer in source_mesh.uv_layers:
                uv_name = src_uv_layer.name

                if src_loop_count != tgt_loop_count:
                    print(
                        f"  WARNING: UV layer '{uv_name}' skipped for "
                        f"'{target_obj.name}' — loop count mismatch "
                        f"({src_loop_count} vs {tgt_loop_count}). "
                        f"Topology must match for UV copy."
                    )
                    continue

                # Create the layer on target if missing
                if uv_name not in target_mesh.uv_layers:
                    target_mesh.uv_layers.new(name=uv_name)

                uv_data = [0.0] * (src_loop_count * 2)
                src_uv_layer.data.foreach_get("uv", uv_data)
                target_mesh.uv_layers[uv_name].data.foreach_set("uv", uv_data)

            target_mesh.update()



            found_match = True
            break

        if not found_match:
            unmatched_objects.append(source_obj.name)

    if unmatched_objects:
        print("Objects in source collection without a match in target collection:")
        for obj_name in unmatched_objects:
            print(f" - {obj_name}")
    else:
        print("All objects from source collection found a match in target collection.")


def register():
    try:
        bpy.utils.register_class(CopyMaterialsOperator)
    except ValueError:
        # Already registered (e.g. script run twice in same session) - refresh it
        bpy.utils.unregister_class(CopyMaterialsOperator)
        bpy.utils.register_class(CopyMaterialsOperator)


def unregister():
    try:
        bpy.utils.unregister_class(CopyMaterialsOperator)
    except RuntimeError:
        pass


# Call the register function
register()

# Now you can safely call your operator
bpy.ops.object.copy_materials('INVOKE_DEFAULT')
