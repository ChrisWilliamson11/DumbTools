# Tooltip: Delete all the constraints on the selected bones
import bpy

# Get the current armature object
obj = bpy.context.object

# Check if the object is an armature
if obj and obj.type == 'ARMATURE':
    # Enter pose mode
    bpy.ops.object.mode_set(mode='POSE')

    # Iterate over all selected bones
    for bone in obj.pose.bones:
        if bone.bone.select:
            # Remove all constraints from the selected bone
            while bone.constraints:
                bone.constraints.remove(bone.constraints[0])

    # Return to object mode
    bpy.ops.object.mode_set(mode='OBJECT')
else:
    print("No armature selected. Please select an armature.")
