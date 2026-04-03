import bpy
import os
import json
from mathutils import Vector
import gc  # Add garbage collector import
import time

def get_default_tags():
    """Return default tags if preferences are not available."""
    return {
        'normal': 'normal norm nrm nor nrml',
        'bump': 'bump bmp',
        'gloss': 'gloss glossy glossiness',
        'rough': 'rough roughness rgh',
        'displacement': 'displacement disp height heightmap dsp',
        'base_color': 'albedo diffuse diff base col color basecolor',
        'metallic': 'metallic metalness metal mtl',
        'specular': 'specular specularity spec spc',
        'transmission': 'transmission transparency',
        'emission': 'emission emissive emit',
        'alpha': 'alpha opacity',
        'ambient_occlusion': 'ao ambient occlusion ambientocclusion'
    }

def get_principled_tags():
    """Get principled tags from preferences or defaults."""
    # Always return default tags for now
    return get_default_tags()

def get_nodes_links(material):
    """Get nodes and links for a material."""
    if not material.use_nodes:
        material.use_nodes = True
    nodes = material.node_tree.nodes
    links = material.node_tree.links
    return nodes, links

def split_into_components(filename):
    """Split filename into components for matching."""
    # Remove extension
    name = os.path.splitext(filename)[0]
    # Split by common delimiters
    components = []
    for part in name.replace('_', ' ').replace('-', ' ').split(' '):
        components.append(part.lower())
    return components

def match_files_to_socket_names(files, socketnames):
    """Match files to socket names based on components."""
    for file in files:
        file_components = split_into_components(file)
        for socket in socketnames:
            # For each socketname compare with filename
            match = set(socket[1]).intersection(set(file_components))
            if match:
                socket[2] = file
                break

def extract_semantic_tags(json_data):
    """Extract semantic tags from Megascans JSON data."""
    tags = set()  # Using a set to avoid duplicates
    
    # Add tags from the JSON data
    if 'tags' in json_data:
        tags.update(tag.lower() for tag in json_data['tags'])
    
    # Add categories if present
    if 'categories' in json_data:
        tags.update(category.lower() for category in json_data['categories'])
    
    # Add type if present
    if 'type' in json_data:
        tags.add(json_data['type'].lower())
    
    # Add keywords if present
    if 'keywords' in json_data:
        tags.update(keyword.lower() for keyword in json_data['keywords'])
    
    # Add search tags if present
    if 'searchTags' in json_data:
        tags.update(tag.lower() for tag in json_data['searchTags'])
    
    # Filter out empty strings and None values
    tags = {tag for tag in tags if tag and isinstance(tag, str)}
    
    return list(tags)

def find_preview_image(directory):
    """Find the preview image in the directory."""
    for file in os.listdir(directory):
        if file.lower().endswith(('_preview.png', '_preview.jpg')):
            return os.path.join(directory, file)
    return None

def clear_scene():
    """Clear the current scene without resetting preferences."""
    # Remove all objects
    for obj in bpy.data.objects:
        bpy.data.objects.remove(obj, do_unlink=True)
    
    # Clear materials
    for material in bpy.data.materials:
        bpy.data.materials.remove(material)
    
    # Clear images
    for image in bpy.data.images:
        bpy.data.images.remove(image)
    
    # Clear brushes
    for brush in bpy.data.brushes:
        bpy.data.brushes.remove(brush)
    
    # Clear textures
    for texture in bpy.data.textures:
        bpy.data.textures.remove(texture)
    
    # Force garbage collection
    gc.collect()

def load_material_preview(material, preview_path):
    """Load a preview image for a material asset using the preview operator."""
    try:
        # Ensure material is marked as an asset first
        if not material.asset_data:
            material.asset_mark()
        material.use_fake_user = True
        
        # Generate preview first
        with bpy.context.temp_override(id=material):
            bpy.ops.ed.lib_id_generate_preview()
        
        # Now load the custom preview
        if material.preview:
            with bpy.context.temp_override(id=material):
                bpy.ops.ed.lib_id_load_custom_preview(filepath=str(preview_path))
            return True
        else:
            print("Failed to generate preview")
            return False
            
    except Exception as e:
        print(f"Failed to set preview image: {e}")
        import traceback
        traceback.print_exc()
        return False

