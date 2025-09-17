# Tooltip: Strip duplicate suffixes from selected object names and remove bracketed content

import bpy
import re

def sanitize_object_name(name):
    """
    Sanitize object name by:
    1. Removing everything after square brackets [...]
    2. Removing duplicate suffixes, keeping only the first one

    Example: "楼板 常规 - 150mm [340795].013.013.013.013" -> "楼板 常规 - 150mm.013"
    """
    # First, remove everything from the first square bracket onwards
    bracket_pattern = r'\s*\[.*$'
    name = re.sub(bracket_pattern, '', name)

    # Find all suffix patterns (.xxx where xxx is typically 3 digits)
    # This pattern matches .followed by digits/letters
    suffix_pattern = r'(\.\w+)'
    suffixes = re.findall(suffix_pattern, name)

    if suffixes:
        # Remove all suffixes from the name
        base_name = re.sub(r'(\.\w+)+$', '', name)
        # Add back only the first suffix
        sanitized_name = base_name + suffixes[0]
    else:
        sanitized_name = name

    return sanitized_name

def main():
    # Get all selected objects
    selected_objects = bpy.context.selected_objects

    if not selected_objects:
        print("No objects selected. Please select objects to sanitize their names.")
        return

    # Track changes for reporting
    changes_made = 0

    # Process each selected object
    for obj in selected_objects:
        original_name = obj.name
        sanitized_name = sanitize_object_name(original_name)

        if original_name != sanitized_name:
            obj.name = sanitized_name
            changes_made += 1
            print(f"Renamed: '{original_name}' -> '{sanitized_name}'")

    if changes_made > 0:
        print(f"✓ Successfully sanitized {changes_made} object names")
    else:
        print("No changes needed - all selected object names were already clean")

main()