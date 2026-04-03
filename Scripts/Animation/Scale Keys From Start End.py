import bpy

class ANIM_OT_scale_keys_from_start_end(bpy.types.Operator):
    """Scale selected keyframes in time relative to the first or last keyframe of each channel"""
    bl_idname = "anim.scale_keys_from_start_end"
    bl_label = "Scale Keys From Start/End"
    bl_options = {'REGISTER', 'UNDO'}

    mode: bpy.props.EnumProperty(
        name="Origin",
        items=[
            ('START', "From Start", "Scale relative to the first selected keyframe"),
            ('END', "From End", "Scale relative to the last selected keyframe"),
        ],
        default='START'
    )
    
    scale_amount: bpy.props.FloatProperty(
        name="Scale Amount",
        default=1.0,
        description="Factor to scale the keyframes by"
    )

    @classmethod
    def poll(cls, context):
        return context.active_object and context.active_object.animation_data

    def execute(self, context):
        objects = context.selected_objects
        if not objects:
            objects = [context.active_object]
        
        changed_count = 0
        
        # Iterate over all selected objects
        for obj in objects:
            if not obj.animation_data or not obj.animation_data.action:
                continue
                
            action = obj.animation_data.action
            
            # Iterate over all channels (fcurves) in the action
            for fcurve in action.fcurves:
                # Get all selected keyframes in this channel
                selected_keys = [kp for kp in fcurve.keyframe_points if kp.select_control_point]
                
                if not selected_keys:
                    continue
                
                changed_count += 1
                
                # Determine origin frame for this specific channel
                frames = [kp.co[0] for kp in selected_keys]
                
                if self.mode == 'START':
                    origin = min(frames)
                else:
                    origin = max(frames)
                
                # Apply scaling to each selected keyframe
                for kp in selected_keys:
                    # Scale the keyframe coordinate
                    kp.co[0] = origin + (kp.co[0] - origin) * self.scale_amount
                    
                    # Scale the handles as well to preserve curve shape
                    # Handles are absolute coordinates in time
                    kp.handle_left[0] = origin + (kp.handle_left[0] - origin) * self.scale_amount
                    kp.handle_right[0] = origin + (kp.handle_right[0] - origin) * self.scale_amount
                
                fcurve.update()
        
        if changed_count == 0:
            self.report({'WARNING'}, "No selected keyframes found")
            return {'CANCELLED'}
        
        # Update header to show confirmation?
        self.report({'INFO'}, f"Scaled {changed_count} channels")
        
        return {'FINISHED'}

    def invoke(self, context, event):
        wm = context.window_manager
        return wm.invoke_props_dialog(self)

def menu_func(self, context):
    self.layout.operator(ANIM_OT_scale_keys_from_start_end.bl_idname)

def register():
    bpy.utils.register_class(ANIM_OT_scale_keys_from_start_end)
    bpy.types.DOPESHEET_MT_key.append(menu_func)
    bpy.types.GRAPH_MT_key.append(menu_func)

def unregister():
    bpy.types.DOPESHEET_MT_key.remove(menu_func)
    bpy.types.GRAPH_MT_key.remove(menu_func)
    bpy.utils.unregister_class(ANIM_OT_scale_keys_from_start_end)

if __name__ == "__main__":
    register()
    # Automatically invoke for testing/direct usage
    # usage: Run Script in Text Editor with keyframes selected
    try:
        bpy.ops.anim.scale_keys_from_start_end('INVOKE_DEFAULT')
    except Exception as e:
        print(f"Could not invoke operator: {e}")
