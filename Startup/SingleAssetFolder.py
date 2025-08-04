import bpy
from bpy.types import Operator, Panel
from bpy_extras.io_utils import ImportHelper

class DUMBTOOLS_OT_browse_asset_folder(Operator, ImportHelper):
    """Select a folder to use as an asset library"""
    bl_idname = "dumbtools.browse_asset_folder"
    bl_label = "Browse Asset Folder"
    
    # Set up the file browser to select directories only
    directory: bpy.props.StringProperty(
        name="Directory",
        subtype='DIR_PATH'
    )
    
    filename_ext = ""
    use_filter_folder = True
    
    def execute(self, context):
        # Check if 'DumbAssets' library already exists
        if 'DumbAssets' not in bpy.context.preferences.filepaths.asset_libraries:
            # Create new asset library using the operator
            bpy.ops.preferences.asset_library_add()
            # Get reference to the newly added library
            new_lib = bpy.context.preferences.filepaths.asset_libraries[-1]
            new_lib.name = 'DumbAssets'
        
        # Get the library (either existing or newly created)
        lib = bpy.context.preferences.filepaths.asset_libraries['DumbAssets']
        
        # Set the path
        lib.path = self.directory
        
        # Switch the asset browser to the DumbAssets library
        context.space_data.params.asset_library_reference = 'DumbAssets'
        
        return {'FINISHED'}

class DUMBTOOLS_PT_asset_browser_tools(Panel):
    """Panel in Asset Browser's tools region"""
    bl_space_type = 'FILE_BROWSER'
    bl_region_type = 'TOOLS'
    bl_category = "Tool"
    bl_label = "DumbTools"
    
    @classmethod
    def poll(cls, context):
        # Only show in asset browser mode
        return context.space_data.browse_mode == 'ASSETS'
    
    def draw(self, context):
        layout = self.layout
        layout.operator("dumbtools.browse_asset_folder", text="Browse Asset Folder")

def register():
    bpy.utils.register_class(DUMBTOOLS_OT_browse_asset_folder)
    bpy.utils.register_class(DUMBTOOLS_PT_asset_browser_tools)

def unregister():
    bpy.utils.unregister_class(DUMBTOOLS_PT_asset_browser_tools)
    bpy.utils.unregister_class(DUMBTOOLS_OT_browse_asset_folder)

register()
