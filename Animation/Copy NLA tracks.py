# Tooltip:  Copy NLA animation from one armature to another
import bpy

def copy_nla_animation(source_armature, target_armature):
    # Clear any existing NLA tracks on the target armature
    target_armature.animation_data_clear()
    
    # Ensure the source armature has animation data
    if not source_armature.animation_data or not source_armature.animation_data.nla_tracks:
        print("Source armature has no NLA tracks to copy.")
        return

    # Create animation data for the target armature if it doesn't exist
    if not target_armature.animation_data:
        target_armature.animation_data_create()
    
    # Copy each NLA track from the source to the target armature
    for track in source_armature.animation_data.nla_tracks:
        new_track = target_armature.animation_data.nla_tracks.new()
        new_track.name = track.name
        
        # Copy the strips within the track
        for strip in track.strips:
            new_strip = new_track.strips.new(
                name=strip.name,
                start=int(strip.frame_start),  # Ensure start is an integer
                action=strip.action
            )
            new_strip.action_frame_start = strip.action_frame_start
            new_strip.action_frame_end = strip.action_frame_end
            new_strip.scale = strip.scale
            new_strip.repeat = strip.repeat
            new_strip.blend_in = strip.blend_in
            new_strip.blend_out = strip.blend_out
            new_strip.use_animated_influence = strip.use_animated_influence
            new_strip.use_animated_time = strip.use_animated_time
            new_strip.influence = strip.influence
            # Skipping 'time' attribute as it doesn't exist in 'NlaStrip'

def main():
    selected_objects = bpy.context.selected_objects
    if len(selected_objects) != 2:
        print("Please select exactly 2 armatures.")
        return
    
    source_armature = bpy.context.active_object
    if source_armature.type != 'ARMATURE':
        print("The active object is not an armature.")
        return
    
    target_armature = [obj for obj in selected_objects if obj != source_armature][0]
    if target_armature.type != 'ARMATURE':
        print("The selected object is not an armature.")
        return
    
    copy_nla_animation(source_armature, target_armature)
    print(f"NLA animation copied from {source_armature.name} to {target_armature.name}")


main()
