# Tooltip: Tags selected objects with their original material assignments and file paths for USD export.
import bpy
import json

class DUMBTOOLS_OT_usd_material_export(bpy.types.Operator):
    """Tags selected objects with material assignment metadata for USD export"""
    bl_idname = "dumbtools.usd_material_export"
    bl_label = "USD Material Export Tagging"
    bl_options = {'REGISTER', 'UNDO'}

    def execute(self, context):
        if not bpy.data.is_saved:
            self.report({'WARNING'}, "Current file is not saved. Local material paths will be empty. Please save your .blend file first!")

        tagged_count = 0
        
        for obj in context.selected_objects:
            if obj.type not in {'MESH', 'CURVE', 'SURFACE', 'META', 'FONT', 'GPENCIL'}:
                continue
                
            if not obj.material_slots:
                continue
                
            mat_data = {}
            for i, slot in enumerate(obj.material_slots):
                mat = slot.material
                if not mat:
                    mat_data[str(i)] = {
                        "name": None,
                        "path": "",
                        "link_param": getattr(slot, "link", 'OBJECT')
                    }
                    continue
                    
                path = ""
                if mat.library:
                    # It's a linked material
                    path = mat.library.filepath
                else:
                    # It's a local material
                    path = bpy.data.filepath
                    
                # Convert to absolute path so it resolves unambiguously later
                if path.startswith("//"):
                    path = bpy.path.abspath(path)
                    
                mat_data[str(i)] = {
                    "name": mat.name,
                    "path": path,
                    "link_param": slot.link # 'OBJECT' or 'DATA'
                }
            
            if mat_data:
                # Save as custom property
                obj["_dt_usd_materials"] = json.dumps(mat_data)
                tagged_count += 1
                
        self.report({'INFO'}, f"Tagged {tagged_count} objects with USD Material metadata.")
        
        # Invoke USD export dialog automatically with desired defaults.
        # We use try/except fallbacks here because Blender frequently changes the exact 
        # python argument names for the USD exporter between versions (e.g. blendshapes vs shapekeys).
        try:
            # Optimal defaults (including armatures and shapekeys)
            bpy.ops.wm.usd_export('INVOKE_DEFAULT',
                selected_objects_only=True,
                export_animation=True,
                export_armatures=False,
                export_shapekeys=False,
                export_custom_properties=True
            )
        except Exception as e:
            try:
                # Fallback 1: Blender version might not support disabling armatures/shapekeys via python
                bpy.ops.wm.usd_export('INVOKE_DEFAULT',
                    selected_objects_only=True,
                    export_animation=True,
                    export_custom_properties=True
                )
            except Exception as e2:
                # Fallback 2: Absolute safety fallback
                bpy.ops.wm.usd_export('INVOKE_DEFAULT')
                
        return {'FINISHED'}

    def invoke(self, context, event):
        return self.execute(context)


def register():
    try:
        bpy.utils.register_class(DUMBTOOLS_OT_usd_material_export)
    except Exception:
        pass


def unregister():
    try:
        bpy.utils.unregister_class(DUMBTOOLS_OT_usd_material_export)
    except Exception:
        pass


register()
bpy.ops.dumbtools.usd_material_export('INVOKE_DEFAULT')
