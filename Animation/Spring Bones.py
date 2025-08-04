# Tooltip:  Creates spring animation for selected bones in an armature.

import bpy
import math

def calculate_spring_motion(rotation, velocity, target_rotation, mass, stiffness, damping, frame_duration):
    force = -stiffness * (rotation - target_rotation) - damping * velocity
    acceleration = force / mass
    new_velocity = velocity + acceleration * frame_duration
    new_rotation = rotation + new_velocity * frame_duration
    return new_rotation, new_velocity

def replace_with_spring_keyframes(action, bone_name, mass, stiffness, damping, settle_frames):
    bone_path = f'pose.bones["{bone_name}"].rotation_euler'
    
    for i in range(3):  # Apply to all three axes: X (0), Y (1), Z (2)
        fcurve = action.fcurves.find(data_path=bone_path, index=i)
        
        if not fcurve:
            continue

        frame_duration = 1 / bpy.context.scene.render.fps
        spring_vals = []

        # Get the existing keyframes
        keyframes = sorted([kp.co[0] for kp in fcurve.keyframe_points])
        if not keyframes:
            continue

        # Calculate initial velocities based on the keyframes
        velocities = []
        for i in range(1, len(fcurve.keyframe_points)):
            prev_frame, prev_value = fcurve.keyframe_points[i-1].co
            curr_frame, curr_value = fcurve.keyframe_points[i].co
            velocity = (curr_value - prev_value) / ((curr_frame - prev_frame) * frame_duration)
            velocities.append(velocity)
        
        # Apply spring dynamics starting from the first frame
        current_rotation = fcurve.keyframe_points[0].co[1]
        velocity = velocities[0] if velocities else 0

        frame_start = int(keyframes[0])
        frame_end = int(keyframes[-1])
        for frame in range(frame_start, frame_end):
            target_rotation = fcurve.evaluate(frame)
            new_rotation, velocity = calculate_spring_motion(
                current_rotation, velocity, target_rotation, mass, stiffness, damping, frame_duration)
            spring_vals.append((frame, new_rotation))
            current_rotation = new_rotation

        # Allow for settling beyond the keyframes
        for frame in range(frame_end, frame_end + settle_frames):
            new_rotation, velocity = calculate_spring_motion(
                current_rotation, velocity, 0, mass, stiffness, damping, frame_duration)
            spring_vals.append((frame, new_rotation))
            current_rotation = new_rotation

        # Replace all keyframes in the fcurve with spring values
        fcurve.keyframe_points.clear()
        for frame, rotation in spring_vals:
            fcurve.keyframe_points.insert(frame, rotation, options={'FAST'})

def create_animation(armature, mass, stiffness, damping, settle_frames):
    action = armature.animation_data.action
    if not action:
        print(f"No action found for {armature.name}")
        return
    
    selected_bones = [bone for bone in armature.data.bones if bone.select]
    print(f"Selected bones: {[bone.name for bone in selected_bones]}")
    
    for bone in selected_bones:
        print(f"Processing bone: {bone.name}")
        replace_with_spring_keyframes(action, bone.name, mass, stiffness, damping, settle_frames)

class OBJECT_OT_CreateSpringAnimationOperator(bpy.types.Operator):
    bl_idname = "object.create_spring_animation_operator"
    bl_label = "Create Spring Animation"
    bl_options = {'REGISTER', 'UNDO'}

    mass: bpy.props.FloatProperty(name="Mass", default=1.0, min=0.001, max=50.0)
    stiffness: bpy.props.FloatProperty(name="Stiffness", default=1.0, min=0.1, max=50.0)
    damping: bpy.props.FloatProperty(name="Damping", default=0.2, min=0.0, max=50.0)
    settle_frames: bpy.props.IntProperty(name="Settle Frames", default=30, min=1, max=2000)

    def execute(self, context):
        selected_armatures = [obj for obj in context.selected_objects if obj.type == 'ARMATURE']
        
        if not selected_armatures:
            self.report({'ERROR'}, "No armature selected")
            return {'CANCELLED'}
        
        for armature in selected_armatures:
            create_animation(armature, self.mass, self.stiffness, self.damping, self.settle_frames)
        
        return {'FINISHED'}

    def invoke(self, context, event):
        return context.window_manager.invoke_props_dialog(self)

def register():
    bpy.utils.register_class(OBJECT_OT_CreateSpringAnimationOperator)

def unregister():
    bpy.utils.unregister_class(OBJECT_OT_CreateSpringAnimationOperator)


register()
# Automatically run the operator after registering
bpy.ops.object.create_spring_animation_operator('INVOKE_DEFAULT')
