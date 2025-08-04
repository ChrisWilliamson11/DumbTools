# Tooltip:  Delete all keyframes after the current frame for the selected bones in the active armature.
import bpy

def get_nla_offset(obj):
    """
    Calculates the correct offset to align the action's timeline with the NLA strip's timeline.
    """
    if obj.animation_data and obj.animation_data.use_tweak_mode:
        for track in obj.animation_data.nla_tracks:
            for strip in track.strips:
                if strip.active:
                    # Since the direct application of the frame_start as offset seems incorrect,
                    # let's try adjusting based on the relationship between strip and action start frames.
                    # This takes the strip's start frame, but considers the action's start frame to correct the offset.
                    return strip.frame_start - (strip.action_frame_start - 1)
    return 0

def select_keyframes_before_current_frame():
    obj = bpy.context.active_object
    if not obj or obj.type != 'ARMATURE' or not obj.animation_data or not obj.animation_data.action:
        print("No active armature with animation data found.")
        return

    current_frame = bpy.context.scene.frame_current
    offset = get_nla_offset(obj)
    
    # Adjust the current frame using the newly calculated offset
    adjusted_current_frame = current_frame - offset

    for bone in bpy.context.selected_pose_bones:
        bone_name = bone.name
        action = obj.animation_data.action
        
        for fcurve in action.fcurves:
            if bone_name in fcurve.data_path:
                for keyframe in fcurve.keyframe_points:
                    if keyframe.co.x > adjusted_current_frame:
                        keyframe.select_control_point = True
                    else:
                        keyframe.select_control_point = False

def delete_selected_keyframes():
    obj = bpy.context.active_object
    if not obj.animation_data or not obj.animation_data.action:
        print("No active object with animation data found.")
        return

    action = obj.animation_data.action
    offset = get_nla_offset(obj)
    adjusted_current_frame = bpy.context.scene.frame_current - offset

    for fcurve in action.fcurves:
        keyframes_to_remove = [keyframe for keyframe in fcurve.keyframe_points if keyframe.co.x > adjusted_current_frame]
        
        for keyframe in reversed(keyframes_to_remove):
            fcurve.keyframe_points.remove(keyframe)

# Run the functions
select_keyframes_before_current_frame()
delete_selected_keyframes()

