# Tooltip: Bakes action for bones with Child Of constraints, applying reorientation and removing the constraints.

import bpy

def bake_reoriented_action():
    obj = bpy.context.active_object
    if not obj or obj.type != 'ARMATURE':
        print("Must have an Armature active.")
        return
        
    original_mode = bpy.context.mode
    if original_mode != 'POSE':
        bpy.ops.object.mode_set(mode='POSE')
        
    # Find bones with Child Of constraints
    bones_to_bake = []
    for pb in obj.pose.bones:
        has_child_of = any(con.type == 'CHILD_OF' for con in pb.constraints)
        
        # In Blender 4.0+, the select property moved from Bone to PoseBone
        if has_child_of:
            bones_to_bake.append(pb)
            try:
                pb.select = True
            except AttributeError:
                pb.bone.select = True
        else:
            try:
                pb.select = False
            except AttributeError:
                pb.bone.select = False
            
    if not bones_to_bake:
        print("No bones found with Child Of constraints.")
        return
    
    # Determine the frame range to bake
    # Default to scene frame range
    start_frame = bpy.context.scene.frame_start
    end_frame = bpy.context.scene.frame_end
    
    action = obj.animation_data.action if obj.animation_data else None
    has_nla = bool(obj.animation_data and obj.animation_data.nla_tracks and \
                   any(len(track.strips) > 0 for track in obj.animation_data.nla_tracks))
                   
    use_current = True
    
    if action:
        # Bake over the current action's frame range
        # Note: action.frame_range returns (start, end)
        start_frame = int(action.frame_range[0])
        end_frame = int(action.frame_range[1])
    elif has_nla:
        # If no active action, but NLA strips exist, bake to a new action
        use_current = False
        # Calculate NLA frame bounds
        strips = [strip for track in obj.animation_data.nla_tracks for strip in track.strips]
        if strips:
            start_frame = int(min(strip.frame_start for strip in strips))
            end_frame = int(max(strip.frame_end for strip in strips))
            
    # Bake the action
    bpy.ops.nla.bake(
        frame_start=start_frame, 
        frame_end=end_frame, 
        step=1, 
        only_selected=True, 
        visual_keying=True, 
        clear_constraints=True, 
        clear_parents=False, 
        use_current_action=use_current, 
        bake_types={'POSE'}
    )
    
    if original_mode != 'POSE':
        bpy.ops.object.mode_set(mode=original_mode)
    
bake_reoriented_action()
