import bpy
import os
import gc

def replace_preview_with_jpeg(blend_path, jpeg_path):
    """Replace the material preview with a JPEG file."""
    try:
        # Open the blend file
        bpy.ops.wm.open_mainfile(filepath=blend_path)
        
        # Locate the material asset
        for material in bpy.data.materials:
            if material.asset_data:
                # Load the custom preview
                with bpy.context.temp_override(id=material):
                    bpy.ops.ed.lib_id_load_custom_preview(filepath=jpeg_path)
                print(f"Replaced preview for material: {material.name}")
        
        # Save the blend file
        bpy.ops.wm.save_as_mainfile(filepath=blend_path)
        print(f"Saved updated blend file: {blend_path}")
        
    except Exception as e:
        print(f"Error updating blend file: {e}")
        import traceback
        traceback.print_exc()

def main():
    root_folder = "F:/Megascans/Surfaces"
    print(f"Processing Megascans library at: {root_folder}")
    
    for dirpath, dirnames, filenames in os.walk(root_folder):
        blend_files = [f for f in filenames if f.endswith('.blend')]
        jpeg_files = [f for f in filenames if f.endswith('_preview.jpg')]
        
        for blend_file in blend_files:
            blend_path = os.path.join(dirpath, blend_file)
            for jpeg_file in jpeg_files:
                jpeg_path = os.path.join(dirpath, jpeg_file)
                replace_preview_with_jpeg(blend_path, jpeg_path)
        
        # Clean up after processing each directory
        gc.collect()

main()