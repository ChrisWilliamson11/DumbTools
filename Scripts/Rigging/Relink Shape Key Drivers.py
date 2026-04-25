# Tooltip: Select meshes with broken shape key drivers, then SHIFT+SELECT target object. Run script to relink missing objects.

import bpy

class DUMBTOOLS_OT_relink_shapekey_drivers(bpy.types.Operator):
    bl_idname = "dumbtools.relink_shapekey_drivers"
    bl_label = "Relink Shape Key Drivers"
    bl_description = "Relinks shape key drivers on selected meshes to use the active object as the target"
    bl_options = {'REGISTER', 'UNDO'}

    @classmethod
    def poll(cls, context):
        has_sel = len(context.selected_objects) > 1
        has_active = context.active_object is not None
        return has_sel and has_active

    def execute(self, context):
        target_obj = context.active_object
        
        if not target_obj:
            self.report({'WARNING'}, "No active target object selected")
            return {'CANCELLED'}

        drivers_updated = 0
        objects_updated = 0
        
        for obj in context.selected_objects:
            if obj == target_obj:
                continue
                
            if obj.type != 'MESH' or not obj.data or not obj.data.shape_keys:
                continue
            
            anim_data = obj.data.shape_keys.animation_data
            if not anim_data or not anim_data.drivers:
                continue
            
            obj_modified = False
            for fcurve in anim_data.drivers:
                driver_modified = False
                for var in fcurve.driver.variables:
                    for target in var.targets:
                        is_eye_bone = hasattr(target, 'bone_target') and target.bone_target in ('EyeBoneRight', 'EyeBoneLeft')
                        
                        if is_eye_bone:
                            if obj.parent and target.id != obj.parent:
                                target.id = obj.parent
                                driver_modified = True
                        elif target.id is None:
                            target.id = target_obj
                            driver_modified = True
                
                if driver_modified:
                    drivers_updated += 1
                    obj_modified = True
                    
            if obj_modified:
                objects_updated += 1

        try:
            bpy.context.view_layer.update()
            bpy.context.evaluated_depsgraph_get().update()
        except Exception:
            pass

        self.report({'INFO'}, f"Relinked {drivers_updated} shape key drivers across {objects_updated} objects to {target_obj.name}")
        return {'FINISHED'}

def register():
    try:
        bpy.utils.register_class(DUMBTOOLS_OT_relink_shapekey_drivers)
    except ValueError:
        pass

def unregister():
    try:
        bpy.utils.unregister_class(DUMBTOOLS_OT_relink_shapekey_drivers)
    except ValueError:
        pass

register()
bpy.ops.dumbtools.relink_shapekey_drivers('INVOKE_DEFAULT')
