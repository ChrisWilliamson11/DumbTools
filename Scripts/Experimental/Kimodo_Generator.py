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
        description="Text prompt for motion generation",
        default="A person waving their hand"
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
        name="Skeletal Posing",
        description="Export the animated dummy skeleton as full-body keyframe constraints",
        default=True
    )
    export_root: bpy.props.BoolProperty(
        name="Root Trajectory",
        description="Export the animated 'Kimodo_Trajectory' Empty as continuous 2D plane constraints",
        default=True
    )

class DUMBTOOLS_OT_create_kimodo_trajectory(bpy.types.Operator):
    """Generate an animatable Empty tracking root trajectory dynamically"""
    bl_idname = "dumbtools.create_kimodo_trajectory"
    bl_label = "Create Trajectory Control"

    def execute(self, context):
        if "Kimodo_Trajectory" in bpy.data.objects:
            self.report({'WARNING'}, "Trajectory control already exists!")
            return {'CANCELLED'}
        bpy.ops.object.empty_add(type='CIRCLE', radius=1.0, align='WORLD', location=(0, 0, 0))
        tracker = context.active_object
        tracker.name = "Kimodo_Trajectory"
        self.report({'INFO'}, "Created Trajectory Tracking Empty!")
        return {'FINISHED'}

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
    # This runs the WSL command in a separate thread so Blender does not freeze indefinitely
    wsl_cmd = (
        'wsl -d Ubuntu -e bash -c "cd ~/Kimodo_WSL/kimodo && '
        'source venv/bin/activate && '
        'kimodo_gen --input_folder /mnt/g/Kimodo/temp --output /mnt/g/Kimodo/temp/motion --bvh --bvh_standard_tpose"'
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
        
        # Discover universal start frame anchor to sync pose and trajectory timelines
        min_frame = 99999999
        keyframes = set()
        if settings.export_pose and obj.animation_data and obj.animation_data.action:
            for fcurve in iter_fcurves(obj.animation_data.action):
                for kp in fcurve.keyframe_points:
                    fr = int(kp.co[0])
                    keyframes.add(fr)
                    min_frame = min(min_frame, fr)
                    
        tracker = bpy.data.objects.get("Kimodo_Trajectory")
        traj_keyframes = set()
        if settings.export_root and tracker and tracker.animation_data and tracker.animation_data.action:
            for fcurve in iter_fcurves(tracker.animation_data.action):
                for kp in fcurve.keyframe_points:
                    fr = int(kp.co[0])
                    traj_keyframes.add(fr)
                    min_frame = min(min_frame, fr)
                    
        if min_frame == 99999999:
            min_frame = context.scene.frame_start

        original_frame = context.scene.frame_current

        constraints_data = []

        # 1. Process Skeleton Pose Constraints
        if settings.export_pose and keyframes:
            keyframes = sorted(list(keyframes))
            local_joints_rot_all = []
            root_positions_all = []
            pose_indices = []

            for frame in keyframes:
                context.scene.frame_set(frame)
                
                time_sec = (frame - min_frame) / scene_fps
                kimodo_frame = int(round(time_sec * 30.0))
                pose_indices.append(kimodo_frame)
                
                frame_rot_list = []
                for j_name in joint_order:
                    if j_name in obj.pose.bones:
                        pb = obj.pose.bones[j_name]
                        quat = pb.matrix_basis.to_quaternion()
                        frame_rot_list.append([quat.w, quat.x, quat.y, quat.z])
                    else:
                        frame_rot_list.append([1.0, 0.0, 0.0, 0.0])
                local_joints_rot_all.append(frame_rot_list)
                
                if "Hips" in obj.pose.bones:
                    orig = obj.pose.bones["Hips"].matrix.translation
                    root_positions_all.append([orig.x, orig.y, orig.z])
                else:
                    root_positions_all.append([0.0, 0.0, 0.0])
                    
            constraints_data.append({
                "type": "full_body",
                "frame_indices": pose_indices,
                "local_joints_rot": local_joints_rot_all,
                "root_positions": root_positions_all
            })

        # 2. Process Root 2D Trajectory Constraints
        if settings.export_root and traj_keyframes:
            import math
            traj_keyframes = sorted(list(traj_keyframes))
            root_indices = []
            smooth_root_2d = []
            global_root_heading = []

            for frame in traj_keyframes:
                context.scene.frame_set(frame)
                
                time_sec = (frame - min_frame) / scene_fps
                kimodo_frame = int(round(time_sec * 30.0))
                root_indices.append(kimodo_frame)
                
                loc = tracker.location
                smooth_root_2d.append([loc.x, loc.y]) # Blender X, Y correspond natively to ground plane mapping
                
                rot_z = tracker.rotation_euler.z 
                global_root_heading.append([math.cos(rot_z), math.sin(rot_z)])
                
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
            
        # Calculate duration based on scene length
        fps = context.scene.render.fps / context.scene.render.fps_base
        total_frames = context.scene.frame_end - context.scene.frame_start + 1
        calculated_duration = total_frames / fps
        
        # Write meta.json
        meta_data = {
            "num_samples": settings.num_samples,
            "diffusion_steps": settings.diffusion_steps,
            "seed": settings.seed if settings.seed >= 0 else None,
            "text": settings.prompt,
            "duration": str(calculated_duration),
            "cfg": {
                "enabled": True,
                "text_weight": settings.cfg_weight,
                "constraint_weight": 2.0
            }
        }
        with open(os.path.join(temp_dir, "meta.json"), 'w') as f:
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
        layout.operator(DUMBTOOLS_OT_create_kimodo_trajectory.bl_idname)
        
        layout.separator()
        layout.prop(settings, "export_pose")
        layout.prop(settings, "export_root")
        
        layout.separator()
        layout.prop(settings, "prompt")
        layout.prop(settings, "seed")
        layout.prop(settings, "num_samples")
        layout.prop(settings, "diffusion_steps")
        layout.prop(settings, "cfg_weight")
        layout.prop(settings, "transition_frames")
        
        layout.separator()
        layout.operator(DUMBTOOLS_OT_generate_motion_from_pose.bl_idname, icon='PLAY', text="Export & Generate Motion")

def register():
    bpy.utils.register_class(KimodoSettings)
    bpy.types.Scene.kimodo_settings = bpy.props.PointerProperty(type=KimodoSettings)
    bpy.utils.register_class(DUMBTOOLS_OT_generate_soma_skeleton)
    bpy.utils.register_class(DUMBTOOLS_OT_create_kimodo_trajectory)
    bpy.utils.register_class(DUMBTOOLS_OT_generate_motion_from_pose)
    bpy.utils.register_class(DUMBTOOLS_PT_kimodo_panel)

def unregister():
    bpy.utils.unregister_class(DUMBTOOLS_PT_kimodo_panel)
    bpy.utils.unregister_class(DUMBTOOLS_OT_generate_motion_from_pose)
    bpy.utils.unregister_class(DUMBTOOLS_OT_create_kimodo_trajectory)
    bpy.utils.unregister_class(DUMBTOOLS_OT_generate_soma_skeleton)
    del bpy.types.Scene.kimodo_settings
register()
