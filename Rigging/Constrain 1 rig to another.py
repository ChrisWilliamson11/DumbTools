# Tooltip: constrains 1 rig to another matching rig
import bpy

def copy_transform_constraints(source_armature, target_armature):
    # Ensure both armatures have the same bone hierarchy
    if len(source_armature.pose.bones) != len(target_armature.pose.bones):
        print("Armatures do not have the same number of bones")
        return
    
    # Iterate through each bone in the source armature
    for bone in source_armature.pose.bones:
        # Find the corresponding bone in the target armature
        if bone.name in target_armature.pose.bones:
            target_bone = target_armature.pose.bones[bone.name]
            
            # Add 'Copy Transforms' constraint to the source bone
            constraint = bone.constraints.new(type='COPY_TRANSFORMS')
            constraint.target = target_armature
            constraint.subtarget = target_bone.name
            
            # Set the space for both the target and owner to local space
            constraint.target_space = 'LOCAL'
            constraint.owner_space = 'LOCAL'
        else:
            print(f"Bone {bone.name} not found in target armature")

# Get the selected armatures
selected_objects = bpy.context.selected_objects

# Check if exactly 2 armatures are selected
if len(selected_objects) != 2:
    print("Please select exactly 2 armatures")
else:
    source_armature = None
    target_armature = None

    # Determine which is the active and which is the selected armature
    for obj in selected_objects:
        if obj == bpy.context.view_layer.objects.active:
            target_armature = obj
        else:
            source_armature = obj
    
    if source_armature and target_armature:
        copy_transform_constraints(source_armature, target_armature)
    else:
        print("Unable to determine source and target armatures")

