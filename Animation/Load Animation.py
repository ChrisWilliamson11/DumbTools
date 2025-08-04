# Tooltip: Load an image sequence and apply it to selected objects using geometry nodes
import numpy as np
import os
import subprocess
import sys
# Get info
start_frame = bpy.context.scene.frame_start
end_frame = bpy.context.scene.frame_end
total_frames = end_frame - start_frame + 1

print(f"Start Frame: {start_frame}, End Frame: {end_frame}, Total Frames: {total_frames}")

objects = bpy.context.selected_objects
dependency_graph = bpy.context.evaluated_depsgraph_get()

print(f"Number of selected objects: {len(objects)}")

def get_script_folder():
    # Access the script folder path from the preferences
    prefs = bpy.context.preferences.addons["DumbTools"].preferences
    return prefs.script_folder


class BrowseTargetFolderOperator(bpy.types.Operator):
    bl_idname = "object.browse_target_folder"
    bl_label = "Browse Target Folder"

    filepath: bpy.props.StringProperty(subtype="DIR_PATH")

    def execute(self, context):
        context.scene.store_animation_props.target_folder = self.filepath
        return {'FINISHED'}

    def invoke(self, context, event):
        context.window_manager.fileselect_add(self)
        return {'RUNNING_MODAL'}

class LoadAnimationOperator(bpy.types.Operator):
    bl_idname = "object.load_animation"
    bl_label = "Load Animation"
    bl_options = {'REGISTER', 'UNDO'}

    filepath: bpy.props.StringProperty(subtype="FILE_PATH")

    def execute(self, context):
        # Load the image sequence
        image_sequence = bpy.data.images.load(self.filepath)
        image_sequence.source = 'SEQUENCE'
        image_sequence.name = "Loaded_ImageSequence"
        print(f"Loaded image sequence from: {self.filepath}")

        # Calculate frame range from file names
        frame_start, frame_end = self.calculate_frame_range(self.filepath)

        # Add geometry nodes modifier and set keyframes
        self.add_geometry_nodes_modifier_with_image_sequence(context.active_object, image_sequence, frame_start, frame_end)

        return {'FINISHED'}

    def calculate_frame_range(self, filepath):
        # Extract frame numbers from the file path
        # Assuming file names are in the format: "name_frame_#.ext"
        import re
        frame_numbers = [int(re.search(r'(\d+)', os.path.basename(filepath)).group())]
        # You might need to adjust this logic based on your file naming convention
        return min(frame_numbers), max(frame_numbers)

    def add_geometry_nodes_modifier_with_image_sequence(self, obj, image_sequence, frame_start, frame_end):
        # Append the LoadAnimation node group
        self.append_load_animation_node_group()

        # Add a geometry nodes modifier
        mod_name = f"{obj.name}_LoadAnimation"
        if mod_name not in obj.modifiers:
            mod = obj.modifiers.new(name=mod_name, type='NODES')
            mod.node_group = bpy.data.node_groups.get("LoadAnimation")
            if mod.node_group:
                print(f"Assigned LoadAnimation node group to modifier: {mod_name}")
            else:
                print("Failed to assign LoadAnimation node group. Check if it was appended correctly.")

            # Set the image sequence as the image input
            try:
                mod["Socket_2"] = image_sequence  # Replace "Socket_2" with the correct socket name or index
                print("Assigned image sequence to Socket_2.")
            except KeyError:
                print("Failed to assign image sequence to Socket_2. Check socket name or index.")

            # Set keyframes for the frame input
            try:
                mod["Socket_3"] = 0  # Start at frame 0 of the sequence
                mod.keyframe_insert(data_path='["Socket_3"]', frame=frame_start)

                mod["Socket_3"] = frame_end - frame_start  # End at the last frame of the sequence
                mod.keyframe_insert(data_path='["Socket_3"]', frame=frame_end)

                print(f"Keyframes set from frame {frame_start} to {frame_end}.")
            except Exception as e:
                print(f"Failed to set keyframes for frame input: {e}")
        else:
            print(f"Modifier {mod_name} already exists on the object.")

    def append_load_animation_node_group(self):
        script_folder = get_script_folder()
        filepath = os.path.join(script_folder, "Docs", "Assets", "LoadAnimation.blend")
        print(f"Loading node group from: {filepath}")
        with bpy.data.libraries.load(filepath, link=False) as (data_from, data_to):
            if "LoadAnimation" not in bpy.data.node_groups:
                data_to.node_groups = [name for name in data_from.node_groups if name == "LoadAnimation"]
                print("Appended LoadAnimation node group.")
            else:
                print("LoadAnimation node group already exists.")

    def invoke(self, context, event):
        context.window_manager.fileselect_add(self)
        return {'RUNNING_MODAL'}

def register():


    bpy.utils.register_class(BrowseTargetFolderOperator)
    bpy.utils.register_class(LoadAnimationOperator)

def unregister():
    bpy.utils.unregister_class(BrowseTargetFolderOperator)
    bpy.utils.unregister_class(LoadAnimationOperator)


register()
bpy.ops.object.load_animation('INVOKE_DEFAULT')

