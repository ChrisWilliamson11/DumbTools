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
        alembic_count = 0
        
        for obj in col.objects:
            if obj.type == 'EMPTY':
                has_empty = True
            elif obj.type == 'VOLUME':
                has_volume = True
            elif obj.type in ('MESH', 'POINTCLOUD'):
                alembic_count += 1
        
        print(f"  Checking {col.name}: Empty={has_empty}, Volume={has_volume}, Alembics={alembic_count}")
        
        if has_empty and has_volume and alembic_count > 0:
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
        src_alembics = []
        
        for obj in template_col.objects:
            if obj.type == 'EMPTY':
                src_empty = obj
            elif obj.type == 'VOLUME':
                src_vdb = obj
            elif obj.type in ('MESH', 'POINTCLOUD'):
                src_alembics.append(obj)
        
        if not src_empty or not src_vdb or not src_alembics:
            print(f"Skipping invalid template {template_col.name} (Missing components)")
            return

        print(f"Step 2: Found Empty={src_empty.name}, VDB={src_vdb.name}, Alembics={len(src_alembics)}")

        # 3. Duplicate Objects (Deep Copy where needed)
        
        # Empty
        new_empty = src_empty.copy()
        
        # VDB
        new_vdb = src_vdb.copy()
        if src_vdb.data:
            # Deep copy data for unique settings
            new_vdb.data = src_vdb.data.copy()
            
        gen_col.objects.link(new_empty)
        gen_col.objects.link(new_vdb)

        # Restore Parenting for VDB
        new_vdb.parent = new_empty
        new_vdb.matrix_parent_inverse = src_vdb.matrix_parent_inverse.copy()
        
        # Handle Alembics Loop
        for src_alembic in src_alembics:
            new_alembic = src_alembic.copy()
            # Link
            gen_col.objects.link(new_alembic)
            # Restore Parenting
            new_alembic.parent = new_empty
            new_alembic.matrix_parent_inverse = src_alembic.matrix_parent_inverse.copy()
            
            print(f"  Duplicated Alembic: {new_alembic.name} ({new_alembic.type})")
            
            # Handle Alembic Cache Timing (MeshSequenceCache)
            abc_mod = None
            for mod in new_alembic.modifiers:
                if mod.type == 'MESH_SEQUENCE_CACHE':
                    abc_mod = mod
                    break
            
            if abc_mod and abc_mod.cache_file:
                print(f"  Found Alembic Modifier: {abc_mod.name}")
                
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
                        print(f"  Shifting Alembic Cache by {delta} frames (Start {start_frame} -> {target_start})")
                        shift_action(act, delta)
                    else:
                        print("  Could not find start frame in Alembic Action keyframes")
                else:
                    print("  Alembic CacheFile has no animation action")
            else:
                print("  No MeshSequenceCache modifier or CacheFile found on generated object")

        
        # Force update
        bpy.context.view_layer.update()
        print("Step 3: Objects Duplicated and Linked")

        # 4. Align Empty to Target
        
        # Check for Geometry Nodes Modifier
        has_geo_nodes = False
        for mod in target_obj.modifiers:
            if mod.type == 'NODES':
                has_geo_nodes = True
                break
        
        if has_geo_nodes:
            print("Target has Geometry Nodes. Calculating center from evaluated geometry...")
            # Get evaluated object to see result of GeoNodes
            depsgraph = bpy.context.evaluated_depsgraph_get()
            eval_target = target_obj.evaluated_get(depsgraph)
            
            # Calculate center of vertices
            if eval_target.type == 'MESH' and eval_target.data and len(eval_target.data.vertices) > 0:
                verts = [v.co for v in eval_target.data.vertices]
                center_local = sum(verts, mathutils.Vector()) / len(verts)
                # Transform to world space
                center_world = eval_target.matrix_world @ center_local
                
                new_empty.location = center_world
                # User requested no rotation adjustment for this case
                print(f"Step 4: Placed at Geometry Center: {center_world} (No Rotation Adjustment)")
            else:
                print("Warning: GeoNodes object has no vertices? Falling back to Origin.")
                new_empty.matrix_world = target_obj.matrix_world
        else:
            # Standard Behavior: Align to Object Origin + -90 X Rot
            rot_matrix = mathutils.Matrix.Rotation(math.radians(-90.0), 4, 'X')
            new_empty.matrix_world = target_obj.matrix_world @ rot_matrix
            print(f"Step 4: Aligned to Origin with -90 X Rot. New Matrix: {new_empty.matrix_world}")
        
        # 5. Set VDB Frame Start (To Current Frame)
        if new_vdb.data:
            print(f"Setting VDB Frame Start to {current_frame} (was {new_vdb.data.frame_start})")
            try:
                # User request: "set the start frame to the current frame"
                new_vdb.data.frame_start = int(current_frame)
            except Exception as e:
                print(f"Failed to set VDB frame start: {e}")
        

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
