# Tooltip: Convert Selected Text To Uppercase
import bpy

def convert_to_uppercase():
    selected_objects = bpy.context.selected_objects
    for obj in selected_objects:
        if obj.type == 'FONT':
            text_object = obj.data
            current_text = text_object.body
            new_text = current_text.upper()
            text_object.body = new_text

# Call the function to convert text to uppercase
convert_to_uppercase()