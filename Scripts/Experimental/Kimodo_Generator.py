import bpy
import os
import json
import subprocess
import threading
from mathutils import Matrix

def scrape_bvh_joint_names(filepath):
    names = []
    with open(filepath, 'r') as f:
        for line in f:
            stripped = line.strip()
            if stripped.startswith("ROOT ") or stripped.startswith("JOINT "):
                names.append(stripped.split()[1])
    return names

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

class KimodoSettings(bpy.types.PropertyGroup):
    prompt: bpy.props.StringProperty(
        name="Prompt",
        description="Describe the motion mathematically",
        default="A person walking forward"
    )
    use_markers: bpy.props.BoolProperty(
        name="Prompt via Timeline Markers",
        description="Use sequential Timeline Markers instead of the single global prompt",
        default=False
    )
    model_name: bpy.props.EnumProperty(
        name="Model",
        description="Kimodo model to generate with",
        items=[
            ("kimodo-soma-rp",      "SOMA – Rigplay (latest)",    "Best for complex text prompts"),
            ("kimodo-soma-rp-v1.1", "SOMA – Rigplay v1.1",        "Pinned Rigplay version 1.1"),
            ("kimodo-soma-rp-v1",   "SOMA – Rigplay v1",          "Pinned Rigplay version 1"),
            ("kimodo-soma-seed",    "SOMA – BONES-SEED (latest)", "Production mocap dataset, best for physics realism"),
            ("kimodo-soma-seed-v1.1","SOMA – BONES-SEED v1.1",    "Pinned BONES-SEED version 1.1"),
            ("kimodo-soma-seed-v1", "SOMA – BONES-SEED v1",       "Pinned BONES-SEED version 1"),
            ("kimodo-smplx-rp",     "SMPLX – Rigplay",            "SMPLX body shape model"),
            ("kimodo-g1-rp",        "G1 Robot – Rigplay",         "Unitree G1 humanoid robot"),
            ("kimodo-g1-seed",      "G1 Robot – BONES-SEED",      "Unitree G1 robot with SEED dataset"),
        ],
        default="kimodo-soma-rp"
    )
    seed: bpy.props.IntProperty(
        name="Seed",
        description="Random seed (-1 for random)",
        default=-1
    )
    num_samples: bpy.props.IntProperty(
        name="Variations",
        description="Number of separate animations to generate (Warning: takes longer)",
        default=1,
        min=1, max=10
    )
    diffusion_steps: bpy.props.IntProperty(
        name="Quality (Steps)",
        description="Number of diffusion iterations (Higher = smoother but slower)",
        default=100,
        min=20, max=500
    )
    cfg_weight: bpy.props.FloatProperty(
        name="Prompt Weight (CFG)",
        description="How strictly to follow the prompt vs motion variance",
        default=2.0,
        min=1.0, max=10.0
    )
    export_pose: bpy.props.BoolProperty(
        name="Pose Constraint",
        description="Export non-Root bone keyframes as pose constraints. Key any bones you want to constrain",
        default=True
    )
    pose_mode: bpy.props.EnumProperty(
        name="Pose Mode",
        description="How to interpret keyed non-Root bones",
        items=[
            ("fullbody",     "Full Body",              "Constrain all 77 SOMA joints (strongest, ignores which bones are actually keyed)"),
            ("end_effector", "End Effector (Keyed Bones)", "Constrain only the specific bones you keyed — rest of body is free"),
        ],
        default="fullbody"
    )
    export_root: bpy.props.BoolProperty(
        name="Root Trajectory",
        description="Export the animated Skeleton path natively as continuous 2D plane constraints",
        default=True
    )

class DUMBTOOLS_OT_generate_soma_skeleton(bpy.types.Operator):
    bl_idname = "dumbtools.generate_soma_skeleton"
    bl_label = "Generate SOMA Skeleton"
    bl_description = "Imports a blank SOMA77 rest-pose skeleton from Kimodo assets"
    bl_options = {'REGISTER', 'UNDO'}

    def execute(self, context):
        # We know the repo is in G:\Kimodo\kimodo
        bvh_path = r"g:\Kimodo\kimodo\kimodo\assets\skeletons\somaskel77\somaskel77_standard_tpose.bvh"
        if not os.path.exists(bvh_path):
            self.report({'ERROR'}, f"Cannot find SOMA template at {bvh_path}")
            return {'CANCELLED'}

        # Import BVH scaled down to meters so it matches 1.77m
        bpy.ops.import_anim.bvh(filepath=bvh_path, global_scale=0.01, use_fps_scale=False, update_scene_fps=False, update_scene_duration=False)
        
        # The imported armature becomes the active object
        obj = context.active_object
        if obj and obj.type == 'ARMATURE':
            obj.name = "SOMA77_Rig"
            self.report({'INFO'}, "Successfully generated SOMA77 skeleton")
        return {'FINISHED'}

