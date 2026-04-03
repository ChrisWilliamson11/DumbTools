# Tooltip:  Remove all materials from the selected objects except the first one.

import bpy

for obj in bpy.context.selected_objects:
    if obj.type == 'MESH':
        bpy.context.view_layer.objects.active = obj  # Set the object as active
        
        # Start from the last material and go in reverse, skipping the first material
        for i in reversed(range(1, len(obj.material_slots))):
            obj.active_material_index = i
            bpy.ops.object.material_slot_remove()
