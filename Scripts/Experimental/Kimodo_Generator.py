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
    transition_frames: bpy.props.IntProperty(
        name="Transition Frames",
        description="Number of frames to help transition",
        default=5,
        min=0, max=60
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

        # Import BVH
        bpy.ops.import_anim.bvh(filepath=bvh_path, use_fps_scale=False, update_scene_fps=False, update_scene_duration=False)
        
        # The imported armature becomes the active object
        obj = context.active_object
        if obj and obj.type == 'ARMATURE':
            obj.name = "SOMA77_Rig"
            # Set all bones to Quaternion for better interpolation and axis-angle conversion
            for pb in obj.pose.bones:
                pb.rotation_mode = 'QUATERNION'
            self.report({'INFO'}, "Successfully generated SOMA77 skeleton")
        return {'FINISHED'}

def run_kimodo_generation(filepath_dir, scene):
    # This runs the WSL command in a separate thread so Blender does not freeze indefinitely
    wsl_cmd = (
        'wsl -d Ubuntu -e bash -c "cd ~/Kimodo_WSL/kimodo && '
        'source venv/bin/activate && '
        'kimodo_gen --input_folder /mnt/g/Kimodo/temp --output /mnt/g/Kimodo/temp/motion --bvh"'
    )
    
    def background_task():
        print("Starting Kimodo Generation in WSL...")
        process = subprocess.Popen(wsl_cmd, shell=True, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)
        for line in process.stdout:
            print("[Kimodo WSL]:", line.strip())
        process.wait()
        print("Kimodo Generation completed with exit code", process.returncode)
        
        # Set a flag to trigger import in the main thread (thread-safe execution via app timer)
        bpy.app.timers.register(lambda: import_generated_bvh(filepath_dir), first_interval=0.1)

    thread = threading.Thread(target=background_task)
    thread.start()

def import_generated_bvh(filepath_dir):
    bvh_path = os.path.join(filepath_dir, "motion.bvh")
    if not os.path.exists(bvh_path):
        print(f"Error: generated BVH not found at {bvh_path}")
        return None

    # Save current active object
    original_obj = bpy.context.active_object

    # Import the BVH
    bpy.ops.import_anim.bvh(filepath=bvh_path, use_fps_scale=False, update_scene_fps=False, update_scene_duration=False)
    
    imported_obj = bpy.context.active_object
    if imported_obj and imported_obj != original_obj and imported_obj.animation_data and imported_obj.animation_data.action:
        # Copy the action
        generated_action = imported_obj.animation_data.action
        generated_action.name = "Kimodo_Generated_Action"
        
        # Apply to original
        if original_obj and original_obj.type == 'ARMATURE':
            if not original_obj.animation_data:
                original_obj.animation_data_create()
            original_obj.animation_data.action = generated_action
            
        # Delete imported armature to keep scene clean
        bpy.data.objects.remove(imported_obj, do_unlink=True)
        
        print("Successfully applied Kimodo motion to skeleton.")
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
        except Exception as e:
            self.report({'ERROR'}, f"Could not read SOMA joint order: {e}")
            return {'CANCELLED'}

        settings = context.scene.kimodo_settings

        # Find keyframes
        keyframes = set()
        if obj.animation_data and obj.animation_data.action:
            for fcurve in iter_fcurves(obj.animation_data.action):
                for kp in fcurve.keyframe_points:
                    keyframes.add(int(kp.co[0]))
        
        if not keyframes:
            # If no keyframes, just use the current frame
            keyframes.add(context.scene.frame_current)
            
        keyframes = sorted(list(keyframes))

        temp_dir = r"g:\Kimodo\temp"
        if not os.path.exists(temp_dir):
            os.makedirs(temp_dir)

        # Scrape constraints
        original_frame = context.scene.frame_current
        
        local_joints_rot_all = []
        root_positions_all = []
        frame_indices = []

        for frame in keyframes:
            context.scene.frame_set(frame)
            frame_indices.append(frame - keyframes[0]) # Normalized to 0 start
            
            frame_rot_list = []
            for j_name in joint_order:
                if j_name in obj.pose.bones:
                    pb = obj.pose.bones[j_name]
                    # matrix_basis is local transform relative to rest pose
                    quat = pb.matrix_basis.to_quaternion()
                    # Axis angle = axis * angle
                    axis = quat.axis
                    angle = quat.angle
                    frame_rot_list.append([axis.x * angle, axis.y * angle, axis.z * angle])
                else:
                    frame_rot_list.append([0.0, 0.0, 0.0])
            local_joints_rot_all.append(frame_rot_list)
            
            if "Root" in obj.pose.bones:
                # Get the translation of the root bone in the armature's local space
                orig = obj.pose.bones["Root"].matrix.translation
                # We save it directly
                root_positions_all.append([orig.x, orig.y, orig.z])
            else:
                root_positions_all.append([0.0, 0.0, 0.0])

        context.scene.frame_set(original_frame)

        # Write constraints.json
        constraints_data = [{
            "type": "fullbody",
            "frame_indices": frame_indices,
            "local_joints_rot": local_joints_rot_all,
            "root_positions": root_positions_all
        }]
        
        with open(os.path.join(temp_dir, "constraints.json"), 'w') as f:
            json.dump(constraints_data, f)
            
        # Calculate duration based on scene length
        fps = context.scene.render.fps / context.scene.render.fps_base
        total_frames = context.scene.frame_end - context.scene.frame_start + 1
        calculated_duration = total_frames / fps
        
        # Write meta.json
        meta_data = {
            "num_samples": 1,
            "diffusion_steps": 100,
            "seed": settings.seed if settings.seed >= 0 else None,
            "prompts": [
                {
                    "text": settings.prompt,
                    "duration": str(calculated_duration)
                }
            ],
            "cfg": {
                "enabled": True,
                "text_weight": 2.0,
                "constraint_weight": 2.0
            }
        }
        with open(os.path.join(temp_dir, "meta.json"), 'w') as f:
            json.dump(meta_data, f, indent=4)

        # Trigger background WSL command
        run_kimodo_generation(temp_dir, context.scene)

        self.report({'INFO'}, "Exported constraints! Generation running in background. See terminal for output.")
        return {'FINISHED'}

class VIEW3D_PT_kimodo_panel(bpy.types.Panel):
    bl_space_type = 'VIEW_3D'
    bl_region_type = 'UI'
    bl_category = 'DumbTools'
    bl_label = "Kimodo AI Motion"

    def draw(self, context):
        layout = self.layout
        settings = context.scene.kimodo_settings

        layout.operator("dumbtools.generate_soma_skeleton", icon='ARMATURE_DATA')
        
        layout.separator()
        layout.prop(settings, "prompt")
        layout.prop(settings, "seed")
        layout.prop(settings, "transition_frames")
        
        layout.separator()
        layout.operator("dumbtools.generate_kimodo_motion", icon='PLAY', text="Export & Generate Motion")

classes = (
    KimodoSettings,
    DUMBTOOLS_OT_generate_soma_skeleton,
    DUMBTOOLS_OT_generate_motion_from_pose,
    VIEW3D_PT_kimodo_panel
)

def register():
    for cls in classes:
        bpy.utils.register_class(cls)
    bpy.types.Scene.kimodo_settings = bpy.props.PointerProperty(type=KimodoSettings)

def unregister():
    for cls in reversed(classes):
        bpy.utils.unregister_class(cls)
    del bpy.types.Scene.kimodo_settings

register()
