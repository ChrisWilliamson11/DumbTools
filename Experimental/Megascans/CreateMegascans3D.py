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
    """Clear the current scene completely, including all collections."""
    # Deselect everything to avoid context issues
    try:
        bpy.ops.object.select_all(action='DESELECT')
    except Exception:
        pass

    # Remove all objects
    for obj in list(bpy.data.objects):
        bpy.data.objects.remove(obj, do_unlink=True)

    # Remove all collections (not including the root scene collection)
    for coll in list(bpy.data.collections):
        try:
            bpy.data.collections.remove(coll)
        except Exception as e:
            print(f"Warning: could not remove collection {coll.name}: {e}")

    # Clear materials
    for material in list(bpy.data.materials):
        bpy.data.materials.remove(material)

    # Clear images
    for image in list(bpy.data.images):
        bpy.data.images.remove(image)

    # Clear meshes
    for mesh in list(bpy.data.meshes):
        bpy.data.meshes.remove(mesh)

    # Clear textures
    for texture in list(bpy.data.textures):
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

def import_fbx_as_meshes(file_path):
    """Import an FBX file and return the imported mesh objects (no transforms, no joins)."""
    print(f"\nImporting FBX: {file_path}")
    pre_objects = set(bpy.data.objects)

    bpy.ops.import_scene.fbx(
        filepath=file_path,
        use_custom_normals=True,
        ignore_leaf_bones=True,
        automatic_bone_orientation=True
    )

    imported_objects = [obj for obj in bpy.data.objects if obj not in pre_objects]
    mesh_objects = [obj for obj in imported_objects if obj.type == 'MESH']

    print(f"Imported {len(mesh_objects)} mesh(es) from {os.path.basename(file_path)}")
    return mesh_objects


def mark_meshes_and_collection_as_assets(meshes, collection_name):
    """Create a collection with the given meshes and mark both meshes and the collection as assets."""
    if not meshes:
        print("No meshes to mark as assets")
        return None

    # Create and link collection
    coll = bpy.data.collections.new(collection_name)
    bpy.context.scene.collection.children.link(coll)

    for obj in meshes:
        # Link to our collection if not already linked
        if obj.name not in [o.name for o in coll.objects]:
            try:
                coll.objects.link(obj)
            except Exception as e:
                print(f"Warning: could not link {obj.name} to collection {collection_name}: {e}")
        # Mark object as asset
        if not obj.asset_data:
            obj.asset_mark()
        obj.use_fake_user = True

    # Try to mark the collection itself as an asset (supported in newer Blender versions)
    try:
        if not coll.asset_data:
            coll.asset_mark()
        coll.use_fake_user = True
    except Exception as e:
        print(f"Note: Could not mark collection '{collection_name}' as an asset on this Blender version: {e}")

    return coll



def mark_assets_conditionally(meshes, base_name, all_imported=None):
    """If one mesh: mark the mesh as an asset.
    If multiple meshes: create a collection named after base_name, link ALL imported
    objects into it (meshes, empties, etc.), and mark the collection as an asset.
    """
    if not meshes:
        print("No meshes to mark")
        return None

    if len(meshes) == 1:
        obj = meshes[0]
        if not obj.asset_data:
            obj.asset_mark()
        obj.use_fake_user = True
        print(f"Marked mesh '{obj.name}' as asset")
        return obj

    # Multiple meshes -> collection asset
    coll_name = base_name
    coll = bpy.data.collections.new(coll_name)
    bpy.context.scene.collection.children.link(coll)

    to_link = all_imported if all_imported is not None else meshes
    for obj in to_link:
        if obj.name not in [o.name for o in coll.objects]:
            try:
                coll.objects.link(obj)
            except Exception as e:
                print(f"Could not link {obj.name} to '{coll_name}': {e}")

    try:
        if not coll.asset_data:
            coll.asset_mark()
        coll.use_fake_user = True
        print(f"Marked collection '{coll.name}' as asset with {len(meshes)} meshes")
    except Exception as e:
        print(f"Could not mark collection '{coll_name}' as asset: {e}")

    return coll


