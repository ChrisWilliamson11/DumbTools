# Tooltip: will ReParent your selected objects to their previous parents stored by UnParenting
import bpy

def reparent_using_stored_data():
    for obj in bpy.context.selected_objects:
        # Check if the object has the custom parenting data
        if "parenting_data" in obj:
            data = obj["parenting_data"]
            parent_name = data.get("parent_name")
            bone_name = data.get("bone_name")

            # Find the parent object
            parent_obj = bpy.data.objects.get(parent_name)
            if parent_obj:
                # Clear all selections
                bpy.ops.object.select_all(action='DESELECT')

                # Select the object to be parented
                obj.select_set(True)
                bpy.context.view_layer.objects.active = parent_obj

                if bone_name and parent_obj.type == 'ARMATURE':
                    # Set the active bone for the armature
                    bpy.context.object.data.bones.active = parent_obj.data.bones[bone_name]

                    # Parent to a specific bone using BONE_RELATIVE
                    bpy.ops.object.parent_set(type='BONE_RELATIVE')

                else:
                    # Parent normally to the object
                    parent_obj.select_set(True)
                    bpy.ops.object.parent_set(type='OBJECT', keep_transform=True)

                # Deselect objects after parenting
                obj.select_set(False)
                parent_obj.select_set(False)

            # Remove custom property
            del obj["parenting_data"]

reparent_using_stored_data()
