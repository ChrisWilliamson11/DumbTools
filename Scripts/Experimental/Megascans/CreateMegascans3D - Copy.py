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
    
    # Split by common delimiters and add all components
    components = []
    for part in name.replace('_', ' ').replace('-', ' ').split(' '):
        components.append(part.lower())
    
    print(f"Split components for {filename}: {components}")  # Debug print
    return components

def match_files_to_socket_names(files, socketnames):
    """Match files to socket names based on components."""
    print("\nMatching files to sockets:")  # Debug print
    for file in files:
        print(f"\nChecking file: {file}")  # Debug print
        file_components = split_into_components(file)
        
        for socket in socketnames:
            # For each socketname compare with filename
            match = set(socket[1]).intersection(set(file_components))
            if match:
                print(f"Matched {file} to socket {socket[0]} with tags {match}")  # Debug print
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
        lower_file = file.lower()
        if '_preview.' in lower_file and lower_file.endswith(('.jpg', '.png')):
            return os.path.join(directory, file)
    return None

def clear_scene():
    """Clear the current scene completely."""
    # Remove all objects
    for obj in bpy.data.objects:
        bpy.data.objects.remove(obj, do_unlink=True)
    
    # Clear materials
    for material in bpy.data.materials:
        bpy.data.materials.remove(material)
    
    # Clear images
    for image in bpy.data.images:
        bpy.data.images.remove(image)
        
    # Clear meshes
    for mesh in bpy.data.meshes:
        bpy.data.meshes.remove(mesh)
        
    # Clear textures
    for texture in bpy.data.textures:
        bpy.data.textures.remove(texture)
    
    # Force garbage collection
    gc.collect()

def wait_for_preview_generation():
    """Wait for preview generation to complete."""
    max_wait = 15  # Maximum wait time in seconds
    start_time = time.time()
    
    while bpy.app.is_job_running("RENDER_PREVIEW"):
        print(bpy.app.is_job_running("RENDER_PREVIEW"))
        if time.time() - start_time > max_wait:
            print("Preview generation timed out")
            return False
        time.sleep(0.1)  # Small delay to prevent excessive CPU usage
    
    return True

def find_3d_files(directory):
    """Find all OBJ and FBX files in the directory."""
    files = []
    for file in os.listdir(directory):
        lower_file = file.lower()
        if lower_file.endswith(('.obj', '.fbx')):
            files.append(os.path.join(directory, file))
    return files

def import_3d_file(file_path):
    """Import an OBJ or FBX file and return a single joined object."""
    print(f"\nImporting file: {file_path}")
    pre_import_objects = set(bpy.context.selected_objects)
    
    file_ext = os.path.splitext(file_path)[1].lower()
    
    if file_ext == '.obj':
        bpy.ops.wm.obj_import(
            filepath=file_path,
            use_split_objects=True,
            use_split_groups=True
        )
    elif file_ext == '.fbx':
        bpy.ops.import_scene.fbx(
            filepath=file_path,
            use_custom_normals=True,
            ignore_leaf_bones=True,
            automatic_bone_orientation=True
        )
    
    # Get newly imported objects
    imported_objects = set(bpy.context.selected_objects) - pre_import_objects
    
    if not imported_objects:
        print(f"No objects imported from {file_path}")
        return None
    
    # Filter for mesh objects only
    mesh_objects = [obj for obj in imported_objects if obj.type == 'MESH']
    if not mesh_objects:
        print(f"No mesh objects found in {file_path}")
        return None
        
    print(f"Found {len(mesh_objects)} mesh objects")
    
    # Clear all materials from mesh objects
    for obj in mesh_objects:
        obj.data.materials.clear()
    
    # First apply scale to all objects
    for obj in mesh_objects:
        obj.scale = (0.01, 0.01, 0.01)
        bpy.context.view_layer.objects.active = obj
        bpy.ops.object.transform_apply(location=False, rotation=False, scale=True)
    
    # If only one mesh object, no need to join
    if len(mesh_objects) == 1:
        joined_obj = mesh_objects[0]
    else:
        # Select all mesh objects for joining
        bpy.ops.object.select_all(action='DESELECT')
        for obj in mesh_objects:
            obj.select_set(True)
        
        # Set active object and join
        bpy.context.view_layer.objects.active = mesh_objects[0]
        bpy.ops.object.join()
        joined_obj = bpy.context.active_object
    
    # Rotate and apply the joined object
    joined_obj.rotation_euler.x = 1.5708  # 90 degrees in radians
    bpy.ops.object.transform_apply(location=True, rotation=True, scale=False)
    
    print(f"Successfully processed {file_path}")
    return joined_obj

