# Tooltip: Strip 4-character suffixes (.001, .002, .003, .004, .005, .006) from selected object names

import bpy
import re

def strip_4char_suffix(name):
    """
    Strip 4-character suffixes from object name.
    Removes suffixes: .001, .002, .003, .004, .005, .006

    Example: "Object.001" -> "Object"
    Example: "MyMesh.003" -> "MyMesh"
    """
    # Pattern to match the specific 4-character suffixes at the end of the name
    suffix_pattern = r'\.(001|002|003|004|005|006)$'

    # Check if the pattern matches
    match = re.search(suffix_pattern, name)
    if match:
        print(f"    Found suffix '{match.group()}' in '{name}'")

    # Remove the suffix if it matches
    cleaned_name = re.sub(suffix_pattern, '', name)

    return cleaned_name

def main():
    # Get all selected objects
    selected_objects = bpy.context.selected_objects

    if not selected_objects:
        print("No objects selected. Please select objects to strip suffixes from.")
        return

    # Track changes for reporting
    changes_made = 0
    attempted_changes = 0

    print(f"Processing {len(selected_objects)} selected objects...")

    # Process each selected object
    for obj in selected_objects:
        original_name = obj.name
        cleaned_name = strip_4char_suffix(original_name)

        print(f"Checking object: '{original_name}'")

        if original_name != cleaned_name:
            attempted_changes += 1
            print(f"  -> Attempting to rename to: '{cleaned_name}'")

            # Store the old name for comparison
            old_name = obj.name
            obj.name = cleaned_name

            # Check what Blender actually set the name to
            actual_new_name = obj.name

            if actual_new_name != old_name:
                changes_made += 1
                print(f"  -> Successfully renamed to: '{actual_new_name}'")
            else:
                print(f"  -> Blender kept the original name (possibly due to naming conflict)")
        else:
            print(f"  -> No suffix to remove")

    print(f"\nSummary:")
    print(f"Objects processed: {len(selected_objects)}")
    print(f"Rename attempts: {attempted_changes}")
    print(f"Successful renames: {changes_made}")

    if changes_made > 0:
        print(f"✓ Successfully stripped suffixes from {changes_made} object names")
    elif attempted_changes > 0:
        print("⚠ No objects were renamed - this might be due to naming conflicts")
        print("  (Blender may keep original names if the new name would conflict with existing objects)")
    else:
        print("No changes needed - no selected objects had the target suffixes (.001-.006)")

main()
