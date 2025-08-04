# Tooltip: Delete all the drivers from the selected bones
import bpy

# Get the active object (assumes it is an armature)
obj = bpy.context.active_object

# Ensure the active object is an armature
if obj and obj.type == 'ARMATURE':
    # Get the selected bones
    selected_bones = [bone.name for bone in obj.data.bones if bone.select]
    
    # Iterate over each selected bone
    for bone_name in selected_bones:
        # Iterate over each rotation channel
        for rotation_channel in ['rotation_euler', 'rotation_quaternion']:
            # Check if the bone has the rotation channel
            if hasattr(obj.pose.bones[bone_name], rotation_channel):
                # Get the data path for the rotation channel
                data_path = f'pose.bones["{bone_name}"].{rotation_channel}'
                
                # Iterate over each driver
                for driver in obj.animation_data.drivers:
                    # Check if the driver's data path matches the rotation channel
                    if driver.data_path.startswith(data_path):
                        # Remove the driver
                        obj.animation_data.drivers.remove(driver)

print("Drivers removed from all rotation channels of selected bones.")
