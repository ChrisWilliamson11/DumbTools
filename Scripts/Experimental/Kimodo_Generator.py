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

def run_kimodo_generation(filepath_dir, scene):
    settings = scene.kimodo_settings
    model_string = settings.model_name.strip()
    if not model_string:
        model_string = "kimodo-soma-rp"
        
    wsl_cmd = (
        f'wsl -d Ubuntu -e bash -c "'
        f'cd ~/Kimodo_WSL/kimodo && '
        f'source venv/bin/activate && '
        f'kimodo_gen --input_folder /mnt/g/Kimodo/temp --output /mnt/g/Kimodo/temp/motion --bvh --bvh_standard_tpose --model {model_string}'
        f'"'
    )
    
    def background_task():
        print("Starting Kimodo Generation in WSL...")
        process = subprocess.Popen(wsl_cmd, shell=True, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)
        for line in process.stdout:
            print("[Kimodo WSL]:", line.strip())
        process.wait()
        print("Kimodo Generation completed with exit code", process.returncode)
        
        # We must explicitly read settings.num_samples inside the operator, so pass it through
        num_samples = scene.kimodo_settings.num_samples
        bpy.app.timers.register(lambda: import_generated_bvh(filepath_dir, num_samples), first_interval=0.1)

    thread = threading.Thread(target=background_task)
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
            
            # Visually mute all but the first track so the user can easily toggle / solo them to compare
            if i > 0:
                track.mute = True
                
            # Delete imported armature to keep scene clean
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

        local_joints_rot_all = []
        root_positions_all = []
        pose_indices = []
        
        root_indices = []
        smooth_root_2d = []
        global_root_heading = []

        import math, mathutils
        # The base resting state matrix for the standard Kimodo BVH format aligned back into Blender World Space
        Base_Armature_Matrix = mathutils.Matrix.Rotation(math.pi/2, 4, 'X')

        for frame in all_frames:
            context.scene.frame_set(frame)
            
            # Map Blender frame to Kimodo frame index using the same FPS as the duration calculation
            kimodo_frame = int(round(frame - min_frame))
            
            # --- Global Spatial Resolution ---
            kimodo_global_rots = {}
            for pb in obj.pose.bones:
                # Capture the explicit absolute world coordinate matrices
                M_posed_world = obj.matrix_world @ pb.matrix
                M_pure_rest_world = Base_Armature_Matrix @ pb.bone.matrix_local
                
                # Derive isolation deflection angular matrix 
                R_pose = M_posed_world.to_3x3()
                R_rest = M_pure_rest_world.to_3x3()
                R_applied = R_pose @ R_rest.inverted()
                kimodo_global_rots[pb.name] = R_applied

            # --- Trajectory Constraint Scraping ---
            # Only emit a trajectory point if Root bone was keyed on this frame.
            if settings.export_root and frame in root_frames:
                # Use Root bone world XZ position for trajectory
                if ROOT_BONE in obj.pose.bones:
                    pb_root = obj.pose.bones[ROOT_BONE]
                    root_world = obj.matrix_world @ pb_root.matrix.translation
                else:
                    # Fallback to Hips if no Root bone exists
                    pb_root = obj.pose.bones.get("Hips")
                    root_world = (obj.matrix_world @ pb_root.matrix.translation) if pb_root else mathutils.Vector((0,0,0))
                root_indices.append(kimodo_frame)
                smooth_root_2d.append([root_world.x, -root_world.y])  # Kimodo XZ = Blender X, -Y

                # Heading from Root bone forward vector
                R_root = kimodo_global_rots.get(ROOT_BONE, kimodo_global_rots.get("Hips", mathutils.Matrix.Identity(3)))
                forward = R_root @ mathutils.Vector((0.0, 1.0, 0.0))
                global_root_heading.append([forward.x, -forward.y])

            # --- Skeletal Constraint Scraping ---
            # Only lock a full-body pose on this frame if a non-Hips bone was keyed here.
            if settings.export_pose and frame in pose_frames:
                pose_indices.append(kimodo_frame)
                # Root position for this pose frame
                if "Hips" in obj.pose.bones:
                    pb = obj.pose.bones["Hips"]
                    global_orig = obj.matrix_world @ pb.matrix.translation
                    root_positions_all.append([global_orig.x, global_orig.z, -global_orig.y])
                else:
                    root_positions_all.append([0.0, 0.0, 0.0])
                frame_rot_list = []
                for j_name in joint_order:
                    if j_name in obj.pose.bones:
                        pb = obj.pose.bones[j_name]
                        R_child = kimodo_global_rots[j_name]
                        
                        # Apply parent inverse matrix isolation for pure recursive Kimodo-native angular deflections
                        if pb.parent and pb.parent.name in kimodo_global_rots:
                            R_parent = kimodo_global_rots[pb.parent.name]
                            L_child = R_parent.inverted() @ R_child
                        else:
                            L_child = R_child
                            
                        quat = L_child.to_quaternion()
                        axis = quat.axis
                        angle = quat.angle
                        # Transpose the Blender World Axis natively into the Kimodo World Axis geometry Space (Y up, -Z forward)
                        frame_rot_list.append([axis.x * angle, axis.z * angle, -axis.y * angle])
                    else:
                        frame_rot_list.append([0.0, 0.0, 0.0])
                local_joints_rot_all.append(frame_rot_list)

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
                "local_joints_rot": local_joints_rot_all,
                "root_positions": root_positions_all
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

        # Write constraints.json
        with open(os.path.join(temp_dir, "constraints.json"), 'w') as f:
            json.dump(constraints_data, f)
            
        # Write meta.json
        meta_path = os.path.join(temp_dir, "meta.json")
        dist = context.scene.frame_end - context.scene.frame_start
        scene_fps = context.scene.render.fps / context.scene.render.fps_base

        if settings.use_markers and len(context.scene.timeline_markers) > 0:
            texts = []
            dur_list = []
            markers = sorted(list(context.scene.timeline_markers), key=lambda m: m.frame)
            end_frame = context.scene.frame_end
            for i in range(len(markers)):
                m = markers[i]
                texts.append(m.name)
                next_f = markers[i+1].frame if i+1 < len(markers) else end_frame
                d_frames = max(1, next_f - m.frame)
                dur_list.append(d_frames / scene_fps)
            meta_data = {
                "texts": texts,
                "durations": dur_list,
                "num_samples": settings.num_samples,
                "diffusion_steps": settings.diffusion_steps,
                "seed": settings.seed if settings.seed >= 0 else None,
                "cfg": {"enabled": True, "text_weight": settings.cfg_weight, "constraint_weight": 2.0}
            }
        else:
            meta_data = {
                "text": settings.prompt,
                "duration": dist / scene_fps,
                "num_samples": settings.num_samples,
                "diffusion_steps": settings.diffusion_steps,
                "seed": settings.seed if settings.seed >= 0 else None,
                "cfg": {"enabled": True, "text_weight": settings.cfg_weight, "constraint_weight": 2.0}
            }

        with open(meta_path, 'w') as f:
            json.dump(meta_data, f, indent=4)

        # Trigger background WSL command
        run_kimodo_generation(temp_dir, context.scene)

        self.report({'INFO'}, "Exported constraints! Generation running in background. See terminal for output.")
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
    bpy.utils.register_class(DUMBTOOLS_OT_generate_soma_skeleton)
    bpy.utils.register_class(DUMBTOOLS_OT_generate_motion_from_pose)
    bpy.utils.register_class(DUMBTOOLS_PT_kimodo_panel)

def unregister():
    bpy.utils.unregister_class(DUMBTOOLS_PT_kimodo_panel)
    bpy.utils.unregister_class(DUMBTOOLS_OT_generate_motion_from_pose)
    bpy.utils.unregister_class(DUMBTOOLS_OT_generate_soma_skeleton)
    del bpy.types.Scene.kimodo_settings
register()