import urllib.request
import urllib.error

def start_kimodo_server(scene):
    settings = scene.kimodo_settings
    model_string = settings.model_name.strip()
    if not model_string:
        model_string = "kimodo-soma-rp"
        
    bash_script = (
        "pkill -f blender_server.py ; "
        "cd ~/Kimodo_WSL/kimodo && "
        "source venv/bin/activate && "
        "PYTHONUNBUFFERED=1 python -u kimodo/scripts/blender_server.py"
    )
    wsl_exe = r"C:\Windows\System32\wsl.exe"
    wsl_cmd = [wsl_exe, "-d", "Ubuntu", "-e", "bash", "-c", bash_script]
    
    def background_task():
        print("Starting Kimodo API Server in WSL...")
        try:
            process = subprocess.Popen(wsl_cmd, shell=False, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)
            print(f"[Kimodo Server]: Process started, PID={process.pid}")
            for line in process.stdout:
                print("[Kimodo Server]:", line.strip())
            ret = process.wait()
            print(f"[Kimodo Server]: Process exited with code {ret}")
        except Exception as e:
            print(f"[Kimodo Server]: FAILED TO START - {e}")
        
    thread = threading.Thread(target=background_task)
    thread.daemon = True
    thread.start()
    
    # Ping to load the exact model
    def ping_load():
        import time
        import urllib.request
        import json
        for _ in range(60):
            try:
                data = json.dumps({"model_name": model_string}).encode('utf-8')
                req = urllib.request.Request("http://localhost:8055/load_model", data=data, headers={'Content-Type': 'application/json'})
                with urllib.request.urlopen(req, timeout=5) as resp:
                    print("Model Pre-loaded:", resp.read().decode())
                return
            except Exception:
                time.sleep(1)
        print("Failed to pre-load model, server took too long to start.")
        
    threading.Thread(target=ping_load).start()

class DUMBTOOLS_OT_start_kimodo_server(bpy.types.Operator):
    bl_idname = "dumbtools.start_kimodo_server"
    bl_label = "Start Kimodo Server"
    bl_description = "Starts the background Kimodo generation server in WSL for instant generation"
    
    def execute(self, context):
        start_kimodo_server(context.scene)
        self.report({'INFO'}, "Starting Kimodo API server... Check terminal.")
        return {'FINISHED'}

class DUMBTOOLS_OT_kill_kimodo_server(bpy.types.Operator):
    bl_idname = "dumbtools.kill_kimodo_server"
    bl_label = "Kill Server"
    bl_description = "Kills the running Kimodo server to free up VRAM"
    
    def execute(self, context):
        subprocess.run(['wsl', '-d', 'Ubuntu', '-e', 'pkill', '-f', 'blender_server.py'])
        self.report({'INFO'}, "Kimodo server killed.")
        return {'FINISHED'}

def run_kimodo_generation(filepath_dir, scene, payload):
    def background_request():
        print("Sending generation request to Kimodo API...")
        try:
            req = urllib.request.Request("http://localhost:8055/generate", data=json.dumps(payload).encode('utf-8'), headers={'Content-Type': 'application/json'})
            with urllib.request.urlopen(req, timeout=300) as resp:
                result = json.loads(resp.read().decode())
                print("Generation complete:", result)
                
            num_samples = scene.kimodo_settings.num_samples
            bpy.app.timers.register(lambda: import_generated_bvh(filepath_dir, num_samples), first_interval=0.1)
        except urllib.error.URLError as e:
            print(f"Server Error: {e.reason}. Please ensure the Kimodo server is started.")
            
    thread = threading.Thread(target=background_request)
    thread.start()