def import_fbx_collect_all(file_path):
    """Import FBX and return (all_imported_objects, mesh_objects).
    No transforms or joins are applied.
    """
    print(f"\nImporting FBX (collect all): {file_path}")
    pre_objects = set(bpy.data.objects)

    bpy.ops.import_scene.fbx(
        filepath=file_path,
        use_custom_normals=True,
        ignore_leaf_bones=True,
        automatic_bone_orientation=True
    )

    imported_objects = [obj for obj in bpy.data.objects if obj not in pre_objects]
    mesh_objects = [obj for obj in imported_objects if obj.type == 'MESH']

    print(f"Imported {len(imported_objects)} object(s), {len(mesh_objects)} mesh(es)")
    return imported_objects, mesh_objects




def import_usd_collect_all(file_path):
    """Import USD/USDA/USDC/USDZ and return (all_imported_objects, mesh_objects)."""
    print(f"\nImporting USD (collect all): {file_path}")
    pre_objects = set(bpy.data.objects)
    try:
        bpy.ops.wm.usd_import(filepath=file_path)
    except Exception as e:
        print(f"USD import failed for {file_path}: {e}")
        return [], []

    imported_objects = [obj for obj in bpy.data.objects if obj not in pre_objects]
    mesh_objects = [obj for obj in imported_objects if obj.type == 'MESH']
    print(f"Imported {len(imported_objects)} object(s), {len(mesh_objects)} mesh(es)")
    return imported_objects, mesh_objects




def import_obj_collect_all(file_path):
    """Import OBJ and return (all_imported_objects, mesh_objects)."""
    print(f"\nImporting OBJ (collect all): {file_path}")
    pre_objects = set(bpy.data.objects)
    try:
        try:
            # Newer OBJ importer
            bpy.ops.wm.obj_import(filepath=file_path)
        except AttributeError:
            # Fallback to legacy OBJ importer
            bpy.ops.import_scene.obj(filepath=file_path)
    except Exception as e:
        print(f"OBJ import failed for {file_path}: {e}")
        return [], []

    imported_objects = [obj for obj in bpy.data.objects if obj not in pre_objects]
    mesh_objects = [obj for obj in imported_objects if obj.type == 'MESH']
    print(f"Imported {len(imported_objects)} object(s), {len(mesh_objects)} mesh(es)")
    return imported_objects, mesh_objects

def import_source_collect_all(file_path):
    """Dispatch importer based on source extension (FBX/USD/OBJ)."""
    ext = os.path.splitext(file_path)[1].lower()
    if ext == '.fbx':
        return import_fbx_collect_all(file_path)
    if ext in ('.usd', '.usda', '.usdc', '.usdz'):
        return import_usd_collect_all(file_path)
    if ext == '.obj':
        return import_obj_collect_all(file_path)
    print(f"Unsupported source extension '{ext}' for {file_path}")
    return [], []

SPECIAL_SUFFIXES = {"base_mesh", "render", "raycast", "render_only", "shadowproxy", "working"}


def compute_blend_basename(src_path: str) -> str:
    """Return the base filename (without extension) for the .blend we will write,
    applying special rules for certain source basenames.

    If the source base name is a utility name (SPECIAL_SUFFIXES) and the immediate
    folder is named 'model' or 'models', we use the parent folder above that.
    """
    directory = os.path.dirname(src_path)
    folder = os.path.basename(directory)
    base = os.path.splitext(os.path.basename(src_path))[0]

    if base.lower() in SPECIAL_SUFFIXES:
        # If current folder is 'model' or 'models', go up one level for the folder name
        if folder.lower() in {"model", "models"}:
            parent_dir = os.path.dirname(directory)
            parent_name = os.path.basename(parent_dir) or folder
            folder = parent_name
        return f"{folder}-{base}"
    return base


