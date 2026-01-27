import bpy
import random
import mathutils
import math

def get_or_create_collection(name):
    if name in bpy.data.collections:
        return bpy.data.collections[name]
    else:
        new_col = bpy.data.collections.new(name)
        bpy.context.scene.collection.children.link(new_col)
        return new_col

def find_muzzle_flash_templates():
    if "MuzzleFlashes" not in bpy.data.collections:
        return []
    
    source_col = bpy.data.collections["MuzzleFlashes"]
    valid_templates = []
    
    for col in source_col.children:
        # Check for Empty and Volume (VDB)
        has_empty = False
        has_volume = False
        
        for obj in col.objects:
            if obj.type == 'EMPTY':
                has_empty = True
            elif obj.type == 'VOLUME':
                has_volume = True
        
        if has_empty and has_volume:
            valid_templates.append(col)
            
    return valid_templates

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
    for fc in iter_fcurves(action):
        if fc.data_path.endswith("hide_viewport") or fc.data_path.endswith("hide_render"):
            for kp in fc.keyframe_points:
                # If value is close to 0 (False/Visible)
                if kp.co[1] < 0.5:
                    return kp.co[0]
    return 0.0

def shift_action(action, delta):
    """Shifts all keyframes in the action by delta."""
    if not action:
        return
    for fc in iter_fcurves(action):
        for kp in fc.keyframe_points:
            kp.co[0] += delta
        fc.update()

def copy_and_align(template_col, target_obj, current_frame):
    print(f"--- Entering copy_and_align for {template_col.name} ---")
    try:
        # 1. Create/Get Gen Collection
        gen_col = get_or_create_collection("Muzzleflashes_Generated")
        print("Step 1: Collection Got/Created")
        
        # 2. Identify Source Objects
        src_empty = None
        src_vdb = None
        
        for obj in template_col.objects:
            if obj.type == 'EMPTY':
                src_empty = obj
            elif obj.type == 'VOLUME':
                src_vdb = obj
                
        if not src_empty or not src_vdb:
            print(f"Skipping invalid template {template_col.name} (Missing Empty or Volume)")
            return

        print(f"Step 2: Source Objects Found: Empty={src_empty.name}, VDB={src_vdb.name}")

        # 3. Duplicate Objects (Using Data API to avoid Context issues)
        # Copy Empty
        new_empty = src_empty.copy()
        # Empty data is usually None or shared, copy() on object is enough.
        
        # Copy VDB
        new_vdb = src_vdb.copy()
        if src_vdb.data:
            # Deep copy data to ensure frame_offset properties/animation are unique
            new_vdb.data = src_vdb.data.copy()
        
        print("Step 3: Objects Duplicated")
        
        # Link to Generated Collection
        gen_col.objects.link(new_empty)
        gen_col.objects.link(new_vdb)
        print("Step 3b: Objects Linked to Collection")
        
        # Restore Parent Relationship
        new_vdb.parent = new_empty
        # Preserve transform offset from parent
        new_vdb.matrix_parent_inverse = src_vdb.matrix_parent_inverse.copy()

        # Force update to ensure matrices and relationships are valid
        bpy.context.view_layer.update()

        # 4. Align Empty to Target with -90 X rotation
        # Apply rotation relative to the target's orientation
        rot_matrix = mathutils.Matrix.Rotation(math.radians(-90.0), 4, 'X')
        new_empty.matrix_world = target_obj.matrix_world @ rot_matrix
        print(f"Step 4: Aligned Empty to Target. New Matrix: {new_empty.matrix_world}")
        
        # 5. Set Frame Start (Randomly current or current-1)
        if new_vdb.data:
            # Using getattr/setattr just in case, but standard API is .frame_start
            offset_val = random.choice([0, 1])
            new_start = int(current_frame - offset_val)
            
            print(f"Attempting to set VDB Frame Start to {new_start} (Current Frame: {current_frame})")
            print(f"  Old Frame Start: {new_vdb.data.frame_start}")
            
            try:
                new_vdb.data.frame_start = new_start
            except AttributeError:
                 print("Could not set frame_start on VDB data (AttributeError)")
            except Exception as e:
                 print(f"Could not set frame_start: {e}")
                 
            # Read back to verify
            print(f"  New Frame Start (Readback): {new_vdb.data.frame_start}")
        else:
            print("Step 5 Warning: New VDB has no Data!")

        # 6. Handle Animation & Timing
        # We need to find the "visible frame" from the original (or new) action.
        # We'll use the NEW action so we can shift it comfortably.
        
        # --- Object Action (Visibility) ---
        vis_frame = 0.0
        
        # helper to debug fcurves
        def debug_print_fcurves(act, name):
            print(f"--- Debugging Action: {name} ---")
            count = 0
            for fc in iter_fcurves(act):
                print(f"  FCurve: {fc.data_path} [{fc.array_index}]")
                count += 1
            print(f"  Total FCurves found: {count}")

        if new_vdb.animation_data and new_vdb.animation_data.action:
            # Make Unique
            new_vdb.animation_data.action = new_vdb.animation_data.action.copy()
            new_obj_action = new_vdb.animation_data.action
            
            # Verify curves found
            debug_print_fcurves(new_obj_action, "Object Action")
            
            # Find trigger frame
            vis_frame = frame_at_visible(new_obj_action)
            print(f"Detected Visible Frame: {vis_frame}")
        else:
            print("Step 6 Info: VDB has no Object Action (Visibility)")
        
        # Calculate Delta
        delta = current_frame - vis_frame
        print(f"Shifting Keyframes by {delta} frames (Visible at {vis_frame} -> {current_frame})")
        
        # Shift Object Action
        if new_vdb.animation_data and new_vdb.animation_data.action:
            shift_action(new_vdb.animation_data.action, delta)
            
        # --- Data Action (Frame Offset) ---
        if new_vdb.data and new_vdb.data.animation_data and new_vdb.data.animation_data.action:
            # Make Unique
            new_vdb.data.animation_data.action = new_vdb.data.animation_data.action.copy()
            new_data_action = new_vdb.data.animation_data.action
            
            debug_print_fcurves(new_data_action, "Data Action")
            
            # Shift
            shift_action(new_data_action, delta)
        else:
             print("Step 6 Info: VDB has no Data Action (Frame Offset)")
        
        print("--- copy_and_align Completed Successfully ---")

    except Exception as e:
        import traceback
        print(f"CRITICAL ERROR in copy_and_align: {e}")
        traceback.print_exc()

def main():
    print("--- Starting MuzzleFlashes Script ---")
    target_obj = bpy.context.object
    if not target_obj:
        print("No active object selected.")
        return
        
    current_frame = bpy.context.scene.frame_current
    
    templates = find_muzzle_flash_templates()
    if not templates:
        print("No valid 'MuzzleFlashes' templates found.")
        return
        
    template = random.choice(templates)
    print(f"Selected Muzzle Flash Template: {template.name}")
    
    copy_and_align(template, target_obj, current_frame)
    print("--- Main Function Finished ---")

main()


