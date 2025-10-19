# Tooltip: Copy selected object names to clipboard (newline delimited, removes Blender suffixes)

import bpy
import re

def remove_blender_suffix(name):
    """
    Remove Blender duplicate suffixes (.001, .002, .003) from object names.
    Only removes if it's exactly .001, .002, or .003 at the very end of the name.
    """
    # Pattern to match exactly .001, .002, or .003 at the end
    pattern = r'\.00[1234]$'
    return re.sub(pattern, '', name)

def main():
    # Get all selected objects
    selected_objects = bpy.context.selected_objects

    if not selected_objects:
        print("No objects selected. Please select objects to copy their names.")
        return

    # Get object names and remove Blender suffixes
    object_names = []
    for obj in selected_objects:
        clean_name = remove_blender_suffix(obj.name)
        object_names.append(clean_name)

    # Remove duplicates and sort
    unique_names = list(set(object_names))
    unique_names.sort()  # Sort alphabetically for consistency
    
    # Create newline-delimited string
    names_text = '\n'.join(unique_names)

    # Copy to clipboard
    try:
        bpy.context.window_manager.clipboard = names_text
        print(f"✓ {len(unique_names)} object names copied to clipboard")
    except:
        print("Could not copy to clipboard. Manual copy:")
        print(names_text)

main()
