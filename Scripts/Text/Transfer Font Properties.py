# Tooltip: Will Transfer Font Properties from active to selected
import bpy

# Ensure that the active object is a text object
if bpy.context.object.type != 'FONT':
    print("The active object is not a text object. Please select a text object.")
else:
    # Get the active object's data
    active_obj = bpy.context.object.data

    # Get the font settings
    regular_font = active_obj.font
    bold_font = active_obj.font_bold

    # Iterate over all selected objects
    for obj in bpy.context.selected_objects:
        # Ignore the active object
        if obj == bpy.context.object:
            continue
        # Ignore non-text objects
        if obj.type != 'FONT':
            print(f"{obj.name} is not a text object. Skipping.")
            continue

        # Set the font settings
        obj.data.font = regular_font
        obj.data.font_bold = bold_font
    print("Font settings copied successfully!")
