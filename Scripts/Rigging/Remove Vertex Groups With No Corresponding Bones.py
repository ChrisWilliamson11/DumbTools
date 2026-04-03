# Tooltip: This script will remove the vertex groups that don't have corresponding bones.

import bpy

def remove_unused_vertex_groups():
    # Ensure there's an active object and it's a mesh
    obj = bpy.context.object
    if not obj or obj.type != 'MESH':
        print("Please select a mesh object.")
        return
    
    # Find the armature modifier on the mesh
    armature_modifier = None
    for modifier in obj.modifiers:
        if modifier.type == 'ARMATURE':
            armature_modifier = modifier
            break
    
    if not armature_modifier or not armature_modifier.object or armature_modifier.object.type != 'ARMATURE':
        print("No armature modifier found on the selected mesh.")
        return
    
    # Get the armature object
    armature = armature_modifier.object
    
    # Collect all bone names from the armature
    bone_names = {bone.name for bone in armature.data.bones}
    
    # Get vertex groups on the mesh that don't correspond to any bone
    vertex_groups_to_remove = []
    for group in obj.vertex_groups:
        if group.name not in bone_names:
            vertex_groups_to_remove.append(group.name)
    
    # Remove the vertex groups that don't have corresponding bones
    for group_name in vertex_groups_to_remove:
        group = obj.vertex_groups.get(group_name)
        if group:
            obj.vertex_groups.remove(group)
            print(f"Removed vertex group: {group_name}")

    print(f"Completed. Removed {len(vertex_groups_to_remove)} vertex groups.")

# Call the function
remove_unused_vertex_groups()
