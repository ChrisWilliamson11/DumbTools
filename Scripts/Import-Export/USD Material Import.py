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
        
        layout.separator()
        box = layout.box()
        box.label(text="Detected Source Paths:")
        
        unique_paths = set()
        for obj in context.selected_objects:
            if "_dt_usd_materials" in obj:
                try:
                    data = json.loads(obj["_dt_usd_materials"])
                    for slot_data in data.values():
                        if slot_data.get("path"):
                            unique_paths.add(slot_data.get("path"))
                except Exception:
                    pass
        
        col = box.column(align=True)
        if unique_paths:
            for p in sorted(unique_paths):
                col.label(text=p, icon='FILE_BLEND')
        else:
            col.label(text="No paths found in current selection.", icon='INFO')

    def execute(self, context):
        restored_count = 0
        missing_files = set()
        
        appended_materials = {} 

        def get_or_append_material(mat_name, path):
            cache_key = (mat_name, path)
            if cache_key in appended_materials:
                return appended_materials[cache_key]

            # Before checking if it exists, remember that if we just import USD,
            # the USD Proxy material took the name 'mat_name'. We have freed the name
            # by renaming the proxy in the main loop below.
            
            existing_mat = bpy.data.materials.get(mat_name)
            # If it already exists and has been restored or manually created AFTER proxies were renamed
            if existing_mat:
                appended_materials[cache_key] = existing_mat
                return existing_mat

            if not path or not os.path.exists(path):
                if path:
                    missing_files.add(path)
                return None
                
            try:
                with bpy.data.libraries.load(path, link=False) as (data_from, data_to):
                    if mat_name in data_from.materials:
                        data_to.materials.append(mat_name)
                
                for m in data_to.materials:
                    if m is not None:
                        m["_dt_restored"] = True
                        appended_materials[cache_key] = m
                        return m
            except Exception as e:
                print(f"USD Import Restore: Failed to load material {mat_name} from {path}. Error: {e}")
                
            return None

        # Pre-process: Rename proxy materials, expand slot capacity, and remap polygon indices
        for obj in context.selected_objects:
            if "_dt_usd_materials" not in obj:
                continue
            
            try:
                mat_data = json.loads(obj["_dt_usd_materials"])
            except Exception:
                continue
                
            if getattr(obj, "data", None) and hasattr(obj.data, "materials"):
                # 1. Expand slot capacity to match the original object length
                # This prevents "out of bounds" errors when we fix polygon indices
                max_slot_idx = max([int(k) for k in mat_data.keys()]) if mat_data else -1
                while len(obj.material_slots) <= max_slot_idx:
                    obj.data.materials.append(None)
                    
                # 2. Build a mapping of (current USD slot index -> original physical slot index)
                poly_remap = {}
                for current_idx, slot in enumerate(obj.material_slots):
                    mat = slot.material
                    if not mat: continue
                    
                    # Prevent touching materials we've already restored
                    if mat.get("_dt_restored"): continue
                        
                    mat_name = mat.name
                    base_name = mat_name[:-9] if mat_name.endswith("_USDProxy") else mat_name
                    
                    original_idx = None
                    for slot_idx_str, data in mat_data.items():
                        if data.get("name") == base_name:
                            original_idx = int(slot_idx_str)
                            break
                            
                    if original_idx is not None:
                        # 3. Securely rename the dummy proxy so the appended material can take the real name
                        if mat.name == base_name and "_dt_restored" not in mat:
                            mat.name = base_name + "_USDProxy"
                        poly_remap[current_idx] = original_idx
                
                # 4. Correct the materials assigned to all physical polygons
                if poly_remap and hasattr(obj.data, "polygons") and len(obj.data.polygons) > 0:
                    poly_indices = [0] * len(obj.data.polygons)
                    obj.data.polygons.foreach_get("material_index", poly_indices)
                    
                    changed = False
                    for i in range(len(poly_indices)):
                        old_idx = poly_indices[i]
                        if old_idx in poly_remap and poly_remap[old_idx] != old_idx:
                            poly_indices[i] = poly_remap[old_idx]
                            changed = True
                            
                    if changed:
                        # extremely fast C-level array assignment
                        obj.data.polygons.foreach_set("material_index", poly_indices)
                        obj.data.update()

        for obj in context.selected_objects:
            if "_dt_usd_materials" not in obj:
                continue
                
            try:
                mat_data = json.loads(obj["_dt_usd_materials"])
            except Exception:
                continue
                
            for slot_idx_str, data in mat_data.items():
                slot_idx = int(slot_idx_str)
                mat_name = data.get("name")
                mat_path = data.get("path")
                link_param = data.get("link_param", 'OBJECT')
                
                if self.search_path and mat_path:
                    mat_path = mat_path.replace(self.search_path, self.replace_path)
                
                mat = get_or_append_material(mat_name, mat_path)
                
                if mat:
                    # Dynamically recreate any missing slots that were lost during USD translation
                    # (e.g. if the material was assigned to a slot but not to any actual faces)
                    if getattr(obj, "data", None) and hasattr(obj.data, "materials"):
                        while len(obj.material_slots) <= slot_idx:
                            obj.data.materials.append(None)
                    
                    if slot_idx < len(obj.material_slots):
                        obj.material_slots[slot_idx].material = mat
                        obj.material_slots[slot_idx].link = link_param
            
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
