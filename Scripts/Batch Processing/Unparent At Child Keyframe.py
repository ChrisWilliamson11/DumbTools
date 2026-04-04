# Tooltip: Un-parent each selected object at the frame after the first position keyframe on its child object

import bpy
from mathutils import Matrix


def iter_fcurves(action):
    """
    Yields fcurves from an Action, handling both Legacy Blender and Blender 5+ Layered Animation.
    """
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


def get_first_location_keyframe_frame(obj):
    """
    Returns the frame of the earliest position keyframe on the given object,
    or None if no position keyframes exist.
    """
    if not obj.animation_data or not obj.animation_data.action:
        return None

    earliest = None
    for fc in iter_fcurves(obj.animation_data.action):
        if fc.data_path == "location":
            for kp in fc.keyframe_points:
                frame = kp.co.x
                if earliest is None or frame < earliest:
                    earliest = frame

    return earliest


def find_child_with_location_keys(parent_obj):
    """
    Returns the first direct child of parent_obj that has position keyframes,
    or None.
    """
    for child in parent_obj.children:
        if get_first_location_keyframe_frame(child) is not None:
            return child
    return None


def unparent_keep_transform(obj, frame):
    """
    At the given frame, un-parent obj while preserving its world-space transform.
    Inserts a location/rotation/scale keyframe on that frame so the pose is locked in.
    """
    scene = bpy.context.scene
    original_frame = scene.frame_current

    # Jump to the target frame so matrices are evaluated there
    scene.frame_set(frame)

    # Capture the world-space matrix at this frame
    world_matrix = obj.matrix_world.copy()

    # Clear parent
    obj.parent = None
    obj.matrix_world = world_matrix

    # Insert keyframes to lock the transform at this frame
    obj.keyframe_insert(data_path="location", frame=frame)
    obj.keyframe_insert(data_path="rotation_euler", frame=frame)
    obj.keyframe_insert(data_path="rotation_quaternion", frame=frame)
    obj.keyframe_insert(data_path="scale", frame=frame)

    # Restore the original frame
    scene.frame_set(original_frame)


def main():
    selected = list(bpy.context.selected_objects)

    if not selected:
        print("No objects selected.")
        return

    processed = 0
    skipped = 0

    for obj in selected:
        # Must have a parent
        if obj.parent is None:
            print(f"  ✗ '{obj.name}' has no parent – skipping")
            skipped += 1
            continue

        # Find the child with location keyframes
        child = find_child_with_location_keys(obj)
        if child is None:
            print(f"  ✗ '{obj.name}' has no child with position keyframes – skipping")
            skipped += 1
            continue

        first_frame = get_first_location_keyframe_frame(child)
        target_frame = int(first_frame) + 1

        print(f"  → '{obj.name}': child '{child.name}' first location key at frame {int(first_frame)}, "
              f"un-parenting at frame {target_frame}")

        unparent_keep_transform(obj, target_frame)
        processed += 1

    print(f"\n=== Done: {processed} un-parented, {skipped} skipped ===")


main()
