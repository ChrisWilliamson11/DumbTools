# Tooltip: Select objects where 90% of face normals point upward (within 5 degrees)

import bpy
import bmesh
from mathutils import Vector
import math

def main():
    # Configuration variables
    upward_threshold_percentage = 0.9  # 90% of faces must point upward
    angle_tolerance_degrees = 5.0      # Within 5 degrees of straight up

    # Convert angle tolerance to radians
    angle_tolerance_rad = math.radians(angle_tolerance_degrees)

    # Define the "up" direction in world space
    up_vector = Vector((0, 0, 1))

    # Get currently selected objects
    selected_objects = bpy.context.selected_objects.copy()

    # List to store objects that meet the criteria
    floor_objects = []

    # Process each selected object
    for obj in selected_objects:
        if obj.type != 'MESH':
            continue

        # Calculate the percentage of upward-facing faces
        upward_percentage = calculate_upward_face_percentage(obj, up_vector, angle_tolerance_rad)

        # Check if this object meets the floor criteria
        if upward_percentage >= upward_threshold_percentage:
            floor_objects.append(obj)
            print(f"'{obj.name}': {upward_percentage:.1%} upward faces - SELECTED")
        else:
            print(f"'{obj.name}': {upward_percentage:.1%} upward faces - not selected")

    # Update selection to only include floor objects
    bpy.ops.object.select_all(action='DESELECT')
    for obj in floor_objects:
        obj.select_set(True)

    # Set active object if we have any floor objects
    if floor_objects:
        bpy.context.view_layer.objects.active = floor_objects[0]
        print(f"\nSelected {len(floor_objects)} floor object(s) out of "
              f"{len(selected_objects)} total objects.")
    else:
        print(f"\nNo objects met the floor criteria "
              f"(>={upward_threshold_percentage:.0%} upward faces).")

def calculate_upward_face_percentage(obj, up_vector, angle_tolerance):
    """
    Calculate the percentage of faces that have normals pointing upward
    within the specified angle tolerance.
    """
    # Ensure we're in object mode
    if bpy.context.active_object != obj:
        bpy.context.view_layer.objects.active = obj

    # Get the object's world matrix for transforming normals
    world_matrix = obj.matrix_world

    # Create a new bmesh instance from the mesh
    bm = bmesh.new()
    bm.from_mesh(obj.data)

    # Ensure face indices are valid
    bm.faces.ensure_lookup_table()

    # Calculate face normals if not already calculated
    bm.normal_update()
    bm.faces.ensure_lookup_table()

    total_faces = len(bm.faces)
    if total_faces == 0:
        bm.free()
        return 0.0

    upward_faces = 0

    # Check each face
    for face in bm.faces:
        # Transform the face normal to world space
        world_normal = world_matrix.to_3x3().normalized() @ face.normal
        world_normal.normalize()

        # Calculate the angle between the face normal and the up vector
        # Using dot product: cos(angle) = dot(a, b) / (|a| * |b|)
        dot_product = world_normal.dot(up_vector)

        # Clamp dot product to avoid floating point errors
        dot_product = max(-1.0, min(1.0, dot_product))

        # Calculate angle
        angle = math.acos(abs(dot_product))

        # Check if the face is pointing upward within tolerance
        if angle <= angle_tolerance:
            upward_faces += 1

    # Clean up bmesh
    bm.free()

    # Return the percentage of upward-facing faces
    return upward_faces / total_faces

main()
