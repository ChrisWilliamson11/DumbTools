# Tooltip:  Clamp animation on selected bones to the min & max values of the rotation constraint
import bpy
import math

# Ensure an armature is in pose mode
if bpy.context.object and bpy.context.object.type == "ARMATURE" and bpy.context.object.mode == "POSE":
    armature = bpy.context.object
    action = armature.animation_data.action if armature.animation_data else None

    if action:
        # Process all selected bones
        for bone in bpy.context.selected_pose_bones:
            # Check for the "Limit Rotation" constraint
            limit_rot = next((c for c in bone.constraints if c.type == "LIMIT_ROTATION"), None)
            
            if limit_rot:
                # Iterate through each f-curve of the bone
                for fcurve in action.fcurves:
                    if fcurve.data_path == f'pose.bones["{bone.name}"].rotation_euler':
                        for keyframe in fcurve.keyframe_points:
                            # Clamp the values based on the axis if the axis is clamped
                            if fcurve.array_index == 0 and limit_rot.use_limit_x:  # X rotation
                                keyframe.co[1] = max(min(keyframe.co[1], limit_rot.max_x), limit_rot.min_x)
                            elif fcurve.array_index == 1 and limit_rot.use_limit_y:  # Y rotation
                                keyframe.co[1] = max(min(keyframe.co[1], limit_rot.max_y), limit_rot.min_y)
                            elif fcurve.array_index == 2 and limit_rot.use_limit_z:  # Z rotation
                                keyframe.co[1] = max(min(keyframe.co[1], limit_rot.max_z), limit_rot.min_z)
                        fcurve.update()  # Update the f-curve after modifying keyframes
