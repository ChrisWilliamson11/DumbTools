# Tooltip: Looks for objects with the same name as your selected (aside from the .001 .002 prefix) and links the object data to the selected
import bpy

# Iterate over all selected objects in the scene
for obj in bpy.context.selected_objects:
    # Ensure we're working with a mesh object
    if obj.type == 'MESH':
        # The base name to look for duplicates
        base_name = obj.name.rsplit('.', 1)[0]
        # Iterate over all objects in the scene to find duplicates
        for dup_obj in bpy.data.objects:
            # Skip if it's the original object
            if dup_obj == obj:
                continue
            # Check if this object's name starts with the base name and has a numeric suffix
            if dup_obj.name.startswith(base_name) and dup_obj.name[len(base_name):].startswith('.'):
                try:
                    # Ensure it's a mesh object
                    if dup_obj.type == 'MESH':
                        # Link the duplicate's mesh data to the original object's mesh data
                        dup_obj.data = obj.data
                except Exception as e:
                    print(f"Error linking object {dup_obj.name} to {obj.name}: {e}")

print("Mesh data linking complete.")
