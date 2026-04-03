# Tooltip: This script will match the mesh islands of the selected object to the mesh islands of the 'Shards' collection.

import bpy
import random

def match_mesh_islands():
    # Get the selected object
    selected_obj = bpy.context.active_object
    if not selected_obj or selected_obj.type != 'MESH':
        print("Please select a mesh object.")
        return

    # Get the 'Shards' collection
    shards_collection = bpy.data.collections.get('Shards')
    if not shards_collection:
        print("'Shards' collection not found.")
        return

    # Count faces in the selected object
    total_faces = len(selected_obj.data.polygons)

    # Count faces in each shard object
    shard_face_counts = []
    for shard in shards_collection.objects:
        if shard.type == 'MESH':
            shard_face_counts.append((shard.name, len(shard.data.polygons)))

    # Check if face counts match
    if sum(count for _, count in shard_face_counts) != total_faces:
        print("Face counts don't match. Aborting.")
        return

    # Enter edit mode
    bpy.ops.object.mode_set(mode='EDIT')

    for shard_name, face_count in shard_face_counts:
        # Deselect all faces
        bpy.ops.mesh.select_all(action='DESELECT')
        
        # Select random faces
        bpy.ops.object.mode_set(mode='OBJECT')
        face_indices = random.sample(range(len(selected_obj.data.polygons)), face_count)
        for index in face_indices:
            selected_obj.data.polygons[index].select = True
        bpy.ops.object.mode_set(mode='EDIT')

        # Separate selected faces
        bpy.ops.mesh.separate(type='SELECTED')
        
        # Rename the new object
        new_obj = bpy.context.selected_objects[-1]
        new_obj.name = f"{shard_name}_UV"

        # Switch back to the original object
        bpy.ops.object.mode_set(mode='OBJECT')
        bpy.context.view_layer.objects.active = selected_obj
        bpy.ops.object.mode_set(mode='EDIT')

    # Exit edit mode
    bpy.ops.object.mode_set(mode='OBJECT')

    print("Mesh islands matched and separated successfully.")

# Run the function
match_mesh_islands()