def import_all_3d_files(directory):
    """Import all 3D files in directory and return final joined object."""
    imported_objects = []
    
    # Find and sort 3D files
    files = find_3d_files(directory)
    print(f"\nFound {len(files)} 3D files in {directory}:")
    for f in files:
        print(f"  - {os.path.basename(f)}")
    
    # Import each file and join its meshes
    for file_path in files:
        imported_obj = import_3d_file(file_path)
        if imported_obj:
            imported_objects.append(imported_obj)
    
    if not imported_objects:
        print("No objects were successfully imported")
        return None
    
    print(f"\nSuccessfully imported {len(imported_objects)} objects")
        
    # Space out the joined objects along X axis
    current_x = 0
    for obj in imported_objects:
        obj_width = obj.dimensions.x
        obj.location.x = current_x
        current_x += obj_width + 0.2  # Add gap between objects
    
    # If only one object, no need to join
    if len(imported_objects) == 1:
        return imported_objects[0]
    
    # Join all spaced objects into final mesh
    bpy.ops.object.select_all(action='DESELECT')
    for obj in imported_objects:
        obj.select_set(True)
    
    bpy.context.view_layer.objects.active = imported_objects[0]
    bpy.ops.object.join()
    
    final_obj = bpy.context.active_object
    print(f"Final joined object created: {final_obj.name}")
    return final_obj

def load_object_preview(obj, preview_path):
    """Load a preview image for an object asset."""
    if not preview_path:
        print("No preview path provided")
        return False
        
    print(f"Loading preview from: {preview_path}")
    
    # Ensure object is marked as an asset
    if not obj.asset_data:
        obj.asset_mark()
    obj.use_fake_user = True
    
    # Generate initial preview
    obj.asset_generate_preview()
    
    # Load custom preview
    if obj.preview:
        with bpy.context.temp_override(id=obj):
            bpy.ops.ed.lib_id_load_custom_preview(filepath=preview_path)
            print(f"Preview loaded for {obj.name}")
        return True
        
    print(f"Failed to load preview for {obj.name}")
    return False

def get_texture_files(directory):
    """Get all texture files in directory and categorize them."""
    textures = {}
    principled_tags = get_principled_tags()
    
    for file in os.listdir(directory):
        if not file.lower().endswith(('.jpg', '.png', '.exr')):
            continue
            
        # Skip preview images
        if '_preview' in file.lower():
            continue
            
        file_components = split_into_components(file)
        
        # Match against principled tags
        for tex_type, tags in principled_tags.items():
            tag_set = set(tags.split())
            if set(file_components).intersection(tag_set):
                textures[tex_type] = os.path.join(directory, file)
                break
    
    return textures

def setup_material_nodes(material, textures):
    """Set up material nodes with textures."""
    nodes, links = get_nodes_links(material)
    nodes.clear()
    
    # Create output and BSDF nodes
    output = nodes.new('ShaderNodeOutputMaterial')
    principled = nodes.new('ShaderNodeBsdfPrincipled')
    nodes.active = principled
    
    # Link principled to output
    links.new(principled.outputs['BSDF'], output.inputs['Surface'])
    
    # Create frames
    mapping_frame = nodes.new(type='NodeFrame')
    mapping_frame.label = 'Mapping'
    texture_frame = nodes.new(type='NodeFrame')
    texture_frame.label = 'Textures'
    
    # Create mapping nodes
    tex_coord = nodes.new('ShaderNodeTexCoord')
    mapping = nodes.new('ShaderNodeMapping')
    tex_coord.parent = mapping_frame
    mapping.parent = mapping_frame
    
    # Link mapping nodes
    links.new(tex_coord.outputs['UV'], mapping.inputs['Vector'])
    
    # Position base nodes
    output.location = (300, 300)
    principled.location = (0, 300)
    tex_coord.location = (-1200, 300)
    mapping.location = (-900, 300)
    
    # Track texture nodes for alignment
    texture_nodes = []
    
    # Create bump node first so we can connect to it later
    bump = nodes.new('ShaderNodeBump')
    bump.parent = texture_frame
    bump.inputs['Strength'].default_value = 0.0  # Set to 0
    
    for tex_type, tex_path in textures.items():
        tex_image = nodes.new('ShaderNodeTexImage')
        tex_image.image = bpy.data.images.load(tex_path)
        tex_image.parent = texture_frame
        texture_nodes.append(tex_image)
        
        # Set non-color data for non-color textures
        if tex_type not in ['base_color', 'emission']:
            tex_image.image.colorspace_settings.is_data = True
        
        # Handle specific texture types
        if tex_type == 'normal':
            normal_map = nodes.new('ShaderNodeNormalMap')
            normal_map.parent = texture_frame
            links.new(tex_image.outputs['Color'], normal_map.inputs['Color'])
            links.new(normal_map.outputs['Normal'], bump.inputs['Normal'])
            links.new(bump.outputs['Normal'], principled.inputs['Normal'])
            
        elif tex_type == 'bump':
            # Connect bump texture to the height input of the bump node
            links.new(tex_image.outputs['Color'], bump.inputs['Height'])
            
        elif tex_type == 'displacement':
            disp = nodes.new('ShaderNodeDisplacement')
            disp.parent = texture_frame
            disp.inputs['Scale'].default_value = 0.1  # Set displacement to 0.1
            links.new(tex_image.outputs['Color'], disp.inputs['Height'])
            links.new(disp.outputs['Displacement'], output.inputs['Displacement'])
            material.cycles.displacement_method = 'BOTH'
            
        else:
            # Direct connections for other texture types
            input_map = {
                'base_color': 'Base Color',
                'metallic': 'Metallic',
                'rough': 'Roughness',
                'specular': 'Specular IOR Level',
                'transmission': 'Transmission',
                'emission': 'Emission',
                'alpha': 'Alpha'
            }
            
            if tex_type in input_map:
                links.new(tex_image.outputs['Color'], principled.inputs[input_map[tex_type]])
        
        # Link mapping to all texture nodes
        links.new(mapping.outputs['Vector'], tex_image.inputs['Vector'])
    
    # Align texture nodes
    for i, tex_node in enumerate(texture_nodes):
        tex_node.location = (-600, 300 - (i * 300))

