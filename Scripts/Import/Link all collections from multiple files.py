import bpy
import os
from bpy.props import CollectionProperty, StringProperty
from bpy.types import Operator
from bpy_extras.io_utils import ImportHelper


class IMPORT_OT_append_collections(Operator, ImportHelper):
    """Append collections from selected blend files as instanced collections"""
    bl_idname = "import_scene.append_collections"
    bl_label = "Append Collections from Blend Files"
    bl_description = "Select blend files and append their collections as instanced collections"
    bl_options = {'REGISTER', 'UNDO'}

    # File browser properties
    filename_ext = ".blend"
    filter_glob: StringProperty(
        default="*.blend",
        options={'HIDDEN'},
        maxlen=255,
    )
    
    # Allow multiple file selection
    files: CollectionProperty(
        name="File Path",
        type=bpy.types.OperatorFileListElement,
    )
    
    directory: StringProperty(
        subtype='DIR_PATH',
    )

    def execute(self, context):
        """Execute the append operation"""
        if not self.files:
            self.report({'WARNING'}, "No files selected")
            return {'CANCELLED'}
        
        # Get the current scene
        current_scene = context.scene
        
        # Process each selected blend file
        for file_elem in self.files:
            filepath = os.path.join(self.directory, file_elem.name)
            
            if not os.path.exists(filepath):
                self.report({'WARNING'}, f"File not found: {filepath}")
                continue
            
            if not filepath.lower().endswith('.blend'):
                self.report({'WARNING'}, f"Not a blend file: {filepath}")
                continue
            
            try:
                self.append_collections_from_file(filepath, current_scene)
            except Exception as e:
                self.report({'ERROR'}, f"Failed to process {filepath}: {str(e)}")
        
        # Update the scene
        context.view_layer.update()
        
        self.report({'INFO'}, f"Successfully processed {len(self.files)} blend file(s)")
        return {'FINISHED'}

    def append_collections_from_file(self, filepath, target_scene):
        """Append all collections from a blend file as instanced collections"""

        # Get the filename without extension for naming
        filename = os.path.splitext(os.path.basename(filepath))[0]

        # First, we need to append the collections from the blend file
        with bpy.data.libraries.load(filepath, link=False) as (data_from, data_to):
            # Get all collection names from the source file
            collection_names = data_from.collections

            if not collection_names:
                self.report({'INFO'}, f"No collections found in {filepath}")
                return

            # Append all collections
            data_to.collections = collection_names

        # Now create collection instances for each appended collection
        for collection_name in collection_names:
            if collection_name in bpy.data.collections:
                source_collection = bpy.data.collections[collection_name]

                # Create a unique name for the instance
                instance_name = f"{filename}_{collection_name}_Instance"

                # Create an empty object to serve as the collection instance
                empty_obj = bpy.data.objects.new(
                    name=instance_name,
                    object_data=None
                )

                # Set the empty to instance the collection
                empty_obj.instance_type = 'COLLECTION'
                empty_obj.instance_collection = source_collection

                # Add the empty to the current scene
                target_scene.collection.objects.link(empty_obj)

                print(f"Created collection instance: {instance_name}")
            else:
                warning_msg = f"Collection '{collection_name}' not found after appending"
                self.report({'WARNING'}, warning_msg)

    def invoke(self, context, event):
        """Invoke the file browser"""
        context.window_manager.fileselect_add(self)
        return {'RUNNING_MODAL'}


def menu_func_import(self, context):
    """Add the operator to the import menu"""
    self.layout.operator(
        IMPORT_OT_append_collections.bl_idname,
        text="Append Collections as Instances"
    )


def register():
    """Register the addon"""
    try:
        bpy.utils.register_class(IMPORT_OT_append_collections)
        bpy.types.TOPBAR_MT_file_import.append(menu_func_import)
    except ValueError:
        # Class already registered
        pass


def unregister():
    """Unregister the addon"""
    try:
        bpy.types.TOPBAR_MT_file_import.remove(menu_func_import)
        bpy.utils.unregister_class(IMPORT_OT_append_collections)
    except (ValueError, RuntimeError):
        # Class not registered or already removed
        pass



# Unregister first in case it's already registered
unregister()
# Then register
register()
# Run the operator
bpy.ops.import_scene.append_collections('INVOKE_DEFAULT')
