# Tooltip: If you have x2 collections of objects with the same names (ignoring suffixes .001, .002 etc), this will copy the materials from the objects in the first collection to the objects in the second collection.
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

    def execute(self, context):
        source_collection = bpy.data.collections.get(self.source_collection)
        target_collection = bpy.data.collections.get(self.target_collection)

        if not source_collection or not target_collection:
            self.report({'ERROR'}, f"Either {self.source_collection} or {self.target_collection} is not found!")
            return {'CANCELLED'}

        copy_materials_from_source_to_target(source_collection, target_collection)
        self.report({'INFO'}, f"Materials copied from {self.source_collection} to {self.target_collection}.")
        return {'FINISHED'}

    def invoke(self, context, event):
        return context.window_manager.invoke_props_dialog(self)


def get_base_name(name):
    """
    Strips namespace prefixes (e.g. 'NS:Body') and numeric suffixes (e.g. '.001')
    to get a bare base name for comparison.
    'NS:Body.001' -> 'Body', 'Cube.001' -> 'Cube', 'Body' -> 'Body'
    """
    # Strip namespace prefix (everything up to and including ':')
    if ":" in name:
        name = name.split(":", 1)[1]
    # Strip numeric suffix (.001, .002, etc.)
    if "." in name and name.split(".")[-1].isdigit():
        name = ".".join(name.split(".")[:-1])
    return name


def copy_materials_from_source_to_target(source_collection, target_collection):
    """
    Copies material slots AND per-face material assignments from objects in the
    source collection to matching objects in the target collection (matched by
    base name, ignoring numeric suffixes like .001/.002).

    Handles sources that have had new materials added and re-assigned to faces
    after the duplicates were created.
    """
    unmatched_objects = []

    for source_obj in source_collection.objects:
        if source_obj.type != 'MESH':
            continue

        base_name = get_base_name(source_obj.name)
        found_match = False

        for target_obj in target_collection.objects:
            if target_obj.type != 'MESH':
                continue
            if get_base_name(target_obj.name) != base_name:
                continue

            source_mesh = source_obj.data
            target_mesh = target_obj.data

            # --- Sync material slots ---
            target_mesh.materials.clear()
            for mat in source_mesh.materials:
                target_mesh.materials.append(mat)

            # --- Sync per-face material assignments ---
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
                # foreach_get/foreach_set is the fastest bulk-attribute API in Blender
                indices = [0] * src_count
                src_polys.foreach_get("material_index", indices)
                tgt_polys.foreach_set("material_index", indices[:copy_count])
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
