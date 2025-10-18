import bpy
import os
import subprocess
from bpy_extras.io_utils import ImportHelper
from bpy.props import CollectionProperty, StringProperty, BoolProperty
from bpy.types import Operator, OperatorFileListElement

class BatchRenderMultipleFilesOperator(Operator, ImportHelper):
    bl_idname = "scene.batch_render_multiple_files"
    bl_label = "Batch Render Multiple Blend Files"
    bl_description = "Select multiple blend files and render them one by one"
    
    # File browser properties
    files: CollectionProperty(
        name="File Path",
        type=OperatorFileListElement,
    )
    
    directory: StringProperty(
        subtype='DIR_PATH',
    )
    
    filter_glob: StringProperty(
        default="*.blend",
        options={'HIDDEN'},
    )
    
    # Render options
    render_animation: BoolProperty(
        name="Render Animation",
        description="Render full animation instead of single frame",
        default=True
    )
    
    def get_blender_path(self):
        """Get Blender executable path"""
        return bpy.app.binary_path
    
    def render_blend_file(self, blend_file_path):
        """Render a single blend file"""
        print(f"Rendering blend file: {blend_file_path}")
        
        filename = os.path.splitext(os.path.basename(blend_file_path))[0]
        
        # Build command
        cmd_list = [self.get_blender_path(), "-b", blend_file_path]
        
        if self.render_animation:
            cmd_list.append("-a")  # Render animation
        else:
            cmd_list.extend(["-f", "1"])  # Render single frame
        
        try:
            result = subprocess.run(
                cmd_list,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                timeout=None  # No timeout for rendering
            )
            
            if result.returncode == 0:
                print(f"Successfully rendered: {filename}")
                return True
            else:
                print(f"Failed to render {filename}: {result.stderr}")
                return False
                
        except Exception as e:
            print(f"Error rendering {filename}: {e}")
            return False
    
    def execute(self, context):
        if not self.files:
            self.report({'ERROR'}, "No files selected")
            return {'CANCELLED'}
        
        successful_renders = 0
        total_files = len(self.files)
        
        # Process each selected blend file
        for i, file_elem in enumerate(self.files, 1):
            blend_file_path = os.path.join(self.directory, file_elem.name)
            
            if not os.path.exists(blend_file_path):
                print(f"File not found: {blend_file_path}")
                continue
            
            print(f"Processing file {i}/{total_files}: {file_elem.name}")
            
            if self.render_blend_file(blend_file_path):
                successful_renders += 1
        
        if successful_renders > 0:
            self.report({'INFO'}, f"Successfully rendered {successful_renders}/{total_files} files")
        else:
            self.report({'ERROR'}, "No files were rendered successfully")
        
        return {'FINISHED'}

class BatchRenderPanel(bpy.types.Panel):
    bl_label = "Batch Render"
    bl_idname = "SCENE_PT_batch_render"
    bl_space_type = 'PROPERTIES'
    bl_region_type = 'WINDOW'
    bl_context = "render"
    
    def draw(self, context):
        layout = self.layout
        layout.operator("scene.batch_render_multiple_files")

def register():
    bpy.utils.register_class(BatchRenderMultipleFilesOperator)
    bpy.utils.register_class(BatchRenderPanel)

def unregister():
    bpy.utils.unregister_class(BatchRenderMultipleFilesOperator)
    bpy.utils.unregister_class(BatchRenderPanel)

register()
bpy.ops.scene.batch_render_multiple_files('INVOKE_DEFAULT')