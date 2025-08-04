# Tooltip:  Copy constraints from 1 rig to another matching rig
import bpy

def copy_constraints(source_armature, target_armature):
    # Check if both objects are armatures
    if source_armature.type != 'ARMATURE' or target_armature.type != 'ARMATURE':
        print("Both objects need to be armatures.")
        return

    # Access pose bones for source and target
    source_bones = source_armature.pose.bones
    target_bones = target_armature.pose.bones

    # Iterate over all bones in the source armature
    for bone_name in source_bones.keys():
        if bone_name in target_bones.keys():
            source_bone = source_bones[bone_name]
            target_bone = target_bones[bone_name]
            
            # Remove all existing constraints from the target bone one by one
            for constraint in target_bone.constraints:
                target_bone.constraints.remove(constraint)
            
            # Copy all constraints from the source bone to the target bone
            for constraint in source_bone.constraints:
                new_constraint = target_bone.constraints.new(type=constraint.type)
                # Copy attributes of each constraint
                for attr in dir(constraint):
                    if attr.startswith("__") or callable(getattr(constraint, attr)) or attr in ("bl_rna", "rna_type"):
                        continue
                    try:
                        setattr(new_constraint, attr, getattr(constraint, attr))
                    except AttributeError as e:
                        print(f"Cannot set attribute {attr} due to error: {e}")

# Retrieve the selected and active armatures
selected_objs = bpy.context.selected_objects
active_obj = bpy.context.active_object

# Remove active object from selected list
selected_objs.remove(active_obj)

# Ensure there is exactly one other selected armature
if len(selected_objs) != 1 or selected_objs[0].type != 'ARMATURE':
    print("Please select exactly one other armature.")
else:
    copy_constraints(selected_objs[0], active_obj)
