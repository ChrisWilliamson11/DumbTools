import bpy

def iter_fcurves(action):
    """
    Yields fcurves from an Action, handling both Legacy Blender and Blender 5+ Layered Animation.
    """
    if not action:
        return
    # Legacy: Direct fcurves list
    if hasattr(action, "fcurves") and action.fcurves:
        for fc in action.fcurves:
            yield fc
    # Blender 5+: Layers and Strips
    if hasattr(action, "layers"):
        for layer in action.layers:
            if hasattr(layer, "strips"):
                for strip in layer.strips:
                    if hasattr(strip, "channelbags"):
                         for bag in strip.channelbags:
                             if hasattr(bag, "fcurves"):
                                 for fc in bag.fcurves:
                                     yield fc
                    # Fallback for other structures (legacy transition or direct strips)
                    if hasattr(strip, "fcurves"):
                        for fc in strip.fcurves:
                            yield fc
                    elif hasattr(strip, "channels"):
                         for fc in strip.channels:
                             yield fc

def get_selected_entities_fcurves(context):
    fcurves = []
    
    if context.mode == 'POSE' and context.selected_pose_bones:
        obj_to_bones = {}
        for bone in context.selected_pose_bones:
            obj = bone.id_data
            if obj not in obj_to_bones:
                obj_to_bones[obj] = set()
            obj_to_bones[obj].add(bone.name)
            
        for obj, bone_names in obj_to_bones.items():
            if obj.animation_data and obj.animation_data.action:
                act = obj.animation_data.action
                for fc in iter_fcurves(act):
                    dp = getattr(fc, "data_path", "")
                    for bone_name in bone_names:
                        # Match exact bone names in data_path
                        prefix1 = f'pose.bones["{bone_name}"]'
                        prefix2 = f"pose.bones['{bone_name}']"
                        if dp.startswith(prefix1) or dp.startswith(prefix2):
                            fcurves.append(fc)
                            break
    else:
        for obj in context.selected_objects:
            if obj.animation_data and obj.animation_data.action:
                act = obj.animation_data.action
                for fc in iter_fcurves(act):
                    fcurves.append(fc)
                    
    return fcurves

class ANIM_OT_copy_keys_to_next(bpy.types.Operator):
    bl_idname = "animation.copy_keys_to_next"
    bl_label = "Copy Keys To Next"
    bl_description = "Move to the next frame with keys on selected bones, delete them, and duplicate keys from the original frame"
    bl_options = {'REGISTER', 'UNDO'}

    @classmethod
    def poll(cls, context):
        return (context.mode == 'POSE' and context.selected_pose_bones) or context.selected_objects

    def execute(self, context):
        current_frame = context.scene.frame_current
        fcurves = get_selected_entities_fcurves(context)
        
        if not fcurves:
            self.report({'WARNING'}, "No animation data found for selection.")
            return {'CANCELLED'}
            
        # Find next frame
        next_frame = float('inf')
        for fc in fcurves:
            for k in fc.keyframe_points:
                if k.co[0] > current_frame + 0.1:
                    if k.co[0] < next_frame:
                        next_frame = k.co[0]
                        
        if next_frame == float('inf'):
            self.report({'INFO'}, "No next keyframe found.")
            return {'CANCELLED'}
            
        # Update scene frame
        context.scene.frame_set(int(round(next_frame)))
        
        for fc in fcurves:
            key_current = None
            key_next = None
            
            for k in fc.keyframe_points:
                if abs(k.co[0] - current_frame) < 0.1:
                    key_current = k
                if abs(k.co[0] - next_frame) < 0.1:
                    key_next = k
                    
            if key_next:
                fc.keyframe_points.remove(key_next)
                
            if key_current:
                new_k = fc.keyframe_points.insert(next_frame, key_current.co[1], options={'FAST'})
                new_k.interpolation = key_current.interpolation
                if hasattr(key_current, "easing"):
                    new_k.easing = key_current.easing
                
                # Copy handle types and relative positions
                new_k.handle_left_type = 'FREE'
                new_k.handle_right_type = 'FREE'
                
                dl_x = key_current.handle_left[0] - key_current.co[0]
                dl_y = key_current.handle_left[1] - key_current.co[1]
                new_k.handle_left = (next_frame + dl_x, key_current.co[1] + dl_y)
                
                dr_x = key_current.handle_right[0] - key_current.co[0]
                dr_y = key_current.handle_right[1] - key_current.co[1]
                new_k.handle_right = (next_frame + dr_x, key_current.co[1] + dr_y)
                
                new_k.handle_left_type = key_current.handle_left_type
                new_k.handle_right_type = key_current.handle_right_type
                
        for fc in fcurves:
            fc.update()
            
        return {'FINISHED'}

def register():
    try:
        bpy.utils.register_class(ANIM_OT_copy_keys_to_next)
    except ValueError:
        bpy.utils.unregister_class(ANIM_OT_copy_keys_to_next)
        bpy.utils.register_class(ANIM_OT_copy_keys_to_next)

def unregister():
    try:
        bpy.utils.unregister_class(ANIM_OT_copy_keys_to_next)
    except ValueError:
        pass

register()
bpy.ops.animation.copy_keys_to_next('INVOKE_DEFAULT')
