# Tooltip: Store animation data from selected objects as image sequences for later playback
import bpy
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

class StoreAnimationProperties(bpy.types.PropertyGroup):
    use_world_space: bpy.props.BoolProperty(
        name="Use World Space",
        description="Store vertex positions in world space",
        default=True
    )

    start_frame: bpy.props.IntProperty(
        name="Start Frame",
        description="Start frame for animation",
        default=bpy.context.scene.frame_start
    )

    end_frame: bpy.props.IntProperty(
        name="End Frame",
        description="End frame for animation",
        default=bpy.context.scene.frame_end
    )

    target_folder: bpy.props.StringProperty(
        name="Target Folder",
        description="Folder to save the images",
        default=bpy.path.abspath("//"),
        subtype='DIR_PATH'
    )

class StoreAnimationOperator(bpy.types.Operator):
    bl_idname = "object.store_animation"
    bl_label = "Store Animation"
    bl_options = {'REGISTER', 'UNDO'}

    def execute(self, context):
        props = context.scene.store_animation_props
        start_frame = props.start_frame
        end_frame = props.end_frame
        objects = bpy.context.selected_objects
        dependency_graph = bpy.context.evaluated_depsgraph_get()

        # Export images
        for frame in range(start_frame, end_frame + 1):
            bpy.context.scene.frame_set(frame)
            for obj in objects:
                eval_obj = obj.evaluated_get(dependency_graph)
                mesh = eval_obj.to_mesh()

                vertex_count = len(mesh.vertices)
                image = np.zeros((1, vertex_count, 4), dtype=np.float32)

                for i, vertex in enumerate(mesh.vertices):
                    if props.use_world_space:
                        position = eval_obj.matrix_world @ vertex.co
                    else:
                        position = vertex.co
                    image[0, i] = [position.x, position.y, position.z, 1.0]

                export_name = f"{obj.name}_frame_{frame}"
                image_name = f"{export_name}.exr"
                image_path = os.path.join(props.target_folder, image_name)
                img = bpy.data.images.new(name=image_name, width=vertex_count, height=1, float_buffer=True, alpha=True)
                img.colorspace_settings.name = 'Non-Color'
                img.pixels = image.flatten()
                img.filepath_raw = image_path
                img.file_format = 'OPEN_EXR'
                img.save()

                # Clear the mesh and remove the image from Blender
                eval_obj.to_mesh_clear()
                bpy.data.images.remove(img)

        # After exporting, load the image sequence and set up the geometry nodes modifier
        self.add_geometry_nodes_modifier_with_image_sequence(objects[0], props)

        return {'FINISHED'}

    def add_geometry_nodes_modifier_with_image_sequence(self, obj, props):
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

            # Load the image sequence
            try:
                first_image_path = os.path.join(props.target_folder, f"{obj.name}_frame_{props.start_frame}.exr")
                image_sequence = bpy.data.images.load(first_image_path)
                image_sequence.source = 'SEQUENCE'
                image_sequence.name = f"{obj.name}_ImageSequence"
                print(f"Loaded image sequence starting from: {first_image_path}")

            except Exception as e:
                print(f"Failed to load image sequence: {e}")
                return

            # Set the image sequence as the image input
            try:
                mod["Socket_2"] = image_sequence  # Replace "Socket_2" with the correct socket name or index
                print("Assigned image sequence to Socket_2.")
            except KeyError:
                print("Failed to assign image sequence to Socket_2. Check socket name or index.")

            # Set the driver for the frame input
            try:
                mod["Socket_3"] = bpy.context.scene.frame_current
                frame_driver = mod.driver_add('["Socket_3"]').driver
                frame_driver.type = 'SCRIPTED'
                frame_driver.expression = "frame"
                var = frame_driver.variables.new()
                var.name = "frame"
                var.targets[0].id_type = 'SCENE'
                var.targets[0].id = bpy.context.scene
                var.targets[0].data_path = "frame_current"
                print("Driver set for frame input.")
            except Exception as e:
                print(f"Failed to set driver for frame input: {e}")
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
        return context.window_manager.invoke_props_dialog(self)

    def draw(self, context):
        layout = self.layout
        props = context.scene.store_animation_props
        layout.prop(props, "use_world_space")
        layout.prop(props, "start_frame")
        layout.prop(props, "end_frame")
        layout.prop(props, "target_folder")


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

def register():
    bpy.utils.register_class(StoreAnimationProperties)
    bpy.utils.register_class(StoreAnimationOperator)
    bpy.utils.register_class(BrowseTargetFolderOperator)
    bpy.types.Scene.store_animation_props = bpy.props.PointerProperty(type=StoreAnimationProperties)

def unregister():
    bpy.utils.unregister_class(StoreAnimationProperties)
    bpy.utils.unregister_class(StoreAnimationOperator)
    bpy.utils.unregister_class(BrowseTargetFolderOperator)
    del bpy.types.Scene.store_animation_props

register()
bpy.ops.object.store_animation('INVOKE_DEFAULT')