def create_material_from_json(json_path):
    # Load JSON data first
    print(f"Loading JSON data from: {json_path}")
    with open(json_path, 'r') as f:
        data = json.load(f)
    
    # Clean up the name
    material_name = data['name'].replace('/', '-')
    data['name'] = material_name
    
    # Get directory
    directory = os.path.dirname(json_path)
    
    # Clear everything before starting
    clear_scene()
    
    # Import all 3D files and get the final joined object
    imported_obj = import_all_3d_files(directory)
    if not imported_obj:
        print("No 3D files found or import failed")
        return None
        
    # Set the object name from JSON data
    imported_obj.name = data['name']

    # Create material
    material = bpy.data.materials.new(name=material_name)
    material.use_nodes = True
    
    # Get textures and set up material nodes
    textures = get_texture_files(directory)
    setup_material_nodes(material, textures)
    
    # Assign material to object
    if imported_obj.data.materials:
        imported_obj.data.materials[0] = material
    else:
        imported_obj.data.materials.append(material)

    # Mark as asset and load preview
    if not imported_obj.asset_data:
        imported_obj.asset_mark()
    imported_obj.use_fake_user = True
    
    # Find and load preview
    preview_path = find_preview_image(directory)
    if preview_path:
        load_object_preview(imported_obj, preview_path)
    else:
        print("No preview image found")

    return imported_obj

def clean_name(name):
    """Clean a name to be file system safe."""
    return name.replace('/', '-')

def save_material_to_blend(asset_name, directory):
    """Save the current object/material to a blend file."""
    try:
        # Clean up before saving
        # Remove any unused data
        for datablock in [bpy.data.meshes, bpy.data.materials, 
                          bpy.data.textures, bpy.data.images]:
            for item in datablock:
                if item.users == 0:
                    datablock.remove(item)
        
        # Force garbage collection
        gc.collect()
        
        # Ensure the directory exists
        os.makedirs(directory, exist_ok=True)
        
        # Clean the asset name
        clean_asset_name = clean_name(asset_name)
        
        blend_path = os.path.join(directory, f"{clean_asset_name}.blend")
        
        bpy.ops.wm.save_as_mainfile(
            filepath=blend_path,
            compress=True,
            relative_remap=True,
            copy=True
        )
        
        print(f"Successfully saved asset to {blend_path}")
        
        # Clean up after saving
        gc.collect()
            
    except Exception as e:
        print(f"Error saving blend file: {e}")
        import traceback
        traceback.print_exc()

        raise

# Main execution
def main():
    root_folder = r"F:\New folder\Downloaded\3d"
    print(f"Processing Megascans library at: {root_folder}")
    
    for dirpath, dirnames, filenames in os.walk(root_folder):
        gc.collect()
        
        # Check for OBJ or FBX file first
        if not any(f.lower().endswith(('.obj', '.fbx')) for f in filenames):
            print(f"Skipping folder (no OBJ/FBX file): {dirpath}")
            continue
            
        # Check for existing blend file
        if any(f.lower().endswith('.blend') for f in filenames):
            print(f"Skipping folder (blend file exists): {dirpath}")
            continue
        
        json_files = [f for f in filenames if f.endswith('.json')]
        if json_files:
            print(f"\nProcessing folder: {dirpath}")
            for json_file in json_files:
                json_path = os.path.join(dirpath, json_file)
                
                # Create material and assign to object
                result = create_material_from_json(json_path)
                
                if result:
                    try:
                        # Save the blend file
                        save_material_to_blend(result.name, dirpath)
                        print(f"Successfully processed and saved {json_path}")
                    except Exception as e:
                        print(f"Failed to save blend file: {e}")
                else:
                    print(f"Failed to process {json_path}")
                    
                # Additional cleanup after each file
                clear_scene()

main()
