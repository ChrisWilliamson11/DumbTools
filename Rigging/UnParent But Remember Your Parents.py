# Tooltip: Will Unparent your selected objects, but remembers what they were parent to for later ReParenting

import bpy

def unparent_and_store():
    for obj in bpy.context.selected_objects:
        # Store parent data
        if obj.parent:
            parent_data = {"parent_name": obj.parent.name, "bone_name": None}
            # Check if parented to a bone
            if obj.parent_type == 'BONE':
                parent_data["bone_name"] = obj.parent_bone
            # Store as a custom property
            obj["parenting_data"] = parent_data
        # Unparent the object
        bpy.ops.object.select_all(action='DESELECT')
        obj.select_set(True)
        bpy.context.view_layer.objects.active = obj
        bpy.ops.object.parent_clear(type='CLEAR_KEEP_TRANSFORM')
        obj.select_set(False)

unparent_and_store()
