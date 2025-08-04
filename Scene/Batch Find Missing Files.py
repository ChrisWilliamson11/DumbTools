# Tooltip: This script will batch find missing files in a directory and its subdirectories.

import bpy
import os
from bpy.props import StringProperty, IntProperty
from bpy.types import Operator, Panel

class BatchFindMissingFilesOperator(Operator):
    """Process multiple blend files to find missing files"""
    bl_idname = "file.batch_find_missing"
    bl_label = "Batch Find Missing Files"
    bl_options = {'REGISTER'}
    
    def process_directory(self, directory, search_dir, current_depth, max_depth):
        """Recursively process blend files in directory and its subdirectories"""
        for entry in os.scandir(directory):
            if entry.is_file() and entry.name.endswith(".blend"):
                blend_path = entry.path
                
                # Open the blend file
                bpy.ops.wm.open_mainfile(filepath=blend_path)
                
                # Set search path and find missing files
                bpy.ops.file.find_missing_files(directory=search_dir)
                
                # Save the file
                bpy.ops.wm.save_mainfile()
            
            # Recurse into subdirectories if we haven't reached max depth
            elif entry.is_dir() and (max_depth == -1 or current_depth < max_depth):
                self.process_directory(entry.path, search_dir, current_depth + 1, max_depth)
    
    def execute(self, context):
        source_dir = context.scene.source_directory
        search_dir = context.scene.search_directory
        max_depth = context.scene.recursion_depth
        
        if not source_dir or not search_dir:
            self.report({'ERROR'}, "Please select both directories")
            return {'CANCELLED'}
        
        # Process the source directory
        self.process_directory(source_dir, search_dir, 0, max_depth)
        
        self.report({'INFO'}, "Finished processing all blend files")
        return {'FINISHED'}

    def invoke(self, context, event):
        return context.window_manager.invoke_props_dialog(self, width=400)
    
    def draw(self, context):
        layout = self.layout
        scene = context.scene
        
        # Source directory selection
        box = layout.box()
        box.label(text="Blend Files Directory:", icon='FILE_BLEND')
        row = box.row(align=True)
        row.prop(scene, "source_directory", text="")
        
        # Search directory selection
        box = layout.box()
        box.label(text="Search Directory for Missing Files:", icon='VIEWZOOM')
        row = box.row(align=True)
        row.prop(scene, "search_directory", text="")
        
        # Recursion depth
        box = layout.box()
        box.label(text="Recursion Settings:", icon='NEWFOLDER')
        row = box.row(align=True)
        row.prop(scene, "recursion_depth")

class SelectSourceDirectoryOperator(Operator):
    """Select the directory containing blend files"""
    bl_idname = "file.select_source_directory"
    bl_label = "Select Blend Files Directory"
    
    directory: StringProperty(subtype='DIR_PATH')
    
    def execute(self, context):
        context.scene.source_directory = self.directory
        return {'FINISHED'}
    
    def invoke(self, context, event):
        context.window_manager.fileselect_add(self)
        return {'RUNNING_MODAL'}

class SelectSearchDirectoryOperator(Operator):
    """Select the directory to search for missing files"""
    bl_idname = "file.select_search_directory"
    bl_label = "Select Search Directory"
    
    directory: StringProperty(subtype='DIR_PATH')
    
    def execute(self, context):
        context.scene.search_directory = self.directory
        return {'FINISHED'}
    
    def invoke(self, context, event):
        context.window_manager.fileselect_add(self)
        return {'RUNNING_MODAL'}

def register():
    bpy.types.Scene.source_directory = StringProperty(
        name="Source Directory",
        description="Directory containing blend files to process",
        subtype='DIR_PATH'
    )
    bpy.types.Scene.search_directory = StringProperty(
        name="Search Directory",
        description="Directory to search for missing files",
        subtype='DIR_PATH'
    )
    bpy.types.Scene.recursion_depth = IntProperty(
        name="Recursion Depth",
        description="How deep to recurse into subdirectories (-1 for unlimited, 0 for no recursion)",
        default=0,
        min=-1
    )
    bpy.utils.register_class(BatchFindMissingFilesOperator)
    bpy.utils.register_class(SelectSourceDirectoryOperator)
    bpy.utils.register_class(SelectSearchDirectoryOperator)

def unregister():
    del bpy.types.Scene.source_directory
    del bpy.types.Scene.search_directory
    del bpy.types.Scene.recursion_depth
    bpy.utils.unregister_class(BatchFindMissingFilesOperator)
    bpy.utils.unregister_class(SelectSourceDirectoryOperator)
    bpy.utils.unregister_class(SelectSearchDirectoryOperator)

register()
bpy.ops.file.batch_find_missing('INVOKE_DEFAULT')