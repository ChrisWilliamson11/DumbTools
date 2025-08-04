# Tooltip:  Outputs ever action in the scene on the selected armature to deadline for rendering

import bpy
import os
import re
import tempfile
import subprocess

# Retrieve the existing base directory from the scene's render output path
base_directory = bpy.context.scene.render.filepath
# Ensure we use the directory part only, not a file path
base_directory = os.path.dirname(base_directory)

# Function to clean action name and remove numeric suffixes
def clean_action_name(action_name):
    # Remove numeric suffixes
    clean_name = re.sub(r'\.\d+$', '', action_name)
    # Replace spaces with underscores
    return clean_name.replace(" ", "_")

# Set the armature object to apply the actions to
armature_name = 'TeslaRig'
armature = bpy.data.objects.get(armature_name)

def submit_active_scene_to_deadline(scene_name, frame_start, frame_end):
    DEADLINE_PATH = "\\\\wlgsrvrnd\\DeadlineRepository10\\bin\\Windows\\64bit\\deadlinecommand.exe"
    job_info = {
        "Plugin": "Blender",
        "Name": f"{scene_name}",
        "Frames": f"{frame_start}-{frame_end}",
        "ChunkSize": "1000",  # Adjust based on your preference
        # Add more job info parameters as required
    }

    plugin_info = {
        "SceneFile": bpy.data.filepath,
        # Add more plugin info parameters as required
    }

    # Write job_info and plugin_info to temporary files
    with tempfile.NamedTemporaryFile(delete=False, mode='w', suffix=".job") as job_file, \
         tempfile.NamedTemporaryFile(delete=False, mode='w', suffix=".plugin") as plugin_file:
        
        # Write the job and plugin info
        job_file.write("\n".join([f"{k}={v}" for k, v in job_info.items()]))
        plugin_file.write("\n".join([f"{k}={v}" for k, v in plugin_info.items()]))

        # Ensure files are written and closed
        job_file.close()
        plugin_file.close()

        # Construct and run the submission command
        cmd = f"{DEADLINE_PATH} -SubmitJob {job_file.name} {plugin_file.name}"
        result = subprocess.run(cmd, shell=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
        print(f"Command: {cmd}")
        print(f"Return code: {result.returncode}")
        print(f"Output: {result.stdout}")
        print(f"Errors: {result.stderr}")

        # Cleanup temporary files
        os.remove(job_file.name)
        os.remove(plugin_file.name)

# Example usage within your script:
# This assumes you've set the scene's frame range according to the action before calling this function
submit_active_scene_to_deadline(bpy.context.scene.name, bpy.context.scene.frame_start, bpy.context.scene.frame_end)


if armature:
    # Ensure the armature has an animation data block
    if not armature.animation_data:
        armature.animation_data_create()

    # Iterate through all actions
    for action in bpy.data.actions:
        # Set the action to the armature
        armature.animation_data.action = action

        # Adjust the scene's frame start and end to match the action's frame range
        bpy.context.scene.frame_start = int(action.frame_range[0])
        bpy.context.scene.frame_end = int(action.frame_range[1])

        # Clean and prepare the action name for folder and file naming
        action_safe_name = clean_action_name(action.name)
        action_folder_path = os.path.join(base_directory, action_safe_name)
        if not os.path.exists(action_folder_path):
            os.makedirs(action_folder_path)

        # Update the render output path for the current action's image sequence
        bpy.context.scene.render.filepath = os.path.join(action_folder_path, action_safe_name + "_")

        # Save the Blender file with a new name based on the action name
        new_blender_file_path = os.path.join(base_directory, f"{action_safe_name}.blend")
        bpy.ops.wm.save_as_mainfile(filepath=new_blender_file_path)
        submit_active_scene_to_deadline(bpy.context.scene.name, bpy.context.scene.frame_start, bpy.context.scene.frame_end)

        print(f"Processed action: {action.name} - Files saved in: {action_folder_path}")

    print("Finished processing all actions.")
else:
    print(f"Armature '{armature_name}' not found in the scene.")
