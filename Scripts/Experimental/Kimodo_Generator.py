import bpy
import os
import json
import subprocess
import threading
from mathutils import Matrix

# Tracks the Windows-native server process so we can cleanly terminate it
_kimodo_win_proc = {"proc": None}

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
    # --- Backend selector ---
    use_wsl: bpy.props.BoolProperty(
        name="Use WSL Backend",
        description="Run the server inside WSL (Linux). Uncheck to use a native Windows Python venv instead",
        default=False
    )
    win_python_path: bpy.props.StringProperty(
        name="Python Executable",
        description="Path to the Python executable inside the Windows server venv",
        default=r"G:\Kimodo\kimodo\venv_server\Scripts\python.exe",
        subtype='FILE_PATH'
    )
    win_kimodo_path: bpy.props.StringProperty(
        name="Kimodo Repo Path",
        description="Root of the Kimodo repository on Windows (contains kimodo/ subfolder)",
        default=r"G:\Kimodo\kimodo",
        subtype='DIR_PATH'
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
    model_string = settings.model_name.strip() or "kimodo-soma-rp"

    def background_task_wsl():
        wsl_exe = r"C:\Windows\System32\wsl.exe"
        bash_server = (
            "cd ~/Kimodo_WSL/kimodo && "
            "source venv/bin/activate && "
            "PYTHONUNBUFFERED=1 python -u kimodo/scripts/blender_server.py"
        )
        print("Starting Kimodo API Server in WSL...")
        try:
            subprocess.run([wsl_exe, "-d", "Ubuntu", "-e", "bash", "-c", "pkill -f blender_server.py"], timeout=5)
            process = subprocess.Popen(
                [wsl_exe, "-d", "Ubuntu", "-e", "bash", "-c", bash_server],
                shell=False, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True
            )
            print(f"[Kimodo Server]: Process started, PID={process.pid}")
            for line in process.stdout:
                print("[Kimodo Server]:", line.strip())
            print(f"[Kimodo Server]: Process exited with code {process.wait()}")
        except Exception as e:
            print(f"[Kimodo Server]: FAILED TO START - {e}")

    def background_task_windows():
        python_exe = settings.win_python_path or r"G:\Kimodo\kimodo\venv_server\Scripts\python.exe"
        repo_path  = settings.win_kimodo_path  or r"G:\Kimodo\kimodo"
        server_script = os.path.join(repo_path, "kimodo", "scripts", "blender_server.py")
        print(f"Starting Kimodo API Server (Windows native)...")
        print(f"  Python : {python_exe}")
        print(f"  Script : {server_script}")
        # Kill any leftover process from a previous run
        old = _kimodo_win_proc["proc"]
        if old and old.poll() is None:
            old.terminate()
        try:
            env = os.environ.copy()
            env["PYTHONUNBUFFERED"] = "1"
            process = subprocess.Popen(
                [python_exe, "-u", server_script],
                shell=False,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True,
                env=env,
            )
            _kimodo_win_proc["proc"] = process
            print(f"[Kimodo Server]: Process started, PID={process.pid}")
            for line in process.stdout:
                print("[Kimodo Server]:", line.strip())
            print(f"[Kimodo Server]: Process exited with code {process.wait()}")
        except Exception as e:
            print(f"[Kimodo Server]: FAILED TO START - {e}")
        finally:
            _kimodo_win_proc["proc"] = None

    task = background_task_wsl if settings.use_wsl else background_task_windows
    thread = threading.Thread(target=task)
    thread.daemon = True
    thread.start()

    # Phase 2: wait for server, then pre-load the model
    def ping_load():
        import time, urllib.request, json
        print("Waiting for Kimodo server to come online...")
        for _ in range(60):
            try:
                urllib.request.urlopen("http://localhost:8055/status", timeout=2)
                print("Kimodo server is up. Sending load_model request...")
                break
            except Exception:
                time.sleep(1)
        else:
            print("Kimodo server did not come online within 60 seconds.")
            return
        try:
            data = json.dumps({"model_name": model_string}).encode('utf-8')
            req = urllib.request.Request("http://localhost:8055/load_model", data=data, headers={'Content-Type': 'application/json'})
            with urllib.request.urlopen(req, timeout=300) as resp:
                print("Model pre-loaded:", resp.read().decode())
        except Exception as e:
            print(f"Failed to pre-load model: {e}")

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
        if context.scene.kimodo_settings.use_wsl:
            subprocess.run(['wsl', '-d', 'Ubuntu', '-e', 'pkill', '-f', 'blender_server.py'])
        else:
            proc = _kimodo_win_proc.get("proc")
            if proc and proc.poll() is None:
                proc.terminate()
                _kimodo_win_proc["proc"] = None
                print("[Kimodo Server]: Windows server process terminated.")
            else:
                print("[Kimodo Server]: No running Windows server process found.")
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
            actual_seed = result.get("seed", payload.get("seed"))
            bpy.app.timers.register(
                lambda: import_generated_bvh(filepath_dir, num_samples, actual_seed),
                first_interval=0.1
            )
        except urllib.error.URLError as e:
            print(f"Server Error: {e.reason}. Please ensure the Kimodo server is started.")

    thread = threading.Thread(target=background_request)
    thread.start()

def import_generated_bvh(filepath_dir, num_samples, seed=None):
    original_obj = bpy.context.active_object
    if not original_obj or original_obj.type != 'ARMATURE':
        print("Error: Active object is not a valid Armature!")
        return None

    bvh_files = []
    motion_dir = os.path.join(filepath_dir, "motion")
    for i in range(num_samples):
        p = os.path.join(motion_dir, f"motion_{i:02d}.bvh")
        if os.path.exists(p):
            bvh_files.append(p)

    if not bvh_files:
        print("Error: No BVH files found in temp directory!")
        return None

    # Build a seed suffix for rig names so generations are reproducible.
    # e.g. "_s42" or "_sRND" if seed is unknown.
    seed_str = f"_s{seed}" if seed is not None else ""

    spread_x = 1.5  # metres between each generated copy along X

    # Read bone rolls from the source rig once so we can fix the imported BVH
    # armature's rolls to match.  Must be done in edit mode on the source rig.
    source_bone_rolls = {}
    bpy.context.view_layer.objects.active = original_obj
    bpy.ops.object.mode_set(mode='EDIT')
    for eb in original_obj.data.edit_bones:
        source_bone_rolls[eb.name] = eb.roll
    bpy.ops.object.mode_set(mode='OBJECT')

    # Find the rightmost existing generated rig so repeated runs stack correctly.
    # Match on base_name + "_Gen" prefix to avoid matching unrelated objects.
    base_name = original_obj.name
    rightmost_x = original_obj.location.x
    for obj in bpy.context.scene.objects:
        if obj.type == 'ARMATURE' and obj.name.startswith(base_name + "_Gen"):
            rightmost_x = max(rightmost_x, obj.location.x)
    start_x = rightmost_x + spread_x

    for i, bvh_path in enumerate(bvh_files):
        # Import the BVH — Blender makes a new armature object and sets it active
        bpy.ops.import_anim.bvh(
            filepath=bvh_path,
            global_scale=0.01,
            use_fps_scale=True,
            update_scene_fps=False,
            update_scene_duration=False,
        )

        imported_obj = bpy.context.active_object
        if not (imported_obj and imported_obj != original_obj
                and imported_obj.animation_data
                and imported_obj.animation_data.action):
            print(f"Warning: could not import sample {i}")
            continue

        # Copy bone rolls from the source rig to the imported BVH armature.
        # Blender's BVH importer assigns rolls heuristically from bone offsets,
        # and near-zero offset components (like the arm bones) can produce
        # inconsistent rolls between import calls.  Forcing the imported rig's
        # rolls to match the source rig ensures rotations are interpreted
        # identically when the action is later transferred to the duplicate.
        bpy.context.view_layer.objects.active = imported_obj
        bpy.ops.object.mode_set(mode='EDIT')
        for eb in imported_obj.data.edit_bones:
            if eb.name in source_bone_rolls:
                eb.roll = source_bone_rolls[eb.name]
        bpy.ops.object.mode_set(mode='OBJECT')
        bpy.context.view_layer.objects.active = original_obj

        action = imported_obj.animation_data.action
        action.name = f"Kimodo_Gen_v{i + 1}{seed_str}"
        # Capture the slot BEFORE removing imported_obj (Blender 4.4+ slotted actions).
        source_slot = None
        if hasattr(imported_obj.animation_data, "action_slot"):
            source_slot = imported_obj.animation_data.action_slot
        # Give the action a fake user so it survives when we delete imported_obj.
        action.use_fake_user = True

        # Duplicate the ORIGINAL rig so it keeps all its mesh children,
        # bone groups, etc., then assign the generated action directly.
        dup = original_obj.copy()
        dup.animation_data_clear()
        dup.animation_data_create()
        dup.name = f"{base_name}_Gen{i + 1}{seed_str}"
        bpy.context.collection.objects.link(dup)

        # Assign action + slot. In Blender 4.4+ the slot must be set explicitly
        # or the action appears assigned but no keyframes play.
        dup.animation_data.action = action
        if source_slot is not None and hasattr(dup.animation_data, "action_slot"):
            dup.animation_data.action_slot = source_slot
        elif hasattr(dup.animation_data, "action_suitable_slots"):
            suitable = dup.animation_data.action_suitable_slots
            if suitable:
                dup.animation_data.action_slot = suitable[0]
        # Now dup holds a real user reference — clear the fake user.
        action.use_fake_user = False

        # Store generation info as custom properties (visible in
        # Properties > Object Properties > Custom Properties).
        # To reproduce: set Seed = kimodo_seed, Variations = kimodo_num_samples,
        # then generate again — variation N will be identical.
        dup["kimodo_seed"] = int(seed) if seed is not None else -1
        dup["kimodo_variation"] = i + 1
        dup["kimodo_num_samples"] = num_samples
        dup["kimodo_source"] = base_name
        print(f"  Custom props on '{dup.name}': seed={dup['kimodo_seed']} variation={dup['kimodo_variation']}/{dup['kimodo_num_samples']}")

        # Place the duplicate to the right of all previous generated rigs
        dup.location.x = start_x + i * spread_x

        # Remove the raw BVH import object — action is safely held by dup.
        bpy.data.objects.remove(imported_obj, do_unlink=True)

    # Leave the original selected and active — ready for another generation
    bpy.context.view_layer.objects.active = original_obj
    original_obj.select_set(True)
    print(f"Successfully imported {len(bvh_files)} Kimodo generation(s) [seed={seed}]. Original rig untouched.")
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

        _kimodo_repo = settings.win_kimodo_path.rstrip("\\/") if not settings.use_wsl and settings.win_kimodo_path else r"G:\Kimodo\kimodo"
        temp_dir = os.path.join(os.path.dirname(_kimodo_repo), "temp")
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
                        # Root bone keyframes always drive trajectory
                        if settings.export_root:
                            root_frames.add(fr)
                    elif bone_name is not None:
                        # All other bones (including Hips) are pose constraints
                        if settings.export_pose:
                            pose_frames.add(fr)
                            pose_frame_bones.setdefault(fr, set()).add(bone_name)

        # Fallback: only fire if at least one export type is enabled AND no frames
        # were found. Do NOT send a current-frame constraint when export is off.
        if not root_frames and not pose_frames:
            if settings.export_root or settings.export_pose:
                fr = int(context.scene.frame_current)
                if settings.export_root:
                    root_frames.add(fr)
                if settings.export_pose:
                    pose_frames.add(fr)

        all_frames = sorted(root_frames | pose_frames)
        min_frame = min(all_frames) if all_frames else 0

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

        # ------------------------------------------------------------------ #
        # Coordinate system note
        # ------------------------------------------------------------------ #
        # pb.matrix  — armature-local space.  Because the SOMA skeleton was
        # imported from a Y-up BVH, armature-local IS already Kimodo's Y-up
        # space (X=lateral, Y=up, Z=fwd/back).  The Rx(+90°) the BVH importer
        # applies lives only on obj.matrix_world, not on pb.matrix.
        #
        # For global rotations we strip the BVH rest-pose offset so that a
        # T-pose produces identity matrices, matching Kimodo's expectation:
        #   R_kimodo = inv(pb.bone.matrix_local.to_3x3()) @ pb.matrix.to_3x3()
        #
        # Positions come straight from pb.matrix.translation — already metres,
        # already Y-up.  No coordinate swap needed.
        # ------------------------------------------------------------------ #

        for frame in all_frames:
            context.scene.frame_set(frame)
            kimodo_frame = int(round(frame - min_frame))

            # Compute global rotations and positions for every bone once per frame.
            # Used by both root2d and fullbody/end-effector constraints.
            kimodo_global_rots = {}
            kimodo_global_pos  = {}
            # Coordinate change: world Z-up → Kimodo Y-up
            # Kimodo[X,Y,Z] = World[X, Z, -Y]
            # As a 3x3 matrix: R_conv @ v_world = v_kimodo
            R_conv = mathutils.Matrix(((1,0,0),(0,0,1),(0,-1,0)))
            R_conv_inv = R_conv.transposed()  # orthogonal so inv = transpose
            obj_mat3 = obj.matrix_world.to_3x3()
            for pb in obj.pose.bones:
                # Position: world space then convert to Kimodo Y-up
                w_pos = (obj.matrix_world @ pb.matrix).translation
                kimodo_global_pos[pb.name] = mathutils.Vector((w_pos.x, w_pos.z, -w_pos.y))
                # Rotation: express world-space rotation in Kimodo's Y-up frame.
                # R_world = obj rotation * armature-local rotation
                # R_kimodo = R_conv @ R_world @ R_conv^T
                # Then strip rest-pose (also expressed in Kimodo frame) so T-pose → identity.
                R_world = obj_mat3 @ pb.matrix.to_3x3()
                R_rest_world = obj_mat3 @ pb.bone.matrix_local.to_3x3()
                R_kimodo = R_conv @ R_world @ R_conv_inv
                R_rest_kimodo = R_conv @ R_rest_world @ R_conv_inv
                kimodo_global_rots[pb.name] = (R_rest_kimodo.inverted() @ R_kimodo).normalized()

            # Root bone is the armature root, so pb.matrix is always identity in
            # armature-local space.  We must read from WORLD space (Z-up) and
            # convert to Kimodo Y-up:  Kimodo[X,Y,Z] = World[X, Z, -Y]
            # smooth_root_2d = [Kimodo_X, Kimodo_Z] = [World_X, -World_Y]
            if settings.export_root and frame in root_frames:
                root_pb = obj.pose.bones.get(ROOT_BONE)
                if root_pb is not None:
                    # World-space 4x4 of the pose bone
                    world_mat = obj.matrix_world @ root_pb.matrix
                    world_pos = world_mat.translation
                    # Convert world Z-up → Kimodo Y-up for the ground plane
                    # World X → Kimodo X,  World -Y → Kimodo Z
                    root_indices.append(kimodo_frame)
                    smooth_root_2d.append([world_pos.x, -world_pos.y])
                    # Heading: the Root bone's local X axis in world space is the
                    # character's forward direction (confirmed by rest-pose check:
                    # unrotated Root has world X=[1,0,0] which matches Kimodo's
                    # rest-pose heading [1,0]).
                    # Convert world Z-up -> Kimodo Y-up: Kimodo_X=World_X, Kimodo_Z=-World_Y
                    world_rot = world_mat.to_3x3()
                    fwd_world = world_rot @ mathutils.Vector((1.0, 0.0, 0.0))
                    global_root_heading.append([fwd_world.x, fwd_world.y])

            # --- Pose (fullbody / end-effector) ---
            if settings.export_pose and frame in pose_frames:
                pose_indices.append(kimodo_frame)
                frame_rot_list = []
                frame_pos_list = []
                for j_name in joint_order:   # joint_order = 77 SOMA joints, Hips first
                    R = kimodo_global_rots.get(j_name)
                    P = kimodo_global_pos.get(j_name)
                    if R is not None and P is not None:
                        frame_rot_list.append([list(R[0]), list(R[1]), list(R[2])])
                        frame_pos_list.append([P.x, P.y, P.z])
                    else:
                        frame_rot_list.append([[1,0,0],[0,1,0],[0,0,1]])
                        frame_pos_list.append([0.0, 0.0, 0.0])
                global_joints_rot_all.append(frame_rot_list)
                global_joints_pos_all.append(frame_pos_list)

        if settings.export_pose and pose_frames:
            if settings.pose_mode == "end_effector":
                VALID_EE = {"LeftFoot", "RightFoot", "LeftHand", "RightHand", "Hips"}
                j_names = sorted(b for b in all_keyed_bones if b in VALID_EE)
                if not j_names:
                    self.report({'WARNING'}, f"End-Effector: none of the keyed bones are valid. Valid: {sorted(VALID_EE)}")
                    return {'CANCELLED'}
                constraints_data.append({
                    "type": "end-effector",
                    "frame_indices": pose_indices,
                    "global_joints_rot": global_joints_rot_all,
                    "global_joints_pos": global_joints_pos_all,
                    "joint_names": j_names,
                })
            else:
                constraints_data.append({
                    "type": "fullbody",
                    "frame_indices": pose_indices,
                    "global_joints_rot": global_joints_rot_all,
                    "global_joints_pos": global_joints_pos_all,
                })

        if settings.export_root and root_frames:
            constraints_data.append({
                "type": "root2d",
                "frame_indices": root_indices,
                "smooth_root_2d": smooth_root_2d,
                "global_root_heading": global_root_heading,
            })

        context.scene.frame_set(original_frame)


        # Prepare Generation Payload for API Server
        # All frame counts and constraint indices must be in Kimodo's time base (30 fps).
        # Convert from scene FPS using: kimodo_frame = round(blender_frame * KIMODO_FPS / scene_fps)
        KIMODO_FPS = 30.0
        scene_fps = context.scene.render.fps / context.scene.render.fps_base
        fps_ratio = KIMODO_FPS / scene_fps

        def to_kimodo_frames(blender_frames):
            """Convert a blender frame count to Kimodo frame count."""
            return max(1, round(blender_frames * fps_ratio))

        # Re-scale all constraint frame indices that were recorded in Blender frames
        def rescale_indices(indices):
            return [round(i * fps_ratio) for i in indices]

        if constraints_data:
            for c in constraints_data:
                c["frame_indices"] = rescale_indices(c["frame_indices"])

        dist = context.scene.frame_end - context.scene.frame_start

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
                dur_list.append(to_kimodo_frames(d_frames))
        else:
            texts.append(settings.prompt)
            dur_list.append(to_kimodo_frames(dist))

        payload = {
            "model_name": context.scene.kimodo_settings.model_name.strip() or "kimodo-soma-rp",
            "prompts": texts,
            "num_frames": dur_list,
            "num_samples": settings.num_samples,
            "diffusion_steps": settings.diffusion_steps,
            "seed": settings.seed if settings.seed >= 0 else None,
            "cfg_weight": [settings.cfg_weight, 2.0],
            "cfg_type": "separated",
            "out_dir": os.path.join(temp_dir, "motion").replace("\\", "/") if settings.use_wsl else os.path.join(temp_dir, "motion"),
            "constraints": constraints_data
        }

        # Trigger background HTTP hit
        run_kimodo_generation(temp_dir, context.scene, payload)

        self.report({'INFO'}, "Constraints sent to API Server. Generating...")
        return {'FINISHED'}

class DUMBTOOLS_OT_load_seed_from_selected(bpy.types.Operator):
    bl_idname = "dumbtools.load_kimodo_seed"
    bl_label = "Load Seed from Selected"
    bl_description = (
        "Read kimodo_seed and kimodo_num_samples from the selected generated "
        "armature and populate the Seed and Variations fields. "
        "Generate again with the same settings to reproduce all variations."
    )

    def execute(self, context):
        obj = context.active_object
        if not obj or obj.type != 'ARMATURE':
            self.report({'ERROR'}, "Select a generated Kimodo armature first.")
            return {'CANCELLED'}
        if "kimodo_seed" not in obj:
            self.report({'ERROR'}, f"'{obj.name}' has no kimodo_seed property. Is it a Kimodo generation?")
            return {'CANCELLED'}

        settings = context.scene.kimodo_settings
        seed = obj["kimodo_seed"]
        num_samples = obj.get("kimodo_num_samples", 1)
        variation = obj.get("kimodo_variation", "?")

        settings.seed = int(seed)
        settings.num_samples = int(num_samples)

        self.report(
            {'INFO'},
            f"Loaded seed {seed}, {num_samples} variation(s) from '{obj.name}' "
            f"(was variation {variation}/{num_samples}). "
            f"Generate again to reproduce all {num_samples} variation(s)."
        )
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

        # Backend selector
        box = layout.box()
        box.label(text="Backend", icon='PREFERENCES')
        box.prop(settings, "use_wsl")
        if not settings.use_wsl:
            box.prop(settings, "win_python_path")
            box.prop(settings, "win_kimodo_path")
        layout.separator()

        layout.prop(settings, "model_name")
        layout.prop(settings, "prompt")
        layout.prop(settings, "use_markers")
        layout.separator()
        row = layout.row(align=True)
        row.prop(settings, "seed")
        row.operator(DUMBTOOLS_OT_load_seed_from_selected.bl_idname, text="", icon='EYEDROPPER')
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
    bpy.utils.register_class(DUMBTOOLS_OT_load_seed_from_selected)
    bpy.utils.register_class(DUMBTOOLS_PT_kimodo_panel)

def unregister():
    bpy.utils.unregister_class(DUMBTOOLS_PT_kimodo_panel)
    bpy.utils.unregister_class(DUMBTOOLS_OT_load_seed_from_selected)
    bpy.utils.unregister_class(DUMBTOOLS_OT_generate_motion_from_pose)
    bpy.utils.unregister_class(DUMBTOOLS_OT_generate_soma_skeleton)
    bpy.utils.unregister_class(DUMBTOOLS_OT_kill_kimodo_server)
    bpy.utils.unregister_class(DUMBTOOLS_OT_start_kimodo_server)
    del bpy.types.Scene.kimodo_settings
register()
