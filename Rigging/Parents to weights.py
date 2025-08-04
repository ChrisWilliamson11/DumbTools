# Tooltip: If you have objects parented to bones, this will convert them to vertex groups and an armature modifier
import bpy

# Get the active scene
scene = bpy.context.scene

# Iterate over selected objects in the scene
for obj in bpy.context.selected_objects:
    if obj.parent and obj.parent.type == 'ARMATURE' and obj.parent_bone:
        bone_name = obj.parent_bone

        # Create a vertex group with the bone's name
        vg = obj.vertex_groups.new(name=bone_name)
        
        # Assign all vertices to this group
        vertices = [v.index for v in obj.data.vertices]
        vg.add(vertices, 1.0, 'REPLACE')  # 1.0 is the weight, which means fully influenced by the bone
        
        # Add armature modifier
        modifier = obj.modifiers.new(name="Armature", type='ARMATURE')
        modifier.object = obj.parent
        
        # Unparent the object
        obj.parent = None

