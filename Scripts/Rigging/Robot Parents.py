# Tooltip: Select objects then select your armature, it will parent (not Weight) each object to its closest bone, doesnt have to be in rest pose, it will use the armatures current position, even if its animated.
import bpy
import mathutils

# Function to get the center of an object's bounding box in world space
def get_bounding_box_center(obj):
    local_bbox_center = 0.125 * sum((mathutils.Vector(b) for b in obj.bound_box), mathutils.Vector())
    world_bbox_center = obj.matrix_world @ local_bbox_center
    return world_bbox_center

# Function to find the bone closest to the given point
def find_closest_bone(armature, point):
    closest_bone = None
    closest_distance = float('inf')
    for bone in armature.pose.bones:
        bone_world_position = armature.matrix_world @ ((bone.head + bone.tail) / 2)
        distance = (bone_world_position - point).length
        if distance < closest_distance:
            closest_distance = distance
            closest_bone = bone
    return closest_bone

# Ensure that an armature is active
if bpy.context.active_object.type == 'ARMATURE':
    armature = bpy.context.active_object
    
    # Get a list of all selected objects excluding the armature
    selected_objects = [obj for obj in bpy.context.selected_objects if obj.type == 'MESH' and obj != armature]

    # Deselect all objects
    bpy.ops.object.select_all(action='DESELECT')

    # Iterate through previously selected objects
    for obj in selected_objects:
        # Get the bounding box center in world space
        center_point = get_bounding_box_center(obj)

        # Find the closest bone to the bounding box center
        closest_bone = find_closest_bone(armature, center_point)

        if closest_bone:
            # Select the object and make the armature the active object
            obj.select_set(True)
            bpy.context.view_layer.objects.active = armature

            # Set the active bone for the armature
            bpy.context.object.data.bones.active = armature.data.bones[closest_bone.name]

            # Parent the object to the closest bone using BONE_RELATIVE
            bpy.ops.object.parent_set(type='BONE_RELATIVE')

            # Deselect the object before moving to the next one
            obj.select_set(False)

    # Switch back to Object mode
    bpy.ops.object.mode_set(mode='OBJECT')

else:
    print("Please select an armature.")
