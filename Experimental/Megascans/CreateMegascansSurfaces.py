import bpy
import os
import json
from mathutils import Vector
import gc  # Add garbage collector import

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
        if file.lower().endswith('_preview.jpg'):
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

def create_material_from_json(json_path):
    try:
        # Load JSON data
        print(f"Loading JSON data from: {json_path}")
        with open(json_path, 'r') as f:
            data = json.load(f)
        
        # Handle different JSON structures
        maps = []
        if 'maps' in data:
            # Old structure
            maps = data['maps']
        elif 'components' in data:
            # New structure - convert components to maps format
            components = data['components']
            for comp in components:
                comp_type = comp['type']
                if 'uris' in comp and comp['uris']:
                    uri_data = comp['uris'][0]
                    if 'resolutions' in uri_data:
                        # Get highest resolution version
                        highest_res = uri_data['resolutions'][0]
                        # Get jpg format if available, otherwise first format
                        format_data = next(
                            (f for f in highest_res['formats'] if f['mimeType'] == 'image/jpeg'),
                            highest_res['formats'][0]
                        )
                        
                        maps.append({
                            'type': comp_type,
                            'uri': format_data['uri']
                        })
        
        if not maps:
            print("No texture maps found in JSON")
            return None
            
        # Extract metadata
        material_name = data['name']
        tags = data['tags']
        #print(f"Material Name: {material_name}, Tags: {tags}")

        # Clear existing materials and objects
        #print("Clearing existing materials and objects...")
        
        # Delete all objects
        for obj in bpy.data.objects:
            bpy.data.objects.remove(obj, do_unlink=True)
        
        # Clear materials
        for material in bpy.data.materials:
            bpy.data.materials.remove(material)
        
        # Create a new material
        #print(f"Creating new material: {material_name}")
        material = bpy.data.materials.new(name=material_name)
        material.use_nodes = True
        
        # Set the BSDF node as active
        nodes = material.node_tree.nodes
        bsdf_node = nodes.get('Principled BSDF')
        if bsdf_node:
            nodes.active = bsdf_node
            #print("Principled BSDF node set as active.")
        else:
            print("Error: Principled BSDF node not found.")
        
        # Create a temporary cube and assign the material
        #print("Creating a temporary cube and assigning the material...")
        
        # Create cube mesh
        mesh = bpy.data.meshes.new("Cube")
        cube = bpy.data.objects.new("Cube", mesh)
        
        # Create cube vertices, edges, and faces
        verts = [(1,1,1), (1,1,-1), (1,-1,1), (1,-1,-1), (-1,1,1), (-1,1,-1), (-1,-1,1), (-1,-1,-1)]
        edges = []
        faces = [(0,1,3,2), (4,5,7,6), (0,2,6,4), (1,3,7,5), (0,1,5,4), (2,3,7,6)]
        
        mesh.from_pydata(verts, edges, faces)
        mesh.update()
        
        # Link cube to scene
        bpy.context.scene.collection.objects.link(cube)
        
        # Assign material to cube
        if not cube.data.materials:
            cube.data.materials.append(material)
        
        #print("Cube created and material assigned.")
        
        # Prepare file paths and names for the operator
        directory = os.path.dirname(json_path)
        files = []
        first_valid_texture = None
        
        # Check for existing files in the directory
        existing_files = set(os.listdir(directory))
        #print(f"Existing files in directory: {existing_files}")
        
        for map in maps:
            texture_filename = map['uri']
            if texture_filename in existing_files:
                texture_path = os.path.join(directory, texture_filename)
                files.append(texture_filename)
                if not first_valid_texture:
                    first_valid_texture = texture_path
                print(f"Found texture: {texture_filename}")
        
        # Use the first valid texture path as the primary filepath
        absolute_texture_path = first_valid_texture
        #print(f"First valid texture path: {absolute_texture_path}")
        
        # Manually replicate the logic from the NWAddPrincipledSetup operator
        nodes, links = get_nodes_links(material)
        active_node = nodes.active

        # Debugging: Print available inputs on the active node
        #print("Active node inputs:", [input.name for input in active_node.inputs])

        # Filter textures names for texturetypes in filenames
        #print("\nGetting principled tags...")
        tags = get_principled_tags()
        #print(f"Tags: {tags}")
        
        normal_abbr = tags['normal'].split(' ')
        bump_abbr = tags['bump'].split(' ')
        gloss_abbr = tags['gloss'].split(' ')
        rough_abbr = tags['rough'].split(' ')
        
        #print(f"Normal abbreviations: {normal_abbr}")
        #print(f"Bump abbreviations: {bump_abbr}")
        #print(f"Gloss abbreviations: {gloss_abbr}")
        #print(f"Rough abbreviations: {rough_abbr}")
        
        socketnames = [
            ['Displacement', tags['displacement'].split(' '), None],
            ['Base Color', tags['base_color'].split(' '), None],
            ['Metallic', tags['metallic'].split(' '), None],
            ['Specular IOR Level', tags['specular'].split(' '), None],
            ['Roughness', rough_abbr + gloss_abbr, None],
            ['Bump', bump_abbr, None],
            ['Normal', normal_abbr, None],
            ['Transmission Weight', tags['transmission'].split(' '), None],
            ['Emission Color', tags['emission'].split(' '), None],
            ['Alpha', tags['alpha'].split(' '), None],
            ['Ambient Occlusion', tags['ambient_occlusion'].split(' '), None],
        ]
        
        #print("\nInitial socketnames:")
        for socket in socketnames:
            print(f"Socket: {socket}")

        #print("\nMatching files to socket names...")
        match_files_to_socket_names(files, socketnames)
        
        # Remove socketnames without found files
        valid_socketnames = [s for s in socketnames if s[2] and os.path.exists(os.path.join(directory, s[2]))]
        #print(f"\nValid socketnames after filtering: {valid_socketnames}")
        
        if not valid_socketnames:
            print('No matching images found')
            return None

        # Add found images
        #print('\nMatched Textures:')
        texture_nodes = []
        disp_texture = None
        ao_texture = None
        normal_node = None
        normal_node_texture = None
        bump_node = None
        bump_node_texture = None
        roughness_node = None
        for i, sname in enumerate(valid_socketnames):
            #print(f"Processing texture {i}: {sname[0]} - {sname[2]}")

            # DISPLACEMENT NODES
            if sname[0] == 'Displacement':
                disp_texture = nodes.new(type='ShaderNodeTexImage')
                img = bpy.data.images.load(os.path.join(directory, sname[2]))
                disp_texture.image = img
                disp_texture.label = 'Displacement'
                if disp_texture.image:
                    disp_texture.image.colorspace_settings.is_data = True

                # Add displacement offset nodes
                disp_node = nodes.new(type='ShaderNodeDisplacement')
                disp_node.inputs['Scale'].default_value = 0.1  # Set displacement strength to 0.1
                
                # Align the Displacement node under the active Principled BSDF node
                disp_node.location = active_node.location + Vector((100, -700))
                if disp_node.inputs and disp_texture.outputs:
                    links.new(disp_node.inputs[0], disp_texture.outputs[0])

                # Find output node
                output_node = [n for n in nodes if n.bl_idname == 'ShaderNodeOutputMaterial']
                if output_node and disp_node.outputs:
                    if not output_node[0].inputs[2].is_linked:
                        links.new(output_node[0].inputs[2], disp_node.outputs[0])

                # Set material settings to use both displacement and bump
                material.displacement_method = 'BOTH'
                


                continue

            # BUMP NODES
            elif sname[0] == 'Bump':
                # Test if new texture node is bump map
                fname_components = split_into_components(sname[2])
                match_bump = set(bump_abbr).intersection(set(fname_components))
                if match_bump:
                    # If Bump add bump node in between
                    bump_node_texture = nodes.new(type='ShaderNodeTexImage')
                    img = bpy.data.images.load(os.path.join(directory, sname[2]))
                    img.colorspace_settings.is_data = True
                    bump_node_texture.image = img
                    bump_node_texture.label = 'Bump'

                    # Add bump node and set strength to 0
                    bump_node = nodes.new(type='ShaderNodeBump')
                    bump_node.inputs['Strength'].default_value = 0.0  # Set bump strength to 0
                    if bump_node.inputs and bump_node_texture.outputs:
                        links.new(bump_node.inputs[2], bump_node_texture.outputs[0])
                    if active_node.inputs and bump_node.outputs:
                        links.new(active_node.inputs['Normal'], bump_node.outputs[0])
                continue

            # NORMAL NODES
            elif sname[0] == 'Normal':
                # Test if new texture node is normal map
                fname_components = split_into_components(sname[2])
                match_normal = set(normal_abbr).intersection(set(fname_components))
                if match_normal:
                    # If Normal add normal node in between
                    normal_node_texture = nodes.new(type='ShaderNodeTexImage')
                    img = bpy.data.images.load(os.path.join(directory, sname[2]))
                    img.colorspace_settings.is_data = True
                    normal_node_texture.image = img
                    normal_node_texture.label = 'Normal'

                    # Add normal node
                    normal_node = nodes.new(type='ShaderNodeNormalMap')
                    if normal_node.inputs and normal_node_texture.outputs:
                        links.new(normal_node.inputs[1], normal_node_texture.outputs[0])
                    # Connect to bump node if it was created before, otherwise to the BSDF
                    if bump_node is None and active_node.inputs and normal_node.outputs:
                        links.new(active_node.inputs['Normal'], normal_node.outputs[0])
                    elif bump_node.inputs and normal_node.outputs:
                        links.new(bump_node.inputs['Normal'], normal_node.outputs[0])
                continue

            # AMBIENT OCCLUSION TEXTURE
            elif sname[0] == 'Ambient Occlusion':
                ao_texture = nodes.new(type='ShaderNodeTexImage')
                img = bpy.data.images.load(os.path.join(directory, sname[2]))
                ao_texture.image = img
                ao_texture.label = sname[0]
                if ao_texture.image:
                    ao_texture.image.colorspace_settings.is_data = True

                continue

            if not active_node.inputs[sname[0]].is_linked:
                # No texture node connected -> add texture node with new image
                texture_node = nodes.new(type='ShaderNodeTexImage')
                img = bpy.data.images.load(os.path.join(directory, sname[2]))
                texture_node.image = img

                if sname[0] == 'Roughness':
                    # Test if glossy or roughness map
                    fname_components = split_into_components(sname[2])
                    match_rough = set(rough_abbr).intersection(set(fname_components))
                    match_gloss = set(gloss_abbr).intersection(set(fname_components))

                    if match_rough and active_node.inputs and texture_node.outputs:
                        # If Roughness nothing to do
                        links.new(active_node.inputs[sname[0]], texture_node.outputs[0])

                    elif match_gloss:
                        # If Gloss Map add invert node
                        invert_node = nodes.new(type='ShaderNodeInvert')
                        if invert_node.inputs and texture_node.outputs:
                            links.new(invert_node.inputs[1], texture_node.outputs[0])

                        if active_node.inputs and invert_node.outputs:
                            links.new(active_node.inputs[sname[0]], invert_node.outputs[0])
                        roughness_node = texture_node

                else:
                    # This is a simple connection Texture --> Input slot
                    if active_node.inputs and texture_node.outputs:
                        links.new(active_node.inputs[sname[0]], texture_node.outputs[0])

                # Use non-color except for color inputs
                if sname[0] not in ['Base Color', 'Emission Color'] and texture_node.image:
                    texture_node.image.colorspace_settings.is_data = True

            else:
                # If already texture connected. add to node list for alignment
                texture_node = active_node.inputs[sname[0]].links[0].from_node

            # These are all connected texture nodes
            texture_nodes.append(texture_node)
            texture_node.label = sname[0]

        if disp_texture:
            texture_nodes.append(disp_texture)
        if bump_node_texture:
            texture_nodes.append(bump_node_texture)
        if normal_node_texture:
            texture_nodes.append(normal_node_texture)

        if ao_texture:
            # We want the ambient occlusion texture to be the top most texture node
            texture_nodes.insert(0, ao_texture)

        # Alignment
        print("Aligning texture nodes...")
        for i, texture_node in enumerate(texture_nodes):
            offset = Vector((-550, (i * -280) + 200))
            texture_node.location = active_node.location + offset

        if normal_node:
            # Extra alignment if normal node was added
            normal_node.location = normal_node_texture.location + Vector((300, 0))

        if bump_node:
            # Extra alignment if bump node was added
            bump_node.location = bump_node_texture.location + Vector((300, 0))

        if roughness_node:
            # Alignment of invert node if glossy map
            invert_node.location = roughness_node.location + Vector((300, 0))

        # Add texture input + mapping
        print("Adding texture input and mapping nodes...")
        mapping = nodes.new(type='ShaderNodeMapping')
        mapping.location = active_node.location + Vector((-1050, 0))
        if len(texture_nodes) > 1:
            # If more than one texture add reroute node in between
            reroute = nodes.new(type='NodeReroute')
            texture_nodes.append(reroute)
            tex_coords = Vector((texture_nodes[0].location.x,
                                 sum(n.location.y for n in texture_nodes) / len(texture_nodes)))
            reroute.location = tex_coords + Vector((-50, -120))
            for texture_node in texture_nodes:
                if texture_node.inputs and reroute.outputs:
                    links.new(texture_node.inputs[0], reroute.outputs[0])
            if reroute.inputs and mapping.outputs:
                links.new(reroute.inputs[0], mapping.outputs[0])
        else:
            if texture_nodes[0].inputs and mapping.outputs:
                links.new(texture_nodes[0].inputs[0], mapping.outputs[0])

        # Connect texture_coordinates to mapping node
        texture_input = nodes.new(type='ShaderNodeTexCoord')
        texture_input.location = mapping.location + Vector((-200, 0))
        if mapping.inputs and texture_input.outputs:
            links.new(mapping.inputs[0], texture_input.outputs[2])

        # Create frame around tex coords and mapping
        print("Creating frames around nodes...")
        frame = nodes.new(type='NodeFrame')
        frame.label = 'Mapping'
        mapping.parent = frame
        texture_input.parent = frame
        frame.update()

        # Create frame around texture nodes
        frame = nodes.new(type='NodeFrame')
        frame.label = 'Textures'
        for tnode in texture_nodes:
            tnode.parent = frame
        frame.update()

        # Just to be sure
        active_node.select = False
        nodes.update()
        links.update()

        # Mark as asset and add tags
        #print("Marking material as asset...")
        try:
            material.asset_mark()
        except Exception as e:
            print(f"Failed to mark as asset: {e}")
            return None
        
        # Extract and add semantic tags
        semantic_tags = extract_semantic_tags(data)
        if semantic_tags:
            #print("Adding semantic tags to asset...")
            for tag in semantic_tags:
                try:
                    material.asset_data.tags.new(tag)
                    #print(f"Added tag: {tag}")
                except Exception as e:
                    print(f"Failed to add tag '{tag}': {e}")
        
        # Set preview image
        directory = os.path.dirname(json_path)
        preview_path = find_preview_image(directory)
        if preview_path:
            #print(f"Setting preview image from: {preview_path}")
            if load_material_preview(material, preview_path):
                print("Preview image loaded successfully")
            else:
                print("Failed to load preview image")
        else:
            print("No preview image found")
        
        # Add cleanup after loading images
        for image in bpy.data.images:
            if image.users == 0:
                bpy.data.images.remove(image)
        gc.collect()
        
        return material

    except Exception as e:
        print(f"Error in create_material_from_json: {e}")
        import traceback
        traceback.print_exc()
        return None

