# Tooltip: Copy the object color from the active object to all selected objects

import bpy

def set_object_color_active_to_selected():
    active_object = bpy.context.active_object
    selected_objects = bpy.context.selected_objects
    for obj in selected_objects:
        obj.color = active_object.color  

        

set_object_color_active_to_selected()
