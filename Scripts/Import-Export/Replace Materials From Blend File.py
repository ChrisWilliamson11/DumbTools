# Tooltip: For all selected objects, replaces their materials with matching ones appended from a chosen .blend file. Handles Blender's .001/.002 duplicate suffixes automatically.
import bpy
import os
import re
from bpy_extras.io_utils import ImportHelper


def strip_blender_suffix(name):
    """Remove Blender's automatic duplicate suffix (.001, .002, etc.) from a name."""
    return re.sub(r'\.\d{3}$', '', name)


class DUMBTOOLS_OT_replace_materials_from_blend(bpy.types.Operator, ImportHelper):
    """Open a .blend file and replace all materials on selected objects with matching ones from that file"""
    bl_idname = "dumbtools.replace_materials_from_blend"
    bl_label = "Replace Materials From .blend File"
    bl_options = {'REGISTER', 'UNDO'}

    filename_ext = ".blend"
    filter_glob: bpy.props.StringProperty(
        default="*.blend",
        options={'HIDDEN'},
        maxlen=255,
    )

    def execute(self, context):
        blend_path = self.filepath

        if not os.path.isfile(blend_path):
            self.report({'ERROR'}, f"File not found: {blend_path}")
            return {'CANCELLED'}

        selected_objects = [o for o in context.selected_objects if getattr(o, "data", None) and hasattr(o.data, "materials")]

        if not selected_objects:
            self.report({'WARNING'}, "No mesh/curve objects selected.")
            return {'CANCELLED'}

        # ------------------------------------------------------------------ #
        # 1. Collect every unique material currently in the selected objects' #
        #    slots, and build a mapping:  material -> base_name               #
        # ------------------------------------------------------------------ #
        unique_mats = {}  # mat datablock -> base_name
        for obj in selected_objects:
            for slot in obj.material_slots:
                mat = slot.material
                if mat is not None and mat not in unique_mats:
                    unique_mats[mat] = strip_blender_suffix(mat.name)

        if not unique_mats:
            self.report({'WARNING'}, "No materials found on selected objects.")
            return {'CANCELLED'}

        # ------------------------------------------------------------------ #
        # 2. Peek at the source file to find available material names         #
        # ------------------------------------------------------------------ #
        try:
            with bpy.data.libraries.load(blend_path, link=False) as (data_from, _):
                source_material_names = set(data_from.materials)
        except Exception as e:
            self.report({'ERROR'}, f"Could not read .blend file: {e}")
            return {'CANCELLED'}

        if not source_material_names:
            self.report({'WARNING'}, "No materials found in source file.")
            return {'CANCELLED'}

        # ------------------------------------------------------------------ #
        # 3. Determine which base names have a match in the source file        #
        # ------------------------------------------------------------------ #
        # Match priority:
        #   a. Exact current name (rare — means no suffix was added)
        #   b. base_name (the stripped version)
        base_to_source = {}  # base_name -> name_to_append_from_source
        for mat, base_name in unique_mats.items():
            if mat.name in source_material_names:
                base_to_source[base_name] = mat.name
            elif base_name in source_material_names:
                base_to_source[base_name] = base_name

        if not base_to_source:
            self.report({'WARNING'}, "None of the materials on the selected objects match any material in the source file.")
            return {'CANCELLED'}

        # ------------------------------------------------------------------ #
        # 4. Rename existing materials to free up the clean base names,        #
        #    so Blender won't add a suffix when we append                      #
        # ------------------------------------------------------------------ #
        old_mat_map = {}  # base_name -> old mat datablock (renamed to _REPLACE_OLD)
        for mat, base_name in unique_mats.items():
            if base_name not in base_to_source:
                continue  # no source match — leave untouched
            # Give the old material a temporary name so the base name is free
            temp_name = base_name + "_REPLACE_OLD"
            # Avoid collisions if this temp name already exists somehow
            if bpy.data.materials.get(temp_name):
                bpy.data.materials[temp_name].name = temp_name + "_CONFLICT"
            mat.name = temp_name
            old_mat_map[base_name] = mat

        # ------------------------------------------------------------------ #
        # 5. Append matching materials from the source file                   #
        # ------------------------------------------------------------------ #
        appended = {}  # base_name -> newly appended mat datablock
        names_to_append = list(base_to_source.values())

        try:
            with bpy.data.libraries.load(blend_path, link=False) as (data_from, data_to):
                data_to.materials = [n for n in names_to_append if n in data_from.materials]
        except Exception as e:
            # Roll back renames on failure
            for base_name, old_mat in old_mat_map.items():
                old_mat.name = base_name
            self.report({'ERROR'}, f"Failed to append materials: {e}")
            return {'CANCELLED'}

        # Map the freshly appended materials back to base names
        for mat in data_to.materials:
            if mat is None:
                continue
            # After appending with base name free, mat.name should equal the source name
            source_name = mat.name  # might be base_name or base_name.001 if still clashed
            # Find which base_name this corresponds to
            for base_name, src_name in base_to_source.items():
                if source_name == src_name or strip_blender_suffix(source_name) == src_name:
                    appended[base_name] = mat
                    # Ensure the appended mat has the clean base name
                    if mat.name != base_name:
                        mat.name = base_name
                    break

        # ------------------------------------------------------------------ #
        # 6. Remap old materials -> new, then remove the old ones             #
        # ------------------------------------------------------------------ #
        replaced_count = 0
        skipped = []

        for base_name, old_mat in old_mat_map.items():
            new_mat = appended.get(base_name)
            if new_mat is None:
                # Append failed for this one — restore old name
                old_mat.name = base_name
                skipped.append(base_name)
                continue

            # user_remap swaps every reference in the file from old -> new
            old_mat.user_remap(new_mat)
            bpy.data.materials.remove(old_mat)
            replaced_count += 1

        # ------------------------------------------------------------------ #
        # 7. Report                                                           #
        # ------------------------------------------------------------------ #
        msg_parts = [f"Replaced {replaced_count} material(s) from '{os.path.basename(blend_path)}'."]
        if skipped:
            msg_parts.append(f"Could not append: {', '.join(skipped)}.")
        self.report({'INFO'}, " ".join(msg_parts))

        return {'FINISHED'}


def register():
    try:
        bpy.utils.register_class(DUMBTOOLS_OT_replace_materials_from_blend)
    except Exception:
        pass


def unregister():
    try:
        bpy.utils.unregister_class(DUMBTOOLS_OT_replace_materials_from_blend)
    except Exception:
        pass


register()
bpy.ops.dumbtools.replace_materials_from_blend('INVOKE_DEFAULT')
