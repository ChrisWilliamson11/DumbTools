# Tooltip:  Distributes Selected Objects Evenly

import bpy

def main():
    # Get all selected objects
    selected_objects = bpy.context.selected_objects

    # Ensure there are enough objects
    if len(selected_objects) < 3:
        raise ValueError("Please select at least three objects.")

    # Distribute objects on each axis
    for axis in range(3):
        distribute_on_axis(selected_objects, axis)

def distribute_on_axis(objects, axis):
    # Sort objects by their position on the current axis
    objects_sorted = sorted(objects, key=lambda obj: obj.location[axis])

    # Check if distribution is needed (i.e., if there is variation on this axis)
    if objects_sorted[0].location[axis] != objects_sorted[-1].location[axis]:
        # Calculate the step size for distribution
        first_obj, last_obj = objects_sorted[0], objects_sorted[-1]
        total_distance = last_obj.location[axis] - first_obj.location[axis]
        step_size = total_distance / (len(objects_sorted) - 1)

        # Distribute objects
        for index, obj in enumerate(objects_sorted):
            new_position = first_obj.location[axis] + step_size * index
            obj.location[axis] = new_position

main()
 