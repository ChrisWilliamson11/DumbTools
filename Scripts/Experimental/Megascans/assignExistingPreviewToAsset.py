import bpy
import os
from bpy_extras.io_utils import ImportHelper
from bpy.props import StringProperty
from bpy.types import Operator

class DUMBTOOLS_OT_assign_existing_previews(Operator, ImportHelper):
    """Assign existing previews to assets in blend files"""
    bl_idname = "dumbtools.assign_existing_previews"
    bl_label = "Load Existing Previews"
    bl_options = {'REGISTER', 'UNDO'}
    
    filename_ext = ""
    use_filter_folder = True
    
    directory: StringProperty(
        name="Directory",
        description="Choose a directory with blend files",
        subtype='DIR_PATH'
    )
    
    def find_preview_file(self, folder, asset_name):
        """Find preview file for given asset in folder"""
        for file in os.listdir(folder):
            # Check if file contains asset name and '_preview'
            if asset_name in file and '_preview' in file:
                # Check common image extensions
                if file.lower().endswith(('.png', '.jpg', '.jpeg')):
                    return os.path.join(folder, file)
        return None
    
    def process_blend_file(self, filepath):
        """Process a single blend file to assign previews"""
        try:
            # Load the blend file
            bpy.ops.wm.open_mainfile(filepath=filepath)
            folder = os.path.dirname(filepath)
            made_changes = False
            
            # Only check materials
            for material in bpy.data.materials:
                if material.asset_data:  # Check if it's marked as an asset
                    # Find corresponding preview file
                    preview_path = self.find_preview_file(folder, material.name)
                    
                    if preview_path:
                        print(f"Found preview for {material.name}: {preview_path}")
                        # Use new override system to assign preview
                        with bpy.context.temp_override(id=material):
                            bpy.ops.ed.lib_id_load_custom_preview(
                                filepath=preview_path
                            )
                        made_changes = True
            
            # Save only if changes were made
            if made_changes:
                bpy.ops.wm.save_mainfile()
                print(f"Saved changes to {filepath}")
            
            return True
            
        except Exception as e:
            print(f"Error processing {filepath}: {str(e)}")
            return False
    
    def execute(self, context):
        directory = self.directory
        processed_files = 0
        
        # Walk through all subdirectories
        for root, dirs, files in os.walk(directory):
            # Look for .blend files
            blend_files = [f for f in files if f.endswith('.blend')]
            
            if blend_files:
                for blend_file in blend_files:
                    filepath = os.path.join(root, blend_file)
                    if self.process_blend_file(filepath):
                        processed_files += 1
        
        self.report({'INFO'}, f"Processed {processed_files} files")
        return {'FINISHED'}

class DUMBTOOLS_PT_asset_tools(bpy.types.Panel):
    """Panel for asset preview tools"""
    bl_label = "Asset Tools"
    bl_space_type = 'FILE_BROWSER'
    bl_region_type = 'TOOLS'
    bl_category = "Tools"

    @classmethod
    def poll(cls, context):
        # Only show in asset browser
        return context.space_data.browse_mode == 'ASSETS'

    def draw(self, context):
        self.layout.operator(DUMBTOOLS_OT_assign_existing_previews.bl_idname)

def register():
    bpy.utils.register_class(DUMBTOOLS_OT_assign_existing_previews)
    bpy.utils.register_class(DUMBTOOLS_PT_asset_tools)
    # Remove the old draw_button registration
    # bpy.types.FILEBROWSER_PT_directory_path.append(draw_button)

def unregister():
    bpy.utils.unregister_class(DUMBTOOLS_OT_assign_existing_previews)
    bpy.utils.unregister_class(DUMBTOOLS_PT_asset_tools)
    # Remove the old draw_button unregistration
    # bpy.types.FILEBROWSER_PT_directory_path.remove(draw_button)

register()