def save_material_to_blend(material_name, directory):
    """Save the current material to a blend file."""
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
        
        blend_path = os.path.join(directory, f"{material_name}.blend")
        #print(f"Saving material to: {blend_path}")
        
        # Save with relative paths
        bpy.ops.wm.save_as_mainfile(
            filepath=blend_path,
            compress=True,
            relative_remap=True,
            copy=True
        )
        
        print(f"Successfully saved material to {blend_path}")
        
        # Clean up after saving
        gc.collect()
        
    except Exception as e:
        print(f"Error saving blend file: {e}")
        import traceback
        traceback.print_exc()
        raise  # Re-raise the exception to be caught by the main try-except block

# Main execution
def main():
    root_folder = "F:/Megascans/Surfaces"
    print(f"Processing Megascans library at: {root_folder}")
    
    for dirpath, dirnames, filenames in os.walk(root_folder):
        # Force garbage collection at start of each directory
        gc.collect()
        
        json_files = [f for f in filenames if f.endswith('.json')]
        
        if json_files:
            # Check if there's already a .blend file in this directory
            blend_files = [f for f in filenames if f.endswith('.blend')]
            if blend_files:
                print(f"Skipping folder (blend file exists): {dirpath}")
                continue
                
            print(f"\nProcessing folder: {dirpath}")
            for json_file in json_files:
                json_path = os.path.join(dirpath, json_file)
                try:
                    # Clear scene and force garbage collection
                    clear_scene()
                    
                    # Create material
                    material = create_material_from_json(json_path)
                    
                    if material:
                        try:
                            save_material_to_blend(material.name, dirpath)
                            print(f"Successfully processed {json_path}")
                        except Exception as e:
                            print(f"Failed to save material blend file: {e}")
                    else:
                        print(f"Failed to create material from {json_path}")
                    
                    # Force garbage collection after processing each file
                    gc.collect()
                
                except Exception as e:
                    print(f"Error processing {os.path.basename(json_path)}: {e}")
                    import traceback
                    traceback.print_exc()
                    
                # Additional cleanup after each file
                for image in bpy.data.images:
                    if image.users == 0:
                        bpy.data.images.remove(image)
                for material in bpy.data.materials:
                    if material.users == 0:
                        bpy.data.materials.remove(material)
                gc.collect()

main()