def import_generated_bvh(filepath_dir, num_samples):
    original_obj = bpy.context.active_object
    if not original_obj or original_obj.type != 'ARMATURE':
        print("Error: Active object is not a valid Armature!")
        return None

    if not original_obj.animation_data:
        original_obj.animation_data_create()

    # Clear active action to prevent it entirely overriding our new NLA strips
    original_obj.animation_data.action = None

    bvh_files = []
    if num_samples == 1:
        single_path = os.path.join(filepath_dir, "motion.bvh")
        if os.path.exists(single_path):
            bvh_files.append(single_path)
    else:
        motion_dir = os.path.join(filepath_dir, "motion")
        if os.path.isdir(motion_dir):
            for i in range(num_samples):
                p = os.path.join(motion_dir, f"motion_{i:02d}.bvh")
                if os.path.exists(p):
                    bvh_files.append(p)

    if not bvh_files:
        print("Error: No BVH files found in temp directory!")
        return None

    for i, bvh_path in enumerate(bvh_files):
        # Import the BVH
        bpy.ops.import_anim.bvh(filepath=bvh_path, global_scale=0.01, use_fps_scale=True, update_scene_fps=False, update_scene_duration=False)
        
        imported_obj = bpy.context.active_object
        if imported_obj and imported_obj != original_obj and imported_obj.animation_data and imported_obj.animation_data.action:
            action = imported_obj.animation_data.action
            action.name = f"Kimodo_Gen_v{i+1}"
            
            # Create an isolated NLA track for this variation
            track = original_obj.animation_data.nla_tracks.new()
            track.name = f"Kimodo Variation {i+1}"
            
            # Map the generated action into the track
            strip = track.strips.new(action.name, 1, action)
            
            # Offset imported armature along X axis to match web app behavior for multiple samples
            if num_samples > 1:
                spread_factor = 0.8
                center_idx = num_samples // 2
                x_trans = (i - center_idx) * spread_factor
                imported_obj.location.x += x_trans
                imported_obj.keyframe_insert(data_path="location", frame=1)

            # Visually mute all but the first track so the user can easily toggle / solo them to compare
            if i > 0:
                track.mute = True
                
            # Clear location on NLA strips if we want them locked, but actually Kimodo baked the root motion into the BVH.
            # Leaving as is works fine because imported_obj location offsets the whole clip.
            
            # Delete imported armature to keep scene clean (but preserve its action!)
            bpy.data.objects.remove(imported_obj, do_unlink=True)

    # Set context object back
    bpy.context.view_layer.objects.active = original_obj
    original_obj.select_set(True)
    print("Successfully applied Kimodo motion(s) to skeleton NLA.")
    return None