def load_brush_preview(brush, preview_path):
    """Load a preview image for a brush asset using the preview operator."""
    try:
        # Ensure brush is marked as an asset first
        if not brush.asset_data:
            brush.asset_mark()
        brush.use_fake_user = True
        
        # Generate preview first
        with bpy.context.temp_override(id=brush):
            bpy.ops.ed.lib_id_generate_preview()
        
        # Now load the custom preview
        if brush.preview:
            with bpy.context.temp_override(id=brush):
                bpy.ops.ed.lib_id_load_custom_preview(filepath=str(preview_path))
            return True
        else:
            print("Failed to generate preview")
            return False
            
    except Exception as e:
        print(f"Failed to set preview image: {e}")
        import traceback
        traceback.print_exc()
        return False

def create_brush_from_json(json_path):
    try:
        # Load JSON data
        print(f"Loading JSON data from: {json_path}")
        with open(json_path, 'r') as f:
            data = json.load(f)
        
        # Clear existing scene first
        clear_scene()
        
        # Extract metadata
        brush_name = data['name']
        
        # Find the brush image in the directory
        directory = os.path.dirname(json_path)
        image_files = [f for f in os.listdir(directory) 
                      if f.lower().endswith(('.jpg', '.png', '.tif', '.tiff')) 
                      and 'brush' in f.lower()  # Look for 'brush' in filename
                      and '_preview' not in f.lower()  # Explicitly exclude preview
                      and 'preview' not in f.lower()]  # Also check for 'preview' without underscore
        
        if not image_files:
            print("No brush image found")
            return None
            
        # Load the first image as the brush texture
        image_path = os.path.join(directory, image_files[0])
        print('Found brush image:', image_files[0])  # Debug print
        brush_image = bpy.data.images.load(image_path)
        print('loading image for brush:', brush_name)
        print('image path:', image_path)
        #time.sleep(1)
        
        # Create new texture for the brush
        texture = bpy.data.textures.new(name=brush_name, type='IMAGE')
        texture.image = brush_image
        
        # Create new brush
        brush = bpy.data.brushes.new(name=brush_name)
        
        # Set brush settings
        brush.use_custom_icon = True
        brush.icon_filepath = image_path
        brush.curve_preset = 'CONSTANT'  # Set falloff to constant
        
        # Set up texture mask
        brush.mask_texture = texture
        brush.mask_texture_slot.map_mode = 'VIEW_PLANE'
        if hasattr(brush, 'use_texture_overlay'):
            brush.use_texture_overlay = True
        else:
            # For Blender 4.0+
            brush.texture_overlay_alpha = 100
        
        # Mark brush as an asset and ensure it has a fake user
        brush.asset_mark()
        brush.use_fake_user = True
        
        # Extract tags from JSON and add them to the asset
        if brush.asset_data:
            tags = extract_semantic_tags(data)
            for tag in tags:
                brush.asset_data.tags.new(tag)
        
        # Set preview image
        preview_path = find_preview_image(directory)
        if preview_path:
            if load_brush_preview(brush, preview_path):
                print("Preview image loaded successfully")
            else:
                print("Failed to load preview image")
        else:
            print("No preview image found")
        
        # Cleanup
        for image in bpy.data.images:
            if image.users == 0:
                bpy.data.images.remove(image)
        gc.collect()
        
        return brush

    except Exception as e:
        print(f"Error in create_brush_from_json: {e}")
        import traceback
        traceback.print_exc()
        return None

def main():
    root_folder = "F:/Megascans/Brushes"
    print(f"Processing Megascans library at: {root_folder}")
    
    for dirpath, dirnames, filenames in os.walk(root_folder):
        gc.collect()
        
        json_files = [f for f in filenames if f.endswith('.json')]
        blend_files = [f for f in filenames if f.endswith('.blend')]
        
        # Skip if blend files already exist in this folder
        if blend_files:
            print(f"Skipping folder (already processed): {dirpath}")
            continue
            
        if json_files:
            print(f"\nProcessing folder: {dirpath}")
            for json_file in json_files:
                json_path = os.path.join(dirpath, json_file)
                try:
                    brush = create_brush_from_json(json_path)
                    
                    if brush:
                        # Save individual blend file in the same directory
                        blend_path = os.path.join(dirpath, f"{brush.name}.blend")
                        bpy.ops.wm.save_as_mainfile(
                            filepath=blend_path,
                            compress=True,
                            relative_remap=True,
                            copy=True
                        )
                        print(f"Successfully saved brush to {blend_path}")
                    else:
                        print(f"Failed to create brush from {json_path}")
                    
                    gc.collect()
                
                except Exception as e:
                    print(f"Error processing {os.path.basename(json_path)}: {e}")
                    import traceback
                    traceback.print_exc()
                    
                # Additional cleanup
                for image in bpy.data.images:
                    if image.users == 0:
                        bpy.data.images.remove(image)
                gc.collect()

main()