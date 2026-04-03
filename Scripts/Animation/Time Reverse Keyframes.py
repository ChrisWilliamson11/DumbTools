# Tooltip:  This script reverse a range of selected keyframes in place

import bpy

def reverse_keyframes(obj):
    if obj.animation_data is None or obj.animation_data.action is None:
        return

    action = obj.animation_data.action
    fcurves = action.fcurves

    for fcurve in fcurves:
        # Extract keyframes that are selected
        keyframes = [kp for kp in fcurve.keyframe_points if kp.select_control_point]

        if not keyframes:
            continue

        # Calculate the range and midpoint of the keyframes
        min_frame = min(keyframes, key=lambda kp: kp.co.x).co.x
        max_frame = max(keyframes, key=lambda kp: kp.co.x).co.x
        frame_range = max_frame - min_frame

        # Store the original keyframe data
        original_keyframes = [(kp.co.x, kp.co.y, kp.handle_left_type, kp.handle_right_type,
                               kp.handle_left.x, kp.handle_left.y,
                               kp.handle_right.x, kp.handle_right.y) for kp in keyframes]

        # Sort the original keyframes by frame
        original_keyframes.sort(key=lambda x: x[0])

        # Apply the reversed frames
        for i, kp in enumerate(reversed(keyframes)):
            original_frame, value, hl_type, hr_type, hl_x, hl_y, hr_x, hr_y = original_keyframes[i]
            new_frame = min_frame + frame_range - (original_frame - min_frame)
            kp.co = (new_frame, value)
            kp.handle_left_type, kp.handle_right_type = hr_type, hl_type
            # Swap and reposition handles
            kp.handle_left.x = new_frame - (hr_x - original_frame)
            kp.handle_left.y = hr_y
            kp.handle_right.x = new_frame - (hl_x - original_frame)
            kp.handle_right.y = hl_y

# Reverse keyframes of all selected objects
for obj in bpy.context.selected_objects:
    reverse_keyframes(obj)

# Update dependencies
bpy.context.view_layer.update()