class DUMBTOOLS_OT_generate_motion_from_pose(bpy.types.Operator):
    bl_idname = "dumbtools.generate_kimodo_motion"
    bl_label = "Export & Generate Motion"
    bl_description = "Exports keyframes as constraints and runs Kimodo generator natively in WSL"
    bl_options = {'REGISTER', 'UNDO'}

    def execute(self, context):
        obj = context.active_object
        if not obj or obj.type != 'ARMATURE':
            self.report({'ERROR'}, "Please select the SOMA armature.")
            return {'CANCELLED'}

        # Get SOMA bone order
        bvh_path = r"g:\Kimodo\kimodo\kimodo\assets\skeletons\somaskel77\somaskel77_standard_tpose.bvh"
        try:
            joint_order = scrape_bvh_joint_names(bvh_path)
            # Blender's BVH importer adds a dummy 'Root' node. We must strip it so the array represents the exact 77 SOMA joints where Hips is index 0.
            if "Root" in joint_order:
                joint_order.remove("Root")
        except Exception as e:
            self.report({'ERROR'}, f"Could not read SOMA joint order: {e}")
            return {'CANCELLED'}

        settings = context.scene.kimodo_settings
        if not obj or obj.type != 'ARMATURE':
            self.report({'ERROR'}, "Active object is not an Armature")
            return {'CANCELLED'}

        temp_dir = r"g:\Kimodo\temp"
        if not os.path.exists(temp_dir):
            os.makedirs(temp_dir)

        scene_fps = context.scene.render.fps / context.scene.render.fps_base

        # Keyframe discovery — split by bone role:
        #   Root bone keyed → trajectory waypoint (root_frames)
        #   Any other bone keyed → pose constraint frame (pose_frames)
        #   pose_frame_bones tracks which bones are keyed per frame (for end-effector mode)
        ROOT_BONE = "Root"
        root_frames = set()
        pose_frames = set()
        pose_frame_bones = {}   # frame → set of non-Root bone names keyed on that frame

        if obj.animation_data and obj.animation_data.action:
            for fcurve in iter_fcurves(obj.animation_data.action):
                dp = fcurve.data_path
                bone_name = None
                if dp.startswith('pose.bones["'):
                    bone_name = dp.split('"')[1]
                for kp in fcurve.keyframe_points:
                    fr = int(kp.co[0])
                    if bone_name == ROOT_BONE:
                        root_frames.add(fr)
                    elif bone_name is not None:
                        pose_frames.add(fr)
                        pose_frame_bones.setdefault(fr, set()).add(bone_name)

        # Fallback: no animation → treat current frame as both root and pose
        if not root_frames and not pose_frames:
            fr = int(context.scene.frame_current)
            root_frames.add(fr)
            pose_frames.add(fr)

        all_frames = sorted(root_frames | pose_frames)
        min_frame = min(all_frames)

        # Union of all keyed bone names across all pose frames (used for end-effector mode)
        all_keyed_bones = set()
        for bones in pose_frame_bones.values():
            all_keyed_bones |= bones

        original_frame = context.scene.frame_current

        constraints_data = []

        global_joints_rot_all = []
        global_joints_pos_all = []
        pose_indices = []
        
        root_indices = []
        smooth_root_2d = []
        global_root_heading = []

        import math, mathutils
        # The base resting state matrix for the standard Kimodo BVH format aligned back into Blender World Space
        Base_Armature_Matrix = mathutils.Matrix.Rotation(math.pi/2, 4, 'X')
        
        kimodo_T_blender = mathutils.Matrix((
            (1.0, 0.0, 0.0),
            (0.0, 0.0, -1.0),
            (0.0, 1.0, 0.0)
        ))

        for frame in all_frames:
            context.scene.frame_set(frame)
            
            # Map Blender frame to Kimodo frame index using the same FPS as the duration calculation
            kimodo_frame = int(round(frame - min_frame))
            
            # --- Global Spatial Resolution ---
            kimodo_global_rots = {}
            kimodo_global_pos = {}
            for pb in obj.pose.bones:
                # Capture the explicit absolute world coordinate matrices
                M_posed_world = obj.matrix_world @ pb.matrix
                M_pure_rest_world = Base_Armature_Matrix @ pb.bone.matrix_local
                
                # Derive isolation deflection angular matrix 
                R_pose = M_posed_world.to_3x3()
                R_rest = M_pure_rest_world.to_3x3()
                R_applied = R_pose @ R_rest.inverted()
                
                # Conjugate into Kimodo Space
                R_kimodo = kimodo_T_blender @ R_applied @ kimodo_T_blender.inverted()
                kimodo_global_rots[pb.name] = R_kimodo
                
                # Position into Kimodo space
                P_blender = M_posed_world.translation
                P_kimodo = kimodo_T_blender @ P_blender
                kimodo_global_pos[pb.name] = P_kimodo

            # --- Trajectory Constraint Scraping ---
            # Only emit a trajectory point if Root bone was keyed on this frame.
            if settings.export_root and frame in root_frames:
                # Use Root bone world XZ position for trajectory
                if ROOT_BONE in obj.pose.bones:
                    pos = kimodo_global_pos[ROOT_BONE]
                else:
                    pos = kimodo_global_pos.get("Hips", mathutils.Vector((0,0,0)))
                root_indices.append(kimodo_frame)
                smooth_root_2d.append([pos.x, pos.z])

                # Heading from Root bone forward vector (which is Z in Kimodo space, wait no, Kimodo uses -Z forward)
                R_root = kimodo_global_rots.get(ROOT_BONE, kimodo_global_rots.get("Hips", mathutils.Matrix.Identity(3)))
                # Viser expects heading natively, web app uses forward vector as Z?
                forward = R_root @ mathutils.Vector((0.0, 0.0, -1.0))
                global_root_heading.append([forward.x, forward.z])

            # --- Skeletal Constraint Scraping ---
            if settings.export_pose and frame in pose_frames:
                pose_indices.append(kimodo_frame)
                frame_rot_list = []
                frame_pos_list = []
                for j_name in joint_order:
                    if j_name in obj.pose.bones:
                        R_child = kimodo_global_rots[j_name]
                        P_child = kimodo_global_pos[j_name]
                        
                        # Pack into exact flat matrices required by Kimodo
                        frame_rot_list.append([list(R_child[0]), list(R_child[1]), list(R_child[2])])
                        frame_pos_list.append([P_child.x, P_child.y, P_child.z])
                    else:
                        frame_rot_list.append([[1.0, 0.0, 0.0], [0.0, 1.0, 0.0], [0.0, 0.0, 1.0]])
                        frame_pos_list.append([0.0, 0.0, 0.0])
                
                global_joints_rot_all.append(frame_rot_list)
                global_joints_pos_all.append(frame_pos_list)

        if settings.export_pose and pose_frames:
            if settings.pose_mode == "end_effector":
                c_type = "end-effector"
                j_names = sorted(all_keyed_bones)  # union of all keyed bones across pose frames
                if not j_names:
                    self.report({'WARNING'}, "End-Effector mode but no non-Root bones were keyed!")
                    return {'CANCELLED'}
            else:
                c_type = "fullbody"

            dict_full = {
                "type": c_type,
                "frame_indices": pose_indices,
                "global_joints_rot": global_joints_rot_all,
                "global_joints_pos": global_joints_pos_all
            }
            if c_type == "end-effector":
                dict_full["joint_names"] = j_names

            constraints_data.append(dict_full)

        if settings.export_root and root_frames:
            constraints_data.append({
                "type": "root2d",
                "frame_indices": root_indices,
                "smooth_root_2d": smooth_root_2d,
                "global_root_heading": global_root_heading
            })

        context.scene.frame_set(original_frame)

        # Prepare Generation Payload for API Server
        dist = context.scene.frame_end - context.scene.frame_start
        scene_fps = context.scene.render.fps / context.scene.render.fps_base
        
        texts = []
        dur_list = []
        
        if settings.use_markers and len(context.scene.timeline_markers) > 0:
            markers = sorted(list(context.scene.timeline_markers), key=lambda m: m.frame)
            end_frame = context.scene.frame_end
            for i in range(len(markers)):
                m = markers[i]
                texts.append(m.name)
                next_f = markers[i+1].frame if i+1 < len(markers) else end_frame
                d_frames = max(1, next_f - m.frame)
                dur_list.append(int(d_frames))
        else:
            texts.append(settings.prompt)
            dur_list.append(int(dist))

        payload = {
            "model_name": context.scene.kimodo_settings.model_name.strip() or "kimodo-soma-rp",
            "prompts": texts,
            "num_frames": dur_list,
            "num_samples": settings.num_samples,
            "diffusion_steps": settings.diffusion_steps,
            "seed": settings.seed if settings.seed >= 0 else None,
            "cfg_weight": [settings.cfg_weight, 2.0],
            "cfg_type": "separated",
            "out_dir": "/mnt/g/Kimodo/temp/motion",
            "constraints": constraints_data
        }

        # Trigger background HTTP hit
        run_kimodo_generation(temp_dir, context.scene, payload)

        self.report({'INFO'}, "Constraints sent to API Server. Generating...")
        return {'FINISHED'}

