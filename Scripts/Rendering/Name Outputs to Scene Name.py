# Tooltip: Alters the output names based off the scene name with optional prefix and path
import bpy
import os

class NameOutputsToSceneNameOperator(bpy.types.Operator):
    """Set output filenames based on scene names with optional prefix and path"""
    bl_idname = "scene.name_outputs_to_scene_name"
    bl_label = "Name Outputs to Scene Name"
    bl_options = {'REGISTER', 'UNDO'}
    
    prefix: bpy.props.StringProperty(
        name="Prefix",
        description="Prefix to add before the scene name",
        default=""
    )
    
    new_path: bpy.props.StringProperty(
        name="New Output Path",
        description="Optional new directory path for outputs (leave empty to keep current paths)",
        default="",
        subtype='DIR_PATH'
    )
    
    def execute(self, context):
        self.update_output_filenames(self.prefix, self.new_path)
        prefix_msg = f"with prefix: '{self.prefix}'" if self.prefix else ""
        path_msg = f"to new path: '{self.new_path}'" if self.new_path else ""
        if prefix_msg and path_msg:
            self.report({'INFO'}, f"Updated output names {prefix_msg} {path_msg}")
        else:
            self.report({'INFO'}, f"Updated output names {prefix_msg}{path_msg}")
        return {'FINISHED'}
    
    def invoke(self, context, event):
        # Pre-populate the fields with current scene settings
        scene = context.scene
        render = scene.render
        
        # Generate a prefix based on resolution and format
        resolution = f"{render.resolution_x}x{render.resolution_y}"
        file_format = render.image_settings.file_format
        
        # Check for denoise settings
        denoise = ""
        if hasattr(scene, 'cycles') and scene.cycles.use_denoising:
            denoise = "_Denoised"
        
        # Generate a meaningful prefix
        self.prefix = f"{resolution}_{file_format}{denoise}_"
        
        # Pre-fill the path with the current output directory
        current_path = render.filepath
        self.new_path = os.path.dirname(current_path)
        
        return context.window_manager.invoke_props_dialog(self)
    
    def update_output_filenames(self, prefix, new_path):
        for scene in bpy.data.scenes:
            # Get the current output path
            current_output_path = scene.render.filepath
            
            # Get the directory path without the file name
            directory_path = new_path if new_path else os.path.dirname(current_output_path)
            
            # Create a new output path with the optional prefix and scene name as the filename
            filename = f"{prefix}{scene.name}" if prefix else scene.name
            new_output_path = os.path.join(directory_path, filename)
            
            # Set the new output path for the scene
            scene.render.filepath = new_output_path

def register():
    bpy.utils.register_class(NameOutputsToSceneNameOperator)

def unregister():
    bpy.utils.unregister_class(NameOutputsToSceneNameOperator)

register()
# Show the dialog
bpy.ops.scene.name_outputs_to_scene_name('INVOKE_DEFAULT')
