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

def find_templates():
    if "WaterSplashes" not in bpy.data.collections:
        return []
    
    source_col = bpy.data.collections["WaterSplashes"]
    valid_templates = []
    
    print(f"Searching for templates in 'WaterSplashes' (Children: {len(source_col.children)})")
    
    for col in source_col.children:
        # Check for Empty, Volume (VDB) and Mesh/PointCloud (Alembic)
        has_empty = False
        has_volume = False
        has_alembic = False
        
        for obj in col.objects:
            if obj.type == 'EMPTY':
                has_empty = True
            elif obj.type == 'VOLUME':
                has_volume = True
            elif obj.type in ('MESH', 'POINTCLOUD'):
                has_alembic = True
        
        print(f"  Checking {col.name}: Empty={has_empty}, Volume={has_volume}, Alembic={has_alembic}")
        
        if has_empty and has_volume and has_alembic:
            valid_templates.append(col)
        else:
            print(f"    -> REJECTED {col.name}")
            
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
        gen_col = get_or_create_collection("WaterSplashes_Generated")
        
        # 2. Identify Source Objects
        src_empty = None
        src_vdb = None
        src_alembic = None
        
        for obj in template_col.objects:
            if obj.type == 'EMPTY':
                src_empty = obj
            elif obj.type == 'VOLUME':
                src_vdb = obj
            elif obj.type in ('MESH', 'POINTCLOUD'):
                src_alembic = obj
        
        if not src_empty or not src_vdb or not src_alembic:
            print(f"Skipping invalid template {template_col.name} (Missing components)")
            return

        print(f"Step 2: Found Empty={src_empty.name}, VDB={src_vdb.name}, Alembic={src_alembic.name} ({src_alembic.type})")

        # 3. Duplicate Objects (Deep Copy where needed)
        
        # Empty
        new_empty = src_empty.copy()
        
        # VDB
        new_vdb = src_vdb.copy()
        if src_vdb.data:
            # Deep copy data for unique settings
            new_vdb.data = src_vdb.data.copy()
            
        # Alembic (Mesh or PointCloud)
        new_alembic = src_alembic.copy()
        # Share mesh data (geometry) usually fine for alembic, 
        # but modifiers need inspection.
        # Deep copy data just in case if users want unique override on mesh level?
        # Usually MeshSequenceCache modifier is on Object.
        
        print(f"Step 3: Objects Duplicated (Alembic Type: {new_alembic.type})")
        
        # Link to Collection
        for o in [new_empty, new_vdb, new_alembic]:
            gen_col.objects.link(o)

        # Restore Parenting
        new_vdb.parent = new_empty
        new_vdb.matrix_parent_inverse = src_vdb.matrix_parent_inverse.copy()
        new_alembic.parent = new_empty
        new_alembic.matrix_parent_inverse = src_alembic.matrix_parent_inverse.copy()
        
        # Force update
        bpy.context.view_layer.update()

        # 4. Align Empty to Target (-90 X Rot)
        rot_matrix = mathutils.Matrix.Rotation(math.radians(-90.0), 4, 'X')
        new_empty.matrix_world = target_obj.matrix_world @ rot_matrix
        print(f"Step 4: Aligned. New Matrix: {new_empty.matrix_world}")
        
        # 5. Set VDB Frame Start (To Current Frame)
        if new_vdb.data:
            print(f"Setting VDB Frame Start to {current_frame} (was {new_vdb.data.frame_start})")
            try:
                # User request: "set the start frame to the current frame"
                new_vdb.data.frame_start = int(current_frame)
            except Exception as e:
                print(f"Failed to set VDB frame start: {e}")
        
        # 6. Handle Alembic Cache Timing (MeshSequenceCache)
        # Find modifier
        abc_mod = None
        for mod in new_alembic.modifiers:
            if mod.type == 'MESH_SEQUENCE_CACHE':
                abc_mod = mod
                break
        
        if abc_mod and abc_mod.cache_file:
            print(f"Found Alembic Modifier: {abc_mod.name}")
            
            # Duplicate CacheFile to allow unique offset
            old_cache = abc_mod.cache_file
            new_cache = old_cache.copy()
            abc_mod.cache_file = new_cache
            
            # Find Animation on CacheFile (frame property)
            if new_cache.animation_data and new_cache.animation_data.action:
                # Make Action Unique
                new_cache.animation_data.action = new_cache.animation_data.action.copy()
                act = new_cache.animation_data.action
                
                # Find Start Frame of this Action
                start_frame = None
                for fc in iter_fcurves(act):
                    if fc.data_path.endswith("frame"):
                        # Get first keyframe
                        if len(fc.keyframe_points) > 0:
                            # Assuming sorted, or check min
                            t = fc.keyframe_points[0].co[0]
                            if start_frame is None or t < start_frame:
                                start_frame = t
                
                if start_frame is not None:
                    # Calculate Delta
                    # "offset so the first is the frame before the current"
                    target_start = current_frame - 1
                    delta = target_start - start_frame
                    print(f"Shifting Alembic Cache by {delta} frames (Start {start_frame} -> {target_start})")
                    shift_action(act, delta)
                else:
                    print("Could not find start frame in Alembic Action keyframes")
            else:
                print("Alembic CacheFile has no animation action")
        else:
            print("No MeshSequenceCache modifier or CacheFile found on generated object")

        print("--- copy_and_align Completed Successfully ---")

    except Exception as e:
        import traceback
        print(f"CRITICAL ERROR: {e}")
        traceback.print_exc()

def main():
    print("--- Starting WaterSplashes Script ---")
    target_obj = bpy.context.object
    if not target_obj:
        print("No active object selected.")
        return
        
    current_frame = bpy.context.scene.frame_current
    
    templates = find_templates()
    if not templates:
        print("No valid 'WaterSplashes' templates found.")
        return
        
    template = random.choice(templates)
    print(f"Selected Template: {template.name}")
    
    copy_and_align(template, target_obj, current_frame)
    print("--- Main Function Finished ---")

main()
