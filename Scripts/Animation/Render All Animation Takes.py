# Tooltip:  Outputs every action in the scene on the selected armature to deadline for rendering

import bpy
import os
import re
import tempfile
import subprocess
import shutil

# Get deadline path from DumbTools preferences
def get_deadline_path():
    try:
        prefs = bpy.context.preferences.addons["DumbTools"].preferences
        return getattr(prefs, 'deadline_path', "\\\\wlgsrvrnd\\DeadlineRepository10\\bin\\Windows\\64bit\\deadlinecommand.exe")
    except:
        # Fallback to hardcoded path if preferences aren't available
        return "\\\\wlgsrvrnd\\DeadlineRepository10\\bin\\Windows\\64bit\\deadlinecommand.exe"

# Function to clean action name and remove numeric suffixes
def clean_action_name(action_name):
    # Remove numeric suffixes
    clean_name = re.sub(r'\.\d+$', '', action_name)
    # Replace spaces with underscores
    return clean_name.replace(" ", "_")

def submit_to_deadline(blend_filepath, scene_name, frame_start, frame_end):
    """Submit a specific blend file to Deadline"""
    DEADLINE_PATH = get_deadline_path()
    job_info = {
        "Plugin": "Blender",
        "Name": f"{scene_name}",
        "Frames": f"{frame_start}-{frame_end}",
        "ChunkSize": "10000",
    }

    plugin_info = {
        "SceneFile": blend_filepath,
    }

    # Write job_info and plugin_info to temporary files
    with tempfile.NamedTemporaryFile(delete=False, mode='w', suffix=".job") as job_file, \
         tempfile.NamedTemporaryFile(delete=False, mode='w', suffix=".plugin") as plugin_file:

        job_file.write("\n".join([f"{k}={v}" for k, v in job_info.items()]))
        plugin_file.write("\n".join([f"{k}={v}" for k, v in plugin_info.items()]))

        job_file.close()
        plugin_file.close()

        cmd = f"{DEADLINE_PATH} -SubmitJob {job_file.name} {plugin_file.name}"
        result = subprocess.run(cmd, shell=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
        #print(f"Command: {cmd}")
        #print(f"Return code: {result.returncode}")
        #print(f"Output: {result.stdout}")
        #print(f"Errors: {result.stderr}")

        os.remove(job_file.name)
        os.remove(plugin_file.name)

        return result.returncode == 0

# Get the selected armature object
armature = None
if bpy.context.selected_objects:
    for obj in bpy.context.selected_objects:
        if obj.type == 'ARMATURE':
            armature = obj
            break

if not armature:
    print("ERROR: No armature selected. Please select an armature object.")
else:
    #print(f"Using selected armature: {armature.name}")

    # Ensure the armature has an animation data block
    if not armature.animation_data:
        armature.animation_data_create()

    # Get the original file path
    original_filepath = bpy.data.filepath
    original_armature_name = armature.name

    if not original_filepath:
        print("ERROR: Please save your file before running this script.")
    else:
        # Save the current file to ensure we have the latest version
        bpy.ops.wm.save_mainfile()

        # Get base directory from render output path
        render_path = bpy.context.scene.render.filepath

        # If render path is relative, make it absolute relative to the blend file directory
        if not os.path.isabs(render_path):
            blend_dir = os.path.dirname(original_filepath)
            render_path = os.path.join(blend_dir, render_path)

        base_directory = os.path.dirname(render_path)

        # Ensure base_directory is absolute
        base_directory = os.path.abspath(base_directory)

        # Store all action names from the selected armature
        # Filter to only actions that belong to this armature (have matching data)
        all_action_names = [action.name for action in bpy.data.actions]

        #print(f"Found {len(all_action_names)} actions to process")

        # Process each action
        for action_name in all_action_names:
            #print(f"\n--- Processing action: {action_name} ---")

            # Clean the action name for file/folder naming
            action_safe_name = clean_action_name(action_name)

            # Create the new blend file path
            new_blend_path = os.path.join(base_directory, f"{action_safe_name}.blend")

            # Copy the original file to the new location
            #print(f"Copying {original_filepath} to {new_blend_path}")
            shutil.copy2(original_filepath, new_blend_path)

            # Open the copied file
            bpy.ops.wm.open_mainfile(filepath=new_blend_path)

            # Re-get the armature reference in the newly opened file
            armature = bpy.data.objects.get(original_armature_name)
            if not armature:
                print(f"ERROR: Armature '{original_armature_name}' not found in copied file. Skipping {action_name}")
                continue

            # Get the action by name
            action = bpy.data.actions.get(action_name)
            if not action:
                print(f"ERROR: Action '{action_name}' not found in copied file. Skipping.")
                continue

            # Set the action to the armature
            if not armature.animation_data:
                armature.animation_data_create()
            armature.animation_data.action = action

            # Set frame range to match the action
            bpy.context.scene.frame_start = int(action.frame_range[0])
            bpy.context.scene.frame_end = int(action.frame_range[1])

            # Update render output path - renders go directly in base directory
            bpy.context.scene.render.filepath = os.path.join(base_directory, action_safe_name + "_")

            # Remove all other actions (keep only the current one)
            actions_to_remove = [a for a in bpy.data.actions if a != action]
            for other_action in actions_to_remove:
                bpy.data.actions.remove(other_action)

            # Save the modified file
            bpy.ops.wm.save_mainfile()

            # Submit to Deadline
            success = submit_to_deadline(new_blend_path, bpy.context.scene.name,
                                        bpy.context.scene.frame_start, bpy.context.scene.frame_end)

            if success:
                print(f"✓ Submitted: {action_name}")
            else:
                print(f"✗ Failed to submit: {action_name}")

        # Reopen the original file to restore state
        bpy.ops.wm.open_mainfile(filepath=original_filepath)
        print(f"\n=== Finished processing {len(all_action_names)} actions ===")
