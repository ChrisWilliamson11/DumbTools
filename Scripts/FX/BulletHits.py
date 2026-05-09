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
        has_empty, has_volume, alembic_count = False, False, 0
        for obj in col.objects:
            if obj.type == 'EMPTY': has_empty = True
            elif obj.type == 'VOLUME': has_volume = True
            elif obj.type in ('MESH', 'POINTCLOUD'): alembic_count += 1
        if has_empty and (has_volume or alembic_count > 0):
            valid_templates.append(col)
    return valid_templates

def iter_fcurves(action):
    if not action: return
    if hasattr(action, "fcurves") and action.fcurves:
        for fc in action.fcurves: yield fc
    if hasattr(action, "layers"):
        for layer in action.layers:
            if hasattr(layer, "strips"):
                for strip in layer.strips:
                    if hasattr(strip, "fcurves"):
                        for fc in strip.fcurves: yield fc
                    elif hasattr(strip, "channels"):
                         for fc in strip.channels: yield fc

def frame_at_visible(action):
    for fc in iter_fcurves(action):
        if fc.data_path.endswith("hide_viewport") or fc.data_path.endswith("hide_render"):
            for kp in fc.keyframe_points:
                if kp.co[1] < 0.5: return kp.co[0]
    return 0.0

def shift_action(action, delta):
    if not action: return
    for fc in iter_fcurves(action):
        for kp in fc.keyframe_points: kp.co[0] += delta
        fc.update()

def copy_and_align(template_col, matrix_world, birth_frame, target_obj_name):
    print(f"--- Spawning {template_col.name} at frame {birth_frame} ---")
    try:
        gen_col = get_or_create_collection(f"BulletHits_Generated_{target_obj_name}")
        src_empty, src_vdb, src_alembics = None, None, []
        for obj in template_col.objects:
            if obj.type == 'EMPTY': src_empty = obj
            elif obj.type == 'VOLUME': src_vdb = obj
            elif obj.type in ('MESH', 'POINTCLOUD'): src_alembics.append(obj)
        if not src_empty or (not src_vdb and not src_alembics): return

        new_empty = src_empty.copy()
        new_vdb = None
        if src_vdb:
            new_vdb = src_vdb.copy()
            if src_vdb.data: new_vdb.data = src_vdb.data.copy()
        
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
            abc_mod = next((m for m in new_alembic.modifiers if m.type == 'MESH_SEQUENCE_CACHE'), None)
            if abc_mod and abc_mod.cache_file:
                abc_mod.cache_file = abc_mod.cache_file.copy()
                new_cache = abc_mod.cache_file
                if new_cache.animation_data and new_cache.animation_data.action:
                    new_cache.animation_data.action = new_cache.animation_data.action.copy()
                    act = new_cache.animation_data.action
                    start_frame = min((fc.keyframe_points[0].co[0] for fc in iter_fcurves(act) if fc.data_path.endswith("frame")), default=None)
                    if start_frame is not None:
                        shift_action(act, (birth_frame - 1) - start_frame)

        bpy.context.view_layer.update()
        new_empty.matrix_world = matrix_world
        if new_vdb and new_vdb.data:
            try: new_vdb.data.frame_start = int(birth_frame - 1)
            except: pass

        vis_frame = 0.0
        if new_vdb and new_vdb.animation_data and new_vdb.animation_data.action:
            new_vdb.animation_data.action = new_vdb.animation_data.action.copy()
            vis_frame = frame_at_visible(new_vdb.animation_data.action)
        
        delta = birth_frame - vis_frame
        if new_vdb and new_vdb.animation_data and new_vdb.animation_data.action:
            shift_action(new_vdb.animation_data.action, delta)
        if new_vdb and new_vdb.data and new_vdb.data.animation_data and new_vdb.data.animation_data.action:
            new_vdb.data.animation_data.action = new_vdb.data.animation_data.action.copy()
            shift_action(new_vdb.data.animation_data.action, delta)

    except Exception as e:
        import traceback
        traceback.print_exc()

# --- MODIFIED EXTRACTION LOGIC ---
def extract_instance_data(obj):
    depsgraph = bpy.context.evaluated_depsgraph_get()
    eval_obj = obj.evaluated_get(depsgraph)
    mesh = eval_obj.data
    
    unique_hits = {}
    attrs = mesh.attributes
    
    # Required attributes from your baking setup
    attr_filter = "IBulletHit"
    attr_birth = "BirthFrame"
    attr_pos = "IPosition"
    attr_rot = "IRotation"

    if all(a in attrs for a in [attr_filter, attr_birth, attr_pos, attr_rot]):
        f_data = attrs[attr_filter].data
        b_data = attrs[attr_birth].data
        p_data = attrs[attr_pos].data
        r_data = attrs[attr_rot].data
        
        print(f"Scanning realized mesh with {len(mesh.vertices)} vertices...")
        
        for i in range(len(mesh.vertices)):
            if f_data[i].value:
                birth = float(b_data[i].value)
                pos_vec = p_data[i].vector
                rot_vec = r_data[i].vector
                
                # Fingerprint to extract only one entry per complex bullet geometry
                # We use IPosition because it's identical for all verts in one instance
                key = (birth, round(pos_vec.x, 4), round(pos_vec.y, 4), round(pos_vec.z, 4))
                
                if key not in unique_hits:
                    # Construct a MatrixWorld from the IPosition and IRotation
                    mat = mathutils.Matrix.Translation(pos_vec)
                    mat @= mathutils.Euler(rot_vec).to_matrix().to_4x4()
                    
                    unique_hits[key] = (mat, birth)
                    
        print(f"Extraction complete: Found {len(unique_hits)} unique bullet hits.")
    else:
        missing = [a for a in [attr_filter, attr_birth, attr_pos, attr_rot] if a not in attrs]
        print(f"Error: Missing attributes on {obj.name}: {missing}")
        
    return list(unique_hits.values())

# --- MAIN EXECUTION ---
active_obj = bpy.context.active_object
if active_obj:
    templates = find_bullet_hit_templates()
    if not templates:
        print("Error: No valid templates found in 'BulletHits' collection.")
    else:
        # Extract (Matrix, BirthFrame) pairs
        bullet_hits = extract_instance_data(active_obj)
        
        for matrix, birth in bullet_hits:
            # Pick a random template and spawn
            template = random.choice(templates)
            copy_and_align(template, matrix, birth, active_obj.name)
            
    print("Placement script finished.")
else:
    print("Please select the ProjectileSystem_Bullets object.")
