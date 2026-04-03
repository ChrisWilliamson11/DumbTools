# Tooltip: Will copy the weights from one side to another, if the vertex group names have an 'L' or 'R' suffix
import bpy

def flip_vertex_group_names(obj):
    # Create a dictionary to hold the original and temporary names
    temp_names = {}

    # First pass: Rename all groups to a temporary name
    for group in obj.vertex_groups:
        original_name = group.name
        if original_name.lower().startswith('l'):
            temp_name = 'TEMP_RIGHT' + original_name[1:]
        elif original_name.lower().startswith('r'):
            temp_name = 'TEMP_LEFT' + original_name[1:]
        else:
            continue  # Skip groups that don't start with 'l' or 'r'
        temp_names[temp_name] = original_name
        group.name = temp_name

    # Second pass: Rename from temporary to final names
    for temp_name, original_name in temp_names.items():
        if original_name.lower().startswith('l'):
            final_name = 'r' + original_name[1:]
        else:
            final_name = 'l' + original_name[1:]
        obj.vertex_groups[temp_name].name = final_name

# Example usage
obj = bpy.context.active_object
if obj and obj.type == 'MESH':
    flip_vertex_group_names(obj)
else:
    print("No active mesh object selected.")
