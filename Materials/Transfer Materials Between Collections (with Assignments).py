# Tooltip: Copy materials (and face assignments) from matching objects in a source collection to a target collection, with optional name prefix/suffix stripping.
import bpy
from bpy.props import StringProperty, BoolProperty, EnumProperty


class TransferMaterialsBetweenCollections(bpy.types.Operator):
    """Transfer materials from matching objects in one collection to another.

    - Choose source and target collections
    - Match objects by name, after optionally stripping prefixes/suffixes and numeric .001 suffixes
    - Copy material slots; optionally copy per-face material assignments when topology matches
    """

    bl_idname = "object.transfer_materials_between_collections"
    bl_label = "Transfer Materials Between Collections"
    bl_options = {'REGISTER', 'UNDO'}

    # Dynamic collections list
    def get_collections(self, context):
        return [(coll.name, coll.name, "") for coll in bpy.data.collections]

    source_collection: EnumProperty(
        name="Source Collection",
        description="Collection to copy materials from",
        items=get_collections,
    )

    target_collection: EnumProperty(
        name="Target Collection",
        description="Collection to copy materials to",
        items=get_collections,
    )

    # Name normalization options
    source_prefix: StringProperty(name="Source Prefix", description="Strip this prefix from source object names before matching", default="")
    source_suffix: StringProperty(name="Source Suffix", description="Strip this suffix from source object names before matching", default="")
    target_prefix: StringProperty(name="Target Prefix", description="Strip this prefix from target object names before matching", default="")
    target_suffix: StringProperty(name="Target Suffix", description="Strip this suffix from target object names before matching", default="")

    ignore_numeric_suffix: BoolProperty(
        name="Ignore .001 Suffix",
        description="Ignore Blender's numeric .001/.002 style suffixes during matching",
        default=True,
    )
    case_sensitive: BoolProperty(
        name="Case Sensitive",
        description="Treat names as case-sensitive when matching",
        default=False,
    )

    copy_face_assignments: BoolProperty(
        name="Copy Face Assignments",
        description="Also copy per-face material indices when meshes have the same polygon count",
        default=True,
    )

    def draw(self, context):
        layout = self.layout
        layout.prop(self, "source_collection")
        layout.prop(self, "target_collection")

        box = layout.box()
        box.label(text="Name Matching")
        col = box.column(align=True)
        col.prop(self, "source_prefix")
        col.prop(self, "source_suffix")
        col.prop(self, "target_prefix")
        col.prop(self, "target_suffix")
        row = box.row(align=True)
        row.prop(self, "ignore_numeric_suffix")
        row.prop(self, "case_sensitive")

        layout.prop(self, "copy_face_assignments")

    def invoke(self, context, event):
        return context.window_manager.invoke_props_dialog(self)

    def execute(self, context):
        src_coll = bpy.data.collections.get(self.source_collection)
        dst_coll = bpy.data.collections.get(self.target_collection)

        if not src_coll or not dst_coll:
            self.report({'ERROR'}, "Please choose valid source and target collections")
            return {'CANCELLED'}

        # Build fast lookup for target objects by normalized name
        def normalize(name: str, strip_prefix: str, strip_suffix: str) -> str:
            base = name
            # Optionally strip Blender numeric suffix: .001, .002, etc
            if self.ignore_numeric_suffix and "." in base and base.split(".")[-1].isdigit():
                base = ".".join(base.split(".")[:-1])
            if strip_prefix and base.startswith(strip_prefix):
                base = base[len(strip_prefix):]
            if strip_suffix and base.endswith(strip_suffix):
                base = base[: len(base) - len(strip_suffix)]
            return base if self.case_sensitive else base.lower()

        target_map = {}
        for obj in dst_coll.objects:
            if not getattr(obj, "type", None) == 'MESH':
                continue
            key = normalize(obj.name, self.target_prefix, self.target_suffix)
            # Only keep first occurrence; warn on duplicates later
            target_map.setdefault(key, obj)

        unmatched_sources = []
        duplicates_on_target = set()
        transferred = 0
        skipped_non_mesh = 0
        mismatched_topology = 0

        # Detect duplicates for information (same normalized name maps to multiple objects)
        seen_keys = {}
        for obj in dst_coll.objects:
            if obj.type != 'MESH':
                continue
            k = normalize(obj.name, self.target_prefix, self.target_suffix)
            if k in seen_keys:
                duplicates_on_target.add(k)
            else:
                seen_keys[k] = obj

        for src_obj in src_coll.objects:
            if src_obj.type != 'MESH':
                skipped_non_mesh += 1
                continue

            match_key = normalize(src_obj.name, self.source_prefix, self.source_suffix)
            tgt_obj = target_map.get(match_key)

            if not tgt_obj:
                unmatched_sources.append(src_obj.name)
                continue

            # Copy material slots
            tgt_data = getattr(tgt_obj, "data", None)
            src_data = getattr(src_obj, "data", None)
            if not tgt_data or not src_data:
                continue

            # Clear existing materials on target
            if tgt_data.materials:
                tgt_data.materials.clear()

            for mat in src_data.materials:
                tgt_data.materials.append(mat)

            # Optionally copy face assignments when topology matches
            if self.copy_face_assignments:
                if hasattr(src_data, "polygons") and hasattr(tgt_data, "polygons") and len(src_data.polygons) == len(tgt_data.polygons):
                    for i, poly in enumerate(src_data.polygons):
                        tgt_data.polygons[i].material_index = poly.material_index
                else:
                    mismatched_topology += 1

            transferred += 1

        # Summarize in the info bar and console
        msg = f"Transferred materials for {transferred} object(s)."
        if skipped_non_mesh:
            msg += f" Skipped {skipped_non_mesh} non-mesh object(s)."
        if mismatched_topology and self.copy_face_assignments:
            msg += f" {mismatched_topology} object(s) had mismatched topology; assignments not copied."
        if duplicates_on_target:
            msg += f" Note: duplicate normalized names in target: {len(duplicates_on_target)}."
        self.report({'INFO'}, msg)

        if unmatched_sources:
            print("Objects in source collection without a match in target collection:")
            for name in unmatched_sources:
                print(f" - {name}")
        return {'FINISHED'}


def register():
    bpy.utils.register_class(TransferMaterialsBetweenCollections)


def unregister():
    bpy.utils.unregister_class(TransferMaterialsBetweenCollections)


# Register and open the dialog
try:
    unregister()
except Exception:
    pass
register()
bpy.ops.object.transfer_materials_between_collections('INVOKE_DEFAULT')