def get_target_blend_path(src_path: str) -> str:
    directory = os.path.dirname(src_path)
    base_for_blend = compute_blend_basename(src_path)
    return os.path.join(directory, f"{base_for_blend}.blend")


def save_blend_for_source(src_path: str):
    """Save a compressed .blend next to the source, named using our rules.
    - If source base name is one of SPECIAL_SUFFIXES, name is '<folder>-<base>.blend'
    - Otherwise, '<base>.blend'
    Skips saving if the target .blend already exists.
    """
    blend_path = get_target_blend_path(src_path)

    if os.path.exists(blend_path):
        print(f"Skipping save (blend already exists): {blend_path}")
        return blend_path

    bpy.ops.wm.save_as_mainfile(
        filepath=blend_path,
        compress=True,
        relative_remap=True,
        copy=True
    )

    print(f"Saved blend: {blend_path}")
    return blend_path

# Main execution
# --- Progress log controls ---
CONTINUE_FROM_LOG = True  # Skip sources already listed in the log
CLEAR_LOG_ON_START = False  # Delete the log at startup


def _parse_log_line(line: str) -> str:
    line = line.strip()
    if not line:
        return ""
    parts = line.split("|", 2)
    if len(parts) >= 2:
        return parts[1]
    return line


def load_processed_sources(log_path: str) -> set:
    processed = set()
    try:
        with open(log_path, "r", encoding="utf-8", errors="ignore") as f:
            for ln in f:
                src = _parse_log_line(ln)
                if src:
                    processed.add(src)
    except FileNotFoundError:
        pass
    except Exception as e:
        print(f"Warning: could not read log '{log_path}': {e}")
    return processed


def log_progress(log_path: str, path: str, status: str, message: str = "") -> None:
    try:
        with open(log_path, "a", encoding="utf-8", errors="ignore") as f:
            f.write(f"{status}|{path}|{message}\n")
    except Exception as e:
        print(f"Warning: could not write progress log: {e}")


def get_all_assets_in_file():
    """Return a list of IDs in the current file that are marked as assets."""
    assets = []
    for coll in bpy.data.collections:
        if getattr(coll, "asset_data", None):
            assets.append(coll)
    for obj in bpy.data.objects:
        if getattr(obj, "asset_data", None):
            assets.append(obj)
    for mat in bpy.data.materials:
        if getattr(mat, "asset_data", None):
            assets.append(mat)
    return assets




def set_preview_lookdev_mode():
    """Attempt to switch viewport to LookDev/Material preview and use Eevee.
    Safe in background mode (no windows -> no-op).
    """
    # Set Eevee as render engine for material/LookDev-like shading
    try:
        bpy.context.scene.render.engine = 'BLENDER_EEVEE'
    except Exception as e:
        print(f"Could not set Eevee render engine: {e}")

    wm = getattr(bpy.context, 'window_manager', None)
    if not wm:
        return

    for window in wm.windows:
        screen = window.screen
        for area in screen.areas:
            if area.type != 'VIEW_3D':
                continue
            for space in area.spaces:
                if space.type != 'VIEW_3D':
                    continue
                shading = space.shading
                # Prefer 'MATERIAL' (modern LookDev). Fallback to 'LOOKDEV' on older versions.
                try:
                    shading.type = 'MATERIAL'
                except Exception:
                    try:
                        shading.type = 'LOOKDEV'
                    except Exception:
                        pass
                # Use scene lights/world for reliable material preview
                if hasattr(shading, 'use_scene_world'):
                    shading.use_scene_world = True
                if hasattr(shading, 'use_scene_lights'):
                    shading.use_scene_lights = True

