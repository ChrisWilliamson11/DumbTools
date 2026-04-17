# Tooltip: Reads USD material tags on imported objects and automatically appends and assigns the original Blender materials.
import bpy
import json
import os

class DUMBTOOLS_OT_usd_material_import(bpy.types.Operator):
    """Restores materials to imported USD objects using tagged custom properties"""
    bl_idname = "dumbtools.usd_material_import"
    bl_label = "USD Material Import Restore"
    bl_options = {'REGISTER', 'UNDO'}

    search_path: bpy.props.StringProperty(
        name="Search Path",
        description="Path segment to replace in the original material file paths (leave empty to skip)",
        default=""
    )
    
    replace_path: bpy.props.StringProperty(
        name="Replace Path",
        description="New path segment to insert",
        default=""
    )

    def draw(self, context):
        layout = self.layout
        layout.label(text="Remap Source File Paths:")
        layout.prop(self, "search_path", text="Find")
        layout.prop(self, "replace_path", text="Replace")

    def execute(self, context):
        restored_count = 0
        missing_files = set()
        
        # We need a small cache so we don't try to append the same material 50 times
        appended_materials = {} # key: (mat_name, path), value: bpy.types.Material

        def get_or_append_material(mat_name, path):
            # 1. Did we already append it during this script run?
            cache_key = (mat_name, path)
            if cache_key in appended_materials:
                return appended_materials[cache_key]

            # 2. Is it already in the file EXACTLY by name?
            # We assume if the name matches exactly, it's the right one.
            existing_mat = bpy.data.materials.get(mat_name)
            if existing_mat:
                appended_materials[cache_key] = existing_mat
                return existing_mat

            # 3. Need to append it from the source file
            if not path or not os.path.exists(path):
                if path:
                    missing_files.add(path)
                return None
                
            try:
                with bpy.data.libraries.load(path, link=False) as (data_from, data_to):
                    if mat_name in data_from.materials:
                        data_to.materials.append(mat_name)
                
                # Check what was actually appended
                for m in data_to.materials:
                    if m is not None:
                        appended_materials[cache_key] = m
                        return m
            except Exception as e:
                print(f"USD Import Restore: Failed to load material {mat_name} from {path}. Error: {e}")
                
            return None

        for obj in context.selected_objects:
            if "_dt_usd_materials" not in obj:
                continue
                
            try:
                mat_data = json.loads(obj["_dt_usd_materials"])
            except Exception:
                continue
                
            # Iterate through the stored slot mappings
            for slot_idx_str, data in mat_data.items():
                slot_idx = int(slot_idx_str)
                mat_name = data.get("name")
                mat_path = data.get("path")
                link_param = data.get("link_param", 'OBJECT')
                
                # Apply path remapping
                if self.search_path and mat_path:
                    mat_path = mat_path.replace(self.search_path, self.replace_path)
                
                # Resolve the material
                mat = get_or_append_material(mat_name, mat_path)
                
                if mat:
                    # Make sure the slot index exists
                    if slot_idx < len(obj.material_slots):
                        obj.material_slots[slot_idx].material = mat
                        obj.material_slots[slot_idx].link = link_param
            
            # Cleanup the tag
            del obj["_dt_usd_materials"]
            restored_count += 1
            
        if restored_count > 0:
            msg = f"Restored materials on {restored_count} object(s)."
            if missing_files:
                msg += f" WARNING: missing {len(missing_files)} source files!"
            self.report({'INFO'}, msg)
        else:
            self.report({'WARNING'}, "No tagged objects found in selection.")
            
        return {'FINISHED'}

    def invoke(self, context, event):
        return context.window_manager.invoke_props_dialog(self)


def register():
    try:
        bpy.utils.register_class(DUMBTOOLS_OT_usd_material_import)
    except Exception:
        pass


def unregister():
    try:
        bpy.utils.unregister_class(DUMBTOOLS_OT_usd_material_import)
    except Exception:
        pass


register()
bpy.ops.dumbtools.usd_material_import('INVOKE_DEFAULT')
