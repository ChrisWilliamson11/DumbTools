# Tooltip: Generate Bullet Hit effects based on Geometry Nodes instance data
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

def find_bullet_hit_templates():
    if "BulletHits" not in bpy.data.collections:
        return []
    
    source_col = bpy.data.collections["BulletHits"]
    valid_templates = []
    
    for col in source_col.children:
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
        
        if has_empty and (has_volume or alembic_count > 0):
            valid_templates.append(col)
            
    return valid_templates

def iter_fcurves(action):
    if not action:
        return
    if hasattr(action, "fcurves") and action.fcurves:
        for fc in action.fcurves:
            yield fc
    if hasattr(action, "layers"):
        for layer in action.layers:
            if hasattr(layer, "strips"):
                for strip in layer.strips:
                    if hasattr(strip, "channelbags"):
                         for bag in strip.channelbags:
                             if hasattr(bag, "fcurves"):
                                 for fc in bag.fcurves:
                                     yield fc
                    if hasattr(strip, "fcurves"):
                        for fc in strip.fcurves:
                            yield fc
                    elif hasattr(strip, "channels"):
                         for fc in strip.channels:
                             yield fc

def frame_at_visible(action):
    for fc in iter_fcurves(action):
        if fc.data_path.endswith("hide_viewport") or fc.data_path.endswith("hide_render"):
            for kp in fc.keyframe_points:
                if kp.co[1] < 0.5:
                    return kp.co[0]
    return 0.0

def shift_action(action, delta):
    if not action:
        return
    for fc in iter_fcurves(action):
        for kp in fc.keyframe_points:
            kp.co[0] += delta
        fc.update()

def copy_and_align(template_col, matrix_world, birth_frame, target_obj_name):
    print(f"--- Spawning {template_col.name} at frame {birth_frame} ---")
    try:
        gen_col = get_or_create_collection(f"BulletHits_Generated_{target_obj_name}")
        
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
                
        if not src_empty or (not src_vdb and not src_alembics):
            print(f"Skipping invalid template {template_col.name}")
            return

        new_empty = src_empty.copy()
        
        new_vdb = None
        if src_vdb:
            new_vdb = src_vdb.copy()
            if src_vdb.data:
                new_vdb.data = src_vdb.data.copy()
        
        gen_col.objects.link(new_empty)
        if new_vdb:
            gen_col.objects.link(new_vdb)
            new_vdb.parent = new_empty
            new_vdb.matrix_parent_inverse = src_vdb.matrix_parent_inverse.copy()
        
        for src_alembic in src_alembics:
            new_alembic = src_alembic.copy()
            gen_col.objects.link(new_alembic)
            new_alembic.parent = new_empty
            new_alembic.matrix_parent_inverse = src_alembic.matrix_parent_inverse.copy()
            
            abc_mod = None
            for mod in new_alembic.modifiers:
                if mod.type == 'MESH_SEQUENCE_CACHE':
                    abc_mod = mod
                    break
            
            if abc_mod and abc_mod.cache_file:
                old_cache = abc_mod.cache_file
                new_cache = old_cache.copy()
                abc_mod.cache_file = new_cache
                
                if new_cache.animation_data and new_cache.animation_data.action:
                    new_cache.animation_data.action = new_cache.animation_data.action.copy()
                    act = new_cache.animation_data.action
                    
                    start_frame = None
                    for fc in iter_fcurves(act):
                        if fc.data_path.endswith("frame"):
                            if len(fc.keyframe_points) > 0:
                                t = fc.keyframe_points[0].co[0]
                                if start_frame is None or t < start_frame:
                                    start_frame = t
                    
                    if start_frame is not None:
                        # Align the cache animation start to birth_frame
                        abc_delta = (birth_frame - 1) - start_frame
                        shift_action(act, abc_delta)

        bpy.context.view_layer.update()

        # Align Empty to instance matrix
        new_empty.matrix_world = matrix_world
        
        # Set VDB Frame Start
        if new_vdb and new_vdb.data:
            try:
                new_vdb.data.frame_start = int(birth_frame - 1)
            except Exception as e:
                 print(f"Could not set frame_start: {e}")

        # Handle Animation & Timing for VDB (Visibility / Data)
        vis_frame = 0.0
        
        if new_vdb and new_vdb.animation_data and new_vdb.animation_data.action:
            new_vdb.animation_data.action = new_vdb.animation_data.action.copy()
            new_obj_action = new_vdb.animation_data.action
            vis_frame = frame_at_visible(new_obj_action)
        
        delta = birth_frame - vis_frame
        
        if new_vdb and new_vdb.animation_data and new_vdb.animation_data.action:
            shift_action(new_vdb.animation_data.action, delta)
            
        if new_vdb and new_vdb.data and new_vdb.data.animation_data and new_vdb.data.animation_data.action:
            new_vdb.data.animation_data.action = new_vdb.data.animation_data.action.copy()
            new_data_action = new_vdb.data.animation_data.action
            shift_action(new_data_action, delta)

    except Exception as e:
        import traceback
        print(f"CRITICAL ERROR in copy_and_align: {e}")
        traceback.print_exc()

def extract_instance_data(obj):
    depsgraph = bpy.context.evaluated_depsgraph_get()
    eval_obj = obj.evaluated_get(depsgraph)
    
    birth_frames = []
    if eval_obj.data and hasattr(eval_obj.data, "attributes") and 'BirthFrame' in eval_obj.data.attributes:
        attr = eval_obj.data.attributes['BirthFrame']
        birth_frames = [d.value for d in attr.data]
        print(f"Found 'BirthFrame' attribute with {len(birth_frames)} values.")
    else:
        print("Warning: 'BirthFrame' attribute not found on evaluated geometry.")
        return []

    instances = [inst for inst in depsgraph.object_instances if inst.is_instance and inst.parent.original == obj]
    
    hit_data = []
    bullet_hit_found = False
    
    # First pass: check if there are any instances with 'BulletHit' in name
    for inst in instances:
        if inst.object and "BulletHit" in inst.object.name:
            bullet_hit_found = True
            break
            
    print(f"Total instances evaluated: {len(instances)}. Contains 'BulletHit' explicitly? {bullet_hit_found}")
    
    for i, inst in enumerate(instances):
        # If user explicitly asked for 'BulletHit', filter by it if we found any. 
        # If none have that name, we process all of them to be safe.
        is_bullet_hit = False
        if inst.object and "BulletHit" in inst.object.name:
            is_bullet_hit = True
            
        if bullet_hit_found and not is_bullet_hit:
            continue
            
        bframe = birth_frames[i] if i < len(birth_frames) else 0.0
        
        matrix = inst.matrix_world.copy()
        
        hit_data.append({
            'matrix': matrix,
            'birth_frame': bframe,
            'name': inst.object.name if inst.object else "Unknown"
        })
        
    return hit_data

def main():
    print("--- Starting BulletHits Script ---")
    target_obj = bpy.context.object
    if not target_obj:
        print("No active object selected.")
        return
        
    templates = find_bullet_hit_templates()
    if not templates:
        print("No valid 'BulletHits' templates found. Please create a 'BulletHits' collection with subcollections containing an Empty and VDB/Alembic.")
        return
        
    hit_data = extract_instance_data(target_obj)
    
    if not hit_data:
        print("No instance data extracted. Make sure the object has geometry node instances and a 'BirthFrame' attribute.")
        return
        
    print(f"Found {len(hit_data)} instances to process.")
    
    for hit in hit_data:
        template = random.choice(templates)
        copy_and_align(template, hit['matrix'], hit['birth_frame'], target_obj.name)
        
    print("--- Main Function Finished ---")

main()
