# Tooltip: Adds an Empty at the average location of selected bones and parents them to it with Child Of constraints to reorient their action.

import bpy
from mathutils import Vector

def reorient_action():
    obj = bpy.context.active_object
    if not obj or obj.type != 'ARMATURE' or bpy.context.mode != 'POSE':
        print("Must be in Pose Mode with an Armature active.")
        return
    
    selected_bones = bpy.context.selected_pose_bones
    if not selected_bones:
        print("No bones selected.")
        return
    
    # Calculate average position in world space
    avg_loc = Vector((0.0, 0.0, 0.0))
    for pb in selected_bones:
        avg_loc += (obj.matrix_world @ pb.matrix).translation
    
    avg_loc /= len(selected_bones)
    
    # Store names to reselect
    selected_bone_names = [pb.name for pb in selected_bones]
    
    # Create empty
    bpy.ops.object.mode_set(mode='OBJECT')
    bpy.ops.object.empty_add(type='PLAIN_AXES', location=avg_loc, rotation=(0.0, 0.0, 0.0))
    empty = bpy.context.active_object
    empty.name = "Reorient_Empty"
    
    # Switch back to pose mode and active armature
    bpy.context.view_layer.objects.active = obj
    bpy.ops.object.mode_set(mode='POSE')
    
    for name in selected_bone_names:
        pb = obj.pose.bones.get(name)
        if not pb: continue
        
        # Deselect all constraints to be clean
        # Add Child Of constraint
        con = pb.constraints.new('CHILD_OF')
        con.name = "Reorient_Child"
        con.target = empty
        
        # Override context for set_inverse
        override = bpy.context.copy()
        override['constraint'] = con
        with bpy.context.temp_override(active_pose_bone=pb, constraint=con):
            bpy.ops.constraint.childof_set_inverse(constraint=con.name, owner='BONE')

    # Exit Pose Mode and select the empty
    bpy.ops.object.mode_set(mode='OBJECT')
    bpy.ops.object.select_all(action='DESELECT')
    empty.select_set(True)
    bpy.context.view_layer.objects.active = empty

reorient_action()
