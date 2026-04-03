# Tooltip: Select a single collection and run this script to save it as a new .blend file and link it back into the original scene. The original collection will be deleted. This can drastically reduce the file size of your scene.
import bpy
import os

def save_and_link_collection():
    # Check if there is an active object
    if bpy.context.active_object:
        # Ensure we're in object mode
        bpy.ops.object.mode_set(mode='OBJECT')

    # Get the path where the .blend file is located
    blend_file_path = bpy.data.filepath
    if not blend_file_path:
        raise Exception("The Blender file needs to be saved before running this script.")
    
    blend_file_directory = os.path.dirname(blend_file_path)

    # Get the active collection
    active_collection = bpy.context.view_layer.active_layer_collection.collection
    active_collection_name = active_collection.name

    # Check if the active collection is not the master collection
    if active_collection == bpy.context.scene.collection:
        raise Exception("The active collection is the master collection. Please select a non-master collection.")

    # Identify the parent collection
    parent_collection = None
    for col in bpy.data.collections:
        if active_collection.name in col.children:
            parent_collection = col
            break

    # Set the path for the new .blend file
    new_blend_file_path = os.path.join(blend_file_directory, f"{active_collection_name}.blend")

    # Set a fake user for the collection to prevent it from being deleted
    active_collection.use_fake_user = True
    
    # Save the active collection to the new .blend file
    bpy.data.libraries.write(new_blend_file_path, {active_collection})

    active_collection.use_fake_user = False
    
    # Unlink the original collection from its parent collection
    if parent_collection:
        parent_collection.children.unlink(active_collection)
    else:
        bpy.context.scene.collection.children.unlink(active_collection)

    # Delete the original collection
    bpy.data.collections.remove(active_collection)

    # Link the collection back into the original scene from the new .blend file
    with bpy.data.libraries.load(new_blend_file_path, link=True) as (data_from, data_to):
        data_to.collections.append(active_collection_name)

    # Link the new collection to its original parent collection
    new_linked_collection = bpy.data.collections.get(active_collection_name)
    if new_linked_collection:
        if parent_collection:
            parent_collection.children.link(new_linked_collection)
        else:
            bpy.context.scene.collection.children.link(new_linked_collection)
    else:
        raise Exception("Failed to link the new collection.")
    
    # Purge orphan data blocks before saving the final file
    bpy.ops.outliner.orphans_purge()
    
    print(f"Collection '{active_collection_name}' has been saved as '{new_blend_file_path}' and linked.")

# Run the function
save_and_link_collection()