def generate_previews_for_current_file() -> int:
    """Generate previews for all assets in the open file. Returns count generated."""
    # Try to ensure the viewport is in LookDev/Material mode and Eevee is active
    set_preview_lookdev_mode()

    assets = get_all_assets_in_file()
    if not assets:
        print("No assets found; skipping preview generation.")
        return 0

    print(f"Generating previews for {len(assets)} asset(s)...")
    count = 0
    for id_block in assets:
        try:
            id_block.asset_generate_preview()
            count += 1
        except Exception as e:
            print(f"Failed preview for '{getattr(id_block, 'name', '<unknown>')}': {e}")
    wait_for_preview_generation()
    return count


def main():
    """Recurse root. For each source (FBX/USD) lacking a corresponding .blend:
    - import as-is, mark asset(s) (single mesh -> mesh asset; multi -> collection asset with all imported objects),
    - find missing files from root,
    - generate previews for assets,
    - save one .blend next to the source file.
    """
    root_folder = r"H:\000_Projects\Goliath\00_Assets\Game\World Drops"
    print(f"Processing asset library at: {root_folder}")

    log_path = os.path.join(root_folder, "_CreateMegascans3D.log")
    if CLEAR_LOG_ON_START:
        try:
            os.remove(log_path)
            print(f"Cleared progress log: {log_path}")
        except FileNotFoundError:
            pass
        except Exception as e:
            print(f"Warning: could not clear log '{log_path}': {e}")

    # First pass: collect source files missing .blend
    to_process = []
    for dirpath, _, filenames in os.walk(root_folder):
        for name in filenames:
            lower = name.lower()
            if not lower.endswith(('.fbx', '.usd', '.usda', '.usdc', '.usdz', '.obj')):
                continue
            src_path = os.path.join(dirpath, name)
            blend_path = get_target_blend_path(src_path)
            if not os.path.exists(blend_path):
                to_process.append(src_path)

    # Apply continue-from-log filtering
    if CONTINUE_FROM_LOG:
        processed = load_processed_sources(log_path)
        if processed:
            before = len(to_process)
            to_process = [p for p in to_process if p not in processed]
            skipped = before - len(to_process)
            print(f"Continue-from-log: {skipped} already listed; {len(to_process)} pending")

    if not to_process:
        print("\n==============================")
        print("NO FILES TO PROCESS")
        print("==============================\n")
        return

    # Sort by file size ascending (smallest first)
    to_process.sort(key=lambda p: os.path.getsize(p))
    print(f"Will process {len(to_process)} source file(s), smallest first.")

    # Track sources that imported with zero meshes so you can review them later
    zero_mesh_sources = []


    for src_path in to_process:
        base_name = os.path.splitext(os.path.basename(src_path))[0]
        print(f"\nProcessing: {src_path}")
        clear_scene()
        gc.collect()

        all_imported, meshes = import_source_collect_all(src_path)
        if not meshes:
            print(f"No meshes imported from {src_path}; skipping.")
            zero_mesh_sources.append(src_path)
            log_progress(log_path, src_path, "ZERO_MESH", "no meshes imported")
            continue

        # Mark asset(s)
        mark_assets_conditionally(meshes, base_name, all_imported)

        # Try to relink any missing files (e.g., textures) by searching from root
        try:
            bpy.ops.file.find_missing_files(directory=root_folder, find_all=True)
        except Exception as e:
            print(f"find_missing_files failed: {e}")

        # Generate previews for any assets in this file
        generate_previews_for_current_file()

        try:
            saved_path = save_blend_for_source(src_path)
            print(f"Successfully saved .blend for {src_path}")
            log_progress(log_path, src_path, "OK", f"saved={saved_path}")
        except Exception as e:
            print(f"Failed to save blend for {src_path}: {e}")
            log_progress(log_path, src_path, "SAVE_FAIL", str(e))

        # Clean up before next source
        clear_scene()
        gc.collect()


    # Summary of zero-mesh sources
    if zero_mesh_sources:
        print("\n========= ZERO-MESH SOURCES =========")
        for p in zero_mesh_sources:
            print(f" - {p}")
        print("====================================\n")
    else:
        print("\nNo zero-mesh sources encountered.\n")


        clear_scene()
        gc.collect()


main()
