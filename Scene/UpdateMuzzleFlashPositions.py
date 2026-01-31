import bpy
import mathutils
import math

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

def frame_at_visible(action):
    """
    Finds the frame where 'hide_viewport' (or 'hide_render') becomes False (0.0).
    Assumes a sequence of True -> False -> True.
    """
    if not action:
        return None
        
    for fc in iter_fcurves(action):
        if fc.data_path.endswith("hide_viewport") or fc.data_path.endswith("hide_render"):
            for kp in fc.keyframe_points:
                # If value is close to 0 (False/Visible)
                if kp.co[1] < 0.5:
                    return kp.co[0]
    return None

def update_positions():
    print("--- Starting Update Muzzle Flash Positions ---")
    
    # 1. Get Target Object
    target_obj = bpy.context.object
    if not target_obj:
        print("Error: No target object selected.")
        return

    # 2. Find Collection
    col_name = "Muzzleflashes_Generated" 
    # Try case-insensitive lookup
    found_col = None
    if col_name in bpy.data.collections:
        found_col = bpy.data.collections[col_name]
    else:
        # Fallback check
        for c in bpy.data.collections:
            if c.name.lower() == "muzzleflashes_generated":
                found_col = c
                break
    
    if not found_col:
        print(f"Error: Collection '{col_name}' not found.")
        return

    print(f"Found Collection: {found_col.name}")
    
    # 3. Store Original Frame
    original_frame = bpy.context.scene.frame_current
    
    # 4. Iterate and Update
    updated_count = 0
    
    # Rotation Matrix (-90 X)
    rot_matrix = mathutils.Matrix.Rotation(math.radians(-90.0), 4, 'X')
    
    # Identify Flash Roots (Empties with VDB children)
    # We iterate all objects in collection
    for obj in found_col.objects:
        if obj.type == 'EMPTY':
            # Check for VDB Child
            vdb_child = None
            for child in obj.children:
                if child.type == 'VOLUME':
                    vdb_child = child
                    break
            
            if vdb_child:
                # Finding visible frame from VDB child animation
                vis_frame = None
                
                # Check Object Action
                if vdb_child.animation_data and vdb_child.animation_data.action:
                    vis_frame = frame_at_visible(vdb_child.animation_data.action)
                
                if vis_frame is not None:
                    # Move Timeline
                    bpy.context.scene.frame_set(int(vis_frame))
                    bpy.context.view_layer.update()
                    
                    # Align
                    obj.matrix_world = target_obj.matrix_world @ rot_matrix
                    
                    print(f"Updated {obj.name}: Frame {int(vis_frame)}")
                    updated_count += 1
                else:
                    print(f"Skipping {obj.name}: Could not determine visible frame on child {vdb_child.name}")
    
    # 5. Restore Frame
    bpy.context.scene.frame_set(original_frame)
    print(f"--- Finished. Updated {updated_count} flashes. ---")

update_positions()
