# Tooltip: Save multiple versions of the blend file, one for each object in 'Bases' collection with individual render outputs

import bpy
import os
from bpy.types import Operator
from bpy.props import StringProperty, BoolProperty

def get_bases_collection():
    """Get the 'Bases' collection"""
    bases_collection = bpy.data.collections.get('Bases')
    if not bases_collection:
        print("Error: Collection 'Bases' not found!")
        return None
    return bases_collection

def set_object_visibility(obj, viewport_visible, render_visible):
    """Set viewport and render visibility for an object"""
    obj.hide_viewport = not viewport_visible
    obj.hide_render = not render_visible

def disable_all_bases_objects(bases_collection):
    """Disable all objects in the Bases collection for viewport and render"""
    for obj in bases_collection.objects:
        set_object_visibility(obj, False, False)

def enable_single_object(obj):
    """Enable a single object for viewport and render"""
    set_object_visibility(obj, True, True)

def get_current_render_filepath():
    """Get the current render output filepath"""
    return bpy.context.scene.render.filepath

def set_render_filepath(new_path):
    """Set the render output filepath"""
    bpy.context.scene.render.filepath = new_path

def get_blend_filename():
    """Get the current blend filename without extension"""
    blend_filepath = bpy.data.filepath
    if not blend_filepath:
        return "untitled"
    return os.path.splitext(os.path.basename(blend_filepath))[0]

def get_blend_directory():
    """Get the directory of the current blend file"""
    blend_filepath = bpy.data.filepath
    if not blend_filepath:
        return ""
    return os.path.dirname(blend_filepath)

def create_output_filename(base_filename, object_name, extension=""):
    """Create output filename by appending object name"""
    return f"{base_filename}_{object_name}{extension}"

class SCENE_OT_SaveMultipleVersions(Operator):
    """Save multiple versions of the blend file, one for each object in 'Bases' collection"""
    bl_idname = "scene.save_multiple_versions"
    bl_label = "Save Multiple Versions"
    bl_options = {'REGISTER', 'UNDO'}
    
    output_suffix: StringProperty(
        name="Output Suffix",
        description="Additional suffix to add to filenames (optional)",
        default=""
    )
    
    update_render_path: BoolProperty(
        name="Update Render Output Path",
        description="Update the render output path for each version",
        default=True
    )
    
    save_original: BoolProperty(
        name="Save Original First",
        description="Save the original file before creating versions",
        default=True
    )

    def execute(self, context):
        print("=== Save Multiple Versions ===")
        
        # Get the Bases collection
        bases_collection = get_bases_collection()
        if not bases_collection:
            self.report({'ERROR'}, "Collection 'Bases' not found!")
            return {'CANCELLED'}
        
        # Get objects from the collection
        objects_list = list(bases_collection.objects)
        if not objects_list:
            self.report({'WARNING'}, "No objects found in 'Bases' collection!")
            return {'CANCELLED'}
        
        print(f"Found {len(objects_list)} objects in 'Bases' collection")
        
        # Get current file info
        original_blend_filename = get_blend_filename()
        blend_directory = get_blend_directory()
        original_render_path = get_current_render_filepath()
        
        if not blend_directory:
            self.report({'ERROR'}, "Please save the blend file first!")
            return {'CANCELLED'}
        
        print(f"Original blend file: {original_blend_filename}")
        print(f"Blend directory: {blend_directory}")
        print(f"Original render path: {original_render_path}")
        
        # Save original file first if requested
        if self.save_original:
            print("Saving original file...")
            bpy.ops.wm.save_mainfile()
        
        # Store original visibility states
        original_visibility = {}
        for obj in objects_list:
            original_visibility[obj.name] = {
                'viewport': not obj.hide_viewport,
                'render': not obj.hide_render
            }
        
        # Process each object
        for i, obj in enumerate(objects_list):
            print(f"\n--- Processing object {i+1}/{len(objects_list)}: {obj.name} ---")
            
            # Disable all objects in Bases collection
            disable_all_bases_objects(bases_collection)
            
            # Enable only the current object
            enable_single_object(obj)
            
            # Create new filenames
            suffix = f"_{self.output_suffix}" if self.output_suffix else ""
            new_blend_filename = create_output_filename(original_blend_filename, obj.name, f"{suffix}.blend")
            new_blend_path = os.path.join(blend_directory, new_blend_filename)
            
            # Update render output path if requested
            if self.update_render_path:
                # Get the directory and base name of the original render path
                if original_render_path:
                    render_dir = os.path.dirname(original_render_path)
                    render_base = os.path.splitext(os.path.basename(original_render_path))[0]
                    render_ext = os.path.splitext(original_render_path)[1]
                    
                    new_render_filename = create_output_filename(render_base, obj.name, f"{suffix}{render_ext}")
                    new_render_path = os.path.join(render_dir, new_render_filename)
                else:
                    # If no original render path, create a default one
                    new_render_filename = create_output_filename("render", obj.name, f"{suffix}.png")
                    new_render_path = os.path.join(blend_directory, new_render_filename)
                
                set_render_filepath(new_render_path)
                print(f"  Updated render path: {new_render_path}")
            
            # Save the new blend file
            try:
                bpy.ops.wm.save_as_mainfile(filepath=new_blend_path)
                print(f"  Saved: {new_blend_filename}")
            except Exception as e:
                print(f"  Error saving {new_blend_filename}: {str(e)}")
                self.report({'ERROR'}, f"Failed to save {new_blend_filename}: {str(e)}")
        
        # Restore original visibility states
        print("\nRestoring original visibility states...")
        for obj in objects_list:
            if obj.name in original_visibility:
                vis = original_visibility[obj.name]
                set_object_visibility(obj, vis['viewport'], vis['render'])
        
        # Restore original render path
        if self.update_render_path:
            set_render_filepath(original_render_path)
            print(f"Restored original render path: {original_render_path}")
        
        print("\n=== Process Complete ===")
        print(f"Created {len(objects_list)} blend file versions")
        
        self.report({'INFO'}, f"Created {len(objects_list)} blend file versions")
        return {'FINISHED'}

    def invoke(self, context, event):
        return context.window_manager.invoke_props_dialog(self)

def register():
    bpy.utils.register_class(SCENE_OT_SaveMultipleVersions)

def unregister():
    bpy.utils.unregister_class(SCENE_OT_SaveMultipleVersions)


register()
# Show the operator dialog
try:
    if bpy.context.window_manager:
        bpy.ops.scene.save_multiple_versions('INVOKE_DEFAULT')
    else:
        print("No UI context available. Use F3 search menu and type 'Save Multiple Versions' to run the operator.")
except Exception as e:
    print(f"Could not invoke operator dialog: {e}")
    print("Alternative ways to run:")
    print("1. Press F3 and search for 'Save Multiple Versions'")
    print("2. Run: bpy.ops.scene.save_multiple_versions('INVOKE_DEFAULT')")
