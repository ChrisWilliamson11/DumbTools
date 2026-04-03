import bpy

def group_selected_objects_into_collections():
    for obj in bpy.context.selected_objects:
        # Create a new collection named after the object
        collection_name = obj.name
        new_collection = bpy.data.collections.new(collection_name)
        bpy.context.scene.collection.children.link(new_collection)

        # Gather the object and all its children recursively
        objects_to_move = [obj] + list(obj.children_recursive)

        for child_obj in objects_to_move:
            # Link to new collection
            new_collection.objects.link(child_obj)
            # Unlink from all other collections
            for coll in child_obj.users_collection:
                if coll != new_collection:
                    coll.objects.unlink(child_obj)

group_selected_objects_into_collections()
