# Tooltip: constrains 1 rig to another matching rig by bone world positions
import bpy

# Margin of error in meters for bone head/tail distance
MARGIN = 0.01 

def copy_transform_constraints_by_position(source_armature, target_armature, margin):
    for bone in source_armature.pose.bones:
        # Calculate world space positions for source bone
        source_head = source_armature.matrix_world @ bone.head
        source_tail = source_armature.matrix_world @ bone.tail
        
        best_match = None
        best_dist = float('inf')
        
        for target_bone in target_armature.pose.bones:
            # Calculate world space positions for target bone
            target_head = target_armature.matrix_world @ target_bone.head
            target_tail = target_armature.matrix_world @ target_bone.tail
            
            dist_head = (source_head - target_head).length
            dist_tail = (source_tail - target_tail).length
            
            # Check if both head and tail are within the margin of error
            if dist_head <= margin and dist_tail <= margin:
                total_dist = dist_head + dist_tail
                # If there are multiple matches within margin, pick the closest one
                if total_dist < best_dist:
                    best_dist = total_dist
                    best_match = target_bone
                    
        if best_match:
            # Add 'Copy Transforms' constraint to the source bone
            constraint = bone.constraints.new(type='COPY_TRANSFORMS')
            constraint.target = target_armature
            constraint.subtarget = best_match.name
            
            # Set the space for both the target and owner to local space
            constraint.target_space = 'LOCAL'
            constraint.owner_space = 'LOCAL'
            print(f"Constrained '{bone.name}' to '{best_match.name}' (error: {best_dist:.4f}m)")
        else:
            print(f"No positional match found for '{bone.name}'")

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
    
    if source_armature and target_armature and source_armature.type == 'ARMATURE' and target_armature.type == 'ARMATURE':
        copy_transform_constraints_by_position(source_armature, target_armature, MARGIN)
    else:
        print("Please ensure both selected objects are armatures and 2 are selected.")