class DUMBTOOLS_PT_kimodo_panel(bpy.types.Panel):
    bl_label = "Kimodo AI Motion"
    bl_idname = "DUMBTOOLS_PT_kimodo_panel"
    bl_space_type = 'VIEW_3D'
    bl_region_type = 'UI'
    bl_category = 'DumbTools'
    
    def draw(self, context):
        layout = self.layout
        settings = context.scene.kimodo_settings
        
        row = layout.row(align=True)
        row.operator(DUMBTOOLS_OT_start_kimodo_server.bl_idname, icon='PLAY')
        row.operator(DUMBTOOLS_OT_kill_kimodo_server.bl_idname, icon='CANCEL')
        layout.separator()
        
        layout.operator(DUMBTOOLS_OT_generate_soma_skeleton.bl_idname)
        
        layout.separator()
        layout.prop(settings, "model_name")
        layout.prop(settings, "prompt")
        layout.prop(settings, "use_markers")
        layout.separator()
        layout.prop(settings, "seed")
        layout.prop(settings, "num_samples")
        layout.prop(settings, "diffusion_steps")
        layout.prop(settings, "cfg_weight")
        layout.separator()
        layout.prop(settings, "export_root")
        layout.prop(settings, "export_pose")
        if settings.export_pose:
            layout.prop(settings, "pose_mode", expand=True)
        layout.separator()
        
        layout.operator(DUMBTOOLS_OT_generate_motion_from_pose.bl_idname, icon='PLAY', text="Export & Generate Motion")

def register():
    bpy.utils.register_class(KimodoSettings)
    bpy.types.Scene.kimodo_settings = bpy.props.PointerProperty(type=KimodoSettings)
    bpy.utils.register_class(DUMBTOOLS_OT_start_kimodo_server)
    bpy.utils.register_class(DUMBTOOLS_OT_kill_kimodo_server)
    bpy.utils.register_class(DUMBTOOLS_OT_generate_soma_skeleton)
    bpy.utils.register_class(DUMBTOOLS_OT_generate_motion_from_pose)
    bpy.utils.register_class(DUMBTOOLS_PT_kimodo_panel)

def unregister():
    bpy.utils.unregister_class(DUMBTOOLS_PT_kimodo_panel)
    bpy.utils.unregister_class(DUMBTOOLS_OT_generate_motion_from_pose)
    bpy.utils.unregister_class(DUMBTOOLS_OT_generate_soma_skeleton)
    bpy.utils.unregister_class(DUMBTOOLS_OT_kill_kimodo_server)
    bpy.utils.unregister_class(DUMBTOOLS_OT_start_kimodo_server)
    del bpy.types.Scene.kimodo_settings
register()
