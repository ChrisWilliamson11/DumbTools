# Tooltip: Select a .blend file with matching objects and this will import its materials and apply them to matching objects in the current file (by name, ignoring .001 suffixes).
import bpy
import os
from bpy.types import Operator
from bpy.props import StringProperty, BoolProperty
from bpy_extras.io_utils import ImportHelper


def normalize_name(name: str, ignore_numeric_suffix: bool = True, case_sensitive: bool = False) -> str:
    base = name or ""
    if ignore_numeric_suffix and "." in base and base.split(".")[-1].isdigit():
        base = ".".join(base.split(".")[:-1])
    return base if case_sensitive else base.lower()


def object_can_have_materials(obj: bpy.types.Object) -> bool:
    data = getattr(obj, "data", None)
    if data is None:
        return False
    return hasattr(data, "materials")


class OBJECT_OT_apply_materials_from_blend(Operator, ImportHelper):
    """Append materials from another .blend and apply them to matching objects here.

    - Prompts for a .blend file
    - Loads only the objects needed (not linked to scene) to read their material slots
    - Applies those materials to all local objects whose names match (ignoring .001, optionally case-insensitive)
    - Works around Blender's unique-number renaming by tracking the external names explicitly
    """

    bl_idname = "object.apply_materials_from_blend"
    bl_label = "Apply Materials From Another Blend"
    bl_options = {'REGISTER', 'UNDO'}

    filename_ext = ".blend"
    filter_glob: StringProperty(default="*.blend", options={'HIDDEN'})

    ignore_numeric_suffix: BoolProperty(
        name="Ignore .001 Suffix",
        description="Ignore Blender's numeric .001/.002 style suffixes when matching object names",
        default=True,
    )
    case_sensitive: BoolProperty(
        name="Case Sensitive",
        description="Case-sensitive name matching",
        default=False,
    )
    include_linked: BoolProperty(
        name="Affect Linked Objects",
        description="Attempt to apply to linked library objects (usually not allowed)",
        default=False,
    )
    cleanup_temp_objects: BoolProperty(
        name="Clean Up Temp Objects",
        description="Remove temporarily loaded external objects after applying materials",
        default=True,
    )

    def draw(self, context):
        layout = self.layout
        layout.prop(self, "filepath")
        row = layout.row(align=True)
        row.prop(self, "ignore_numeric_suffix")
        row.prop(self, "case_sensitive")
        layout.prop(self, "include_linked")
        layout.prop(self, "cleanup_temp_objects")

    def execute(self, context):
        filepath = self.filepath
        if not filepath or not os.path.exists(filepath) or not filepath.lower().endswith('.blend'):
            self.report({'ERROR'}, "Please select a valid .blend file")
            return {'CANCELLED'}

        # Build a lookup of local objects by normalized name
        local_map = {}
        eligible_local_objects = []
        for obj in bpy.data.objects:
            if not object_can_have_materials(obj):
                continue
            if obj.library and not self.include_linked:
                continue
            key = normalize_name(obj.name, self.ignore_numeric_suffix, self.case_sensitive)
            eligible_local_objects.append(obj)
            local_map.setdefault(key, []).append(obj)

        if not local_map:
            self.report({'WARNING'}, "No eligible local objects found to update")
            return {'CANCELLED'}

        # Discover external object names to load (only those that could match something locally)
        try:
            with bpy.data.libraries.load(filepath, link=False) as (data_from, data_to):
                external_object_names = list(data_from.objects) if data_from.objects else []
        except Exception as e:
            self.report({'ERROR'}, f"Failed to read objects from file: {e}")
            return {'CANCELLED'}

        if not external_object_names:
            self.report({'ERROR'}, "No objects found in the selected .blend file")
            return {'CANCELLED'}

        # Map normalized name -> list of external object names with that key
        ext_names_by_key = {}
        for ext_name in external_object_names:
            k = normalize_name(ext_name, self.ignore_numeric_suffix, self.case_sensitive)
            if k in local_map:
                ext_names_by_key.setdefault(k, []).append(ext_name)

        to_load_ext_names = []
        for key, _locals in local_map.items():
            names = ext_names_by_key.get(key)
            if names:
                # Prefer the first occurrence for that name key
                to_load_ext_names.append(names[0])

        if not to_load_ext_names:
            self.report({'WARNING'}, "No matching objects found in the external file")
            return {'CANCELLED'}

        # Load the matching external objects (not linked to the scene)
        loaded_objects = []
        try:
            before_ids = {o.as_pointer() for o in bpy.data.objects}
            with bpy.data.libraries.load(filepath, link=False) as (data_from, data_to):
                data_to.objects = to_load_ext_names
            # Determine which objects were newly loaded by comparing pointers
            loaded_objects = [o for o in bpy.data.objects if o.as_pointer() not in before_ids]
        except Exception as e:
            self.report({'ERROR'}, f"Failed to load objects from file: {e}")
            return {'CANCELLED'}

        if not loaded_objects:
            self.report({'ERROR'}, "Failed to load any matching external objects")
            return {'CANCELLED'}

        # Build mapping from normalized name to the loaded external object's materials
        ext_materials_by_key = {}
        for ext_obj in loaded_objects:
            if not object_can_have_materials(ext_obj):
                continue
            mats = []
            for slot in getattr(ext_obj, "material_slots", []) or []:
                mat = getattr(slot, "material", None)
                if mat is not None:
                    mats.append(mat)
            key = normalize_name(ext_obj.name, self.ignore_numeric_suffix, self.case_sensitive)
            if mats:
                ext_materials_by_key[key] = mats

        if not ext_materials_by_key:
            self.report({'WARNING'}, "No materials found on matching external objects")
            # Continue to cleanup and exit
            if self.cleanup_temp_objects:
                for o in loaded_objects:
                    try:
                        bpy.data.objects.remove(o, do_unlink=True)
                    except Exception:
                        pass
            return {'CANCELLED'}

        # Apply to all local objects that match
        updated = 0
        skipped_linked = 0
        missing_ext = 0

        for key, local_objs in local_map.items():
            mats = ext_materials_by_key.get(key)
            if not mats:
                missing_ext += len(local_objs)
                continue
            for obj in local_objs:
                if obj.library and not self.include_linked:
                    skipped_linked += 1
                    continue
                data = getattr(obj, "data", None)
                if not data or not hasattr(data, "materials"):
                    continue
                # Replace material slots
                try:
                    if data.materials:
                        data.materials.clear()
                    for m in mats:
                        data.materials.append(m)
                    updated += 1
                except Exception:
                    # print(f"Failed to apply materials to {obj.name}: {e}")
                    pass

        # Clean up temporary objects we loaded
        if self.cleanup_temp_objects:
            for o in loaded_objects:
                try:
                    bpy.data.objects.remove(o, do_unlink=True)
                except Exception:
                    pass
            # Optional: leave orphans purge to the user; can be destructive if run automatically
            # try:
            #     bpy.ops.outliner.orphans_purge(do_recursive=True)
            # except Exception:
            #     pass

        info = f"Applied materials to {updated} object(s)."
        if skipped_linked:
            info += f" Skipped {skipped_linked} linked object(s)."
        if missing_ext:
            info += f" No external match for {missing_ext} object(s)."
        self.report({'INFO'}, info)

        # print(f"External mapping keys: {len(ext_materials_by_key)} | Updated: {updated}")
        return {'FINISHED'}


def register():
    try:
        bpy.utils.register_class(OBJECT_OT_apply_materials_from_blend)
    except Exception:
        pass


def unregister():
    try:
        bpy.utils.unregister_class(OBJECT_OT_apply_materials_from_blend)
    except Exception:
        pass


# Register and open the file browser
try:
    unregister()
except Exception:
    pass
register()
bpy.ops.object.apply_materials_from_blend('INVOKE_DEFAULT')

