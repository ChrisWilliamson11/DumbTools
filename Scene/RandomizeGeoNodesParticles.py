# Tooltip: Randomize geometry nodes properties for particle objects and save multiple versions

import bpy
import random
import os
import time
import math
import re
from datetime import datetime
from bpy.types import Operator
from bpy.props import IntProperty
import mathutils

def _strip_seed_suffix(name: str) -> str:
    """Remove one or more trailing "_seed_<digits>" groups"""
    return re.sub(r"(?:_seed_\d+)+$", "", name)

def measure_bounds_across_frames(obj):
    """Measure object bounds across all frames and return dimension info"""
    scene = bpy.context.scene
    current_frame = scene.frame_current
    start_frame = scene.frame_start
    end_frame = scene.frame_end

    max_x_dimension = 0
    max_x_frame = start_frame
    max_x_bounds = None

    min_y_global = float('inf')
    max_y_global = float('-inf')
    y_bounds_frame = start_frame

    print(f"    Measuring bounds for {obj.name} across frames {start_frame}-{end_frame}")

    # Sample all frames for accurate measurement
    for frame in range(start_frame, end_frame + 1):
        scene.frame_set(frame)
        bpy.context.view_layer.update()

        # Get object bounds
        if obj.bound_box:
            # Calculate bounds in world space
            bbox_corners = [obj.matrix_world @ mathutils.Vector(corner) for corner in obj.bound_box]

            # X dimension tracking
            min_x = min(corner.x for corner in bbox_corners)
            max_x = max(corner.x for corner in bbox_corners)
            x_dimension = max_x - min_x

            if x_dimension > max_x_dimension:
                max_x_dimension = x_dimension
                max_x_frame = frame
                max_x_bounds = (min_x, max_x)

            # Y bounds tracking
            min_y = min(corner.y for corner in bbox_corners)
            max_y = max(corner.y for corner in bbox_corners)

            if min_y < min_y_global:
                min_y_global = min_y
                y_bounds_frame = frame
            if max_y > max_y_global:
                max_y_global = max_y
                y_bounds_frame = frame

    # Restore original frame
    scene.frame_set(current_frame)

    print(f"    Max X dimension: {max_x_dimension:.3f} at frame {max_x_frame}")
    print(f"    Y bounds: {min_y_global:.3f} to {max_y_global:.3f}")
    return max_x_dimension, max_x_frame, max_x_bounds, min_y_global, max_y_global, y_bounds_frame

def adjust_post_translation_for_bounds(modifier, obj, target_max_x=6.0, target_y_range=2.0):
    """Adjust PostTranslation X and Y to keep object bounds within limits"""
    # Measure current bounds
    max_x_dim, max_x_frame, max_x_bounds, min_y_global, max_y_global, y_bounds_frame = measure_bounds_across_frames(obj)

    adjustments_made = False

    # Find PostTranslation (Socket_14)
    if 'Socket_14' in modifier:
        current_post_trans = list(modifier['Socket_14'])

        # Adjust X dimension if needed (for mirrored objects, positive X makes it smaller)
        if max_x_dim > target_max_x:
            print(f"    X dimension {max_x_dim:.3f} exceeds {target_max_x}")

            # Try adjusting up to 5 times
            direction = 1  # Start with positive X (right)
            max_attempts = 5

            for attempt in range(max_attempts):
                excess = max_x_dim - target_max_x
                x_adjustment = (excess / 2) * direction

                current_post_trans[0] += x_adjustment
                modifier['Socket_14'] = current_post_trans
                bpy.context.view_layer.update()

                # Re-measure
                new_max_x_dim, _, _, _, _, _ = measure_bounds_across_frames(obj)

                print(f"    Attempt {attempt + 1}: Adjusted X by {x_adjustment:+.3f}, new dimension = {new_max_x_dim:.3f}")

                # Check if we improved
                if new_max_x_dim <= target_max_x:
                    print(f"    ✓ Success! X dimension now {new_max_x_dim:.3f} (under {target_max_x})")
                    adjustments_made = True
                    break
                elif new_max_x_dim < max_x_dim:
                    # We improved but not enough, continue in same direction
                    print(f"    Improved from {max_x_dim:.3f} to {new_max_x_dim:.3f}, trying again...")
                    max_x_dim = new_max_x_dim
                else:
                    # We made it worse! Undo and reverse direction
                    print(f"    Made it worse! Undoing and reversing direction...")
                    current_post_trans[0] -= x_adjustment  # Undo
                    direction *= -1  # Reverse direction
                    modifier['Socket_14'] = current_post_trans
                    bpy.context.view_layer.update()
                    max_x_dim, _, _, _, _, _ = measure_bounds_across_frames(obj)

            if not adjustments_made and new_max_x_dim > target_max_x:
                print(f"    ⚠ WARNING: Could not get X dimension under {target_max_x} after {max_attempts} attempts")
        else:
            print(f"    X dimension {max_x_dim:.3f} is already under {target_max_x}")

        # Adjust Y bounds if needed
        y_adjustment = 0
        if min_y_global < -target_y_range:
            # Min Y is too negative, shift everything up
            y_adjustment = -target_y_range - min_y_global
            print(f"    Min Y {min_y_global:.3f} is below -{target_y_range}, shifting up by {y_adjustment:.3f}")
        elif max_y_global > target_y_range:
            # Max Y is too positive, shift everything down
            y_adjustment = target_y_range - max_y_global
            print(f"    Max Y {max_y_global:.3f} is above +{target_y_range}, shifting down by {y_adjustment:.3f}")
        else:
            print(f"    Y bounds [{min_y_global:.3f}, {max_y_global:.3f}] are within ±{target_y_range}")

        if y_adjustment != 0:
            current_post_trans[1] += y_adjustment
            adjustments_made = True

        # Apply changes if any were made
        if adjustments_made:
            modifier['Socket_14'] = current_post_trans
            print(f"    New PostTranslation: X={current_post_trans[0]:.3f}, Y={current_post_trans[1]:.3f}, Z={current_post_trans[2]:.3f}")

        return adjustments_made
    else:
        print(f"    No Socket_14 (PostTranslation) found in modifier")
        return False

def get_particles_collection():
    """Get the 'Particles' collection"""
    particles_collection = bpy.data.collections.get('Particles')
    if not particles_collection:
        print("Error: Collection 'Particles' not found!")
        return None
    return particles_collection

def get_content_collection():
    """Get the 'Content' collection"""
    content_collection = bpy.data.collections.get('Content')
    if not content_collection:
        print("Error: Collection 'Content' not found!")
        return None
    return content_collection

def get_objects_with_geo_nodes(collection):
    """Get all objects in the collection that have geometry nodes modifiers"""
    objects_with_geo_nodes = []
    for obj in collection.objects:
        for modifier in obj.modifiers:
            if modifier.type == 'NODES' and modifier.node_group:
                objects_with_geo_nodes.append(obj)
                break
    return objects_with_geo_nodes

def find_image_texture_in_material(material):
    """Trace back through material nodes to find an image texture connected to Base Color"""
    if not material or not material.use_nodes:
        return None

    nodes = material.node_tree.nodes
    links = material.node_tree.links

    # Find the material output node
    output_node = None
    for node in nodes:
        if node.type == 'OUTPUT_MATERIAL':
            output_node = node
            break

    if not output_node:
        return None

    # Trace back from the Surface input of the output node
    visited = set()

    def trace_back(socket):
        """Recursively trace back through node connections"""
        if socket in visited:
            return None
        visited.add(socket)

        # Check if this socket is connected
        if not socket.is_linked:
            return None

        # Get the link
        link = socket.links[0]
        from_node = link.from_node

        # If we found an image texture node, return it
        if from_node.type == 'TEX_IMAGE':
            return from_node.image

        # Otherwise, continue tracing back through all inputs of this node
        for input_socket in from_node.inputs:
            if input_socket.type == 'RGBA' or input_socket.type == 'VECTOR':
                result = trace_back(input_socket)
                if result:
                    return result

        return None

    # Start tracing from the Surface input
    if output_node.inputs.get('Surface') and output_node.inputs['Surface'].is_linked:
        return trace_back(output_node.inputs['Surface'])

    return None

def get_fallback_image():
    """Get a random fallback image from Image_0.001 to Image_0.005"""
    fallback_images = []
    for i in range(1, 6):
        img_name = f"Image_0.{i:03d}"
        img = bpy.data.images.get(img_name)
        if img:
            fallback_images.append(img)

    if fallback_images:
        return random.choice(fallback_images)
    return None

def discover_modifier_inputs(modifier):
    """Discover all available inputs in a geometry nodes modifier with their labels"""
    available_inputs = {}
    socket_to_label = {}

    # Method 1: Get labels from node group interface
    if modifier.node_group and hasattr(modifier.node_group, 'interface'):
        try:
            if hasattr(modifier.node_group.interface, 'items_tree'):
                for item in modifier.node_group.interface.items_tree:
                    if hasattr(item, 'name') and hasattr(item, 'identifier'):
                        socket_to_label[item.identifier] = item.name
                        print(f"    Found interface item: {item.identifier} -> '{item.name}'")
        except Exception as e:
            print(f"    Error reading interface: {e}")

    # Method 2: Check modifier keys directly and map to labels
    for key in modifier.keys():
        if key not in ['name', 'type']:  # Skip built-in properties
            try:
                value = modifier[key]
                label = socket_to_label.get(key, key)  # Use label if available, otherwise use key
                available_inputs[key] = {
                    'type': type(value).__name__,
                    'value': value,
                    'label': label
                }
                print(f"    Found input '{key}' ('{label}'): {type(value).__name__} = {value}")
            except Exception as e:
                print(f"    Error reading {key}: {e}")

    return available_inputs

def randomize_geo_nodes_properties(obj, content_objects):
    """Randomize geometry nodes properties for the given object"""
    print(f"Randomizing properties for object: {obj.name}")

    for modifier in obj.modifiers:
        if modifier.type == 'NODES' and modifier.node_group:
            print(f"  Processing geometry nodes modifier: {modifier.name}")

            # Discover available inputs
            available_inputs = discover_modifier_inputs(modifier)

            if not available_inputs:
                print(f"    No inputs found in modifier")
                continue

            # Store original scale values to keep them equal
            scale_value = None

            # Process each available input using your exact socket mappings
            for input_key, input_info in available_inputs.items():
                try:
                    input_type = input_info['type']
                    input_label = input_info['label']
                    current_value = input_info['value']

                    # Use your exact socket mappings:
                    # Socket_13: Object (from Content collection)
                    if input_key == 'Socket_13' and content_objects and input_type == 'Object':
                        random_content_obj = random.choice(content_objects)
                        modifier[input_key] = random_content_obj
                        print(f"    Set Socket_13 (Object): {random_content_obj.name}")

                        # Also find and assign the image texture to Socket_6
                        assigned_image = None

                        # Try to find image from the object's material
                        if random_content_obj.active_material:
                            assigned_image = find_image_texture_in_material(random_content_obj.active_material)
                            if assigned_image:
                                print(f"      Found image texture in material: {assigned_image.name}")

                        # If no image found, use fallback
                        if not assigned_image:
                            assigned_image = get_fallback_image()
                            if assigned_image:
                                print(f"      Using fallback image: {assigned_image.name}")
                            else:
                                print(f"      Warning: No image found and no fallback available")

                        # Assign to Socket_6 if we have an image
                        if assigned_image and 'Socket_6' in modifier:
                            modifier['Socket_6'] = assigned_image
                            print(f"    Set Socket_6 (Image): {assigned_image.name}")

                    # Socket_2: StartFrame (randomize from 0-360)
                    elif input_key == 'Socket_2' and input_type in ['float', 'int']:
                        new_value = random.uniform(0, 360)
                        modifier[input_key] = new_value
                        print(f"    Set Socket_2 (StartFrame): {new_value:.3f}")

                    # Socket_7: InitialPosition (absolute values ±0.05 for all axes)
                    elif input_key == 'Socket_7' and input_type == 'IDPropertyArray':
                        original_pos = list(current_value)
                        print(f"    Original Socket_7 (InitialPosition): X={original_pos[0]:.3f}, Y={original_pos[1]:.3f}, Z={original_pos[2]:.3f}")

                        # Set absolute random values
                        new_pos = [
                            random.uniform(-0.05, 0.05),  # X
                            random.uniform(-0.05, 0.05),  # Y
                            random.uniform(-0.05, 0.05)   # Z
                        ]

                        modifier[input_key] = new_pos
                        print(f"    Set Socket_7 (InitialPosition): X={new_pos[0]:.3f}, Y={new_pos[1]:.3f}, Z={new_pos[2]:.3f}")

                    # Socket_11: InitialRotation (-45 to 45 degrees for all axes, convert to radians)
                    elif input_key == 'Socket_11' and input_type == 'IDPropertyArray':
                        new_rot_degrees = [random.uniform(-45, 45) for _ in range(3)]
                        new_rot_radians = [math.radians(deg) for deg in new_rot_degrees]
                        modifier[input_key] = new_rot_radians
                        print(f"    Set Socket_11 (InitialRotation): X={new_rot_degrees[0]:.1f}°, Y={new_rot_degrees[1]:.1f}°, Z={new_rot_degrees[2]:.1f}°")

                    # Socket_12: InitialScale (0.8-1.2, all axes equal)
                    elif input_key == 'Socket_12' and input_type == 'IDPropertyArray':
                        if scale_value is None:
                            scale_value = random.uniform(0.8, 1.2)
                        new_scale = [scale_value, scale_value, scale_value]
                        modifier[input_key] = new_scale
                        print(f"    Set Socket_12 (InitialScale): {scale_value:.3f} (all axes)")

                    # Socket_8: TranslationAnimation (-0.001 to 0.001 for each axis, different values)
                    elif input_key == 'Socket_8' and input_type == 'IDPropertyArray':
                        new_trans_anim = [random.uniform(-0.001, 0.001) for _ in range(3)]
                        modifier[input_key] = new_trans_anim
                        print(f"    Set Socket_8 (TranslationAnimation): X={new_trans_anim[0]:.6f}, Y={new_trans_anim[1]:.6f}, Z={new_trans_anim[2]:.6f}")

                    # Socket_9: RotationAnimation (-0.4 to 0.4 degrees for all axes, convert to radians)
                    elif input_key == 'Socket_9' and input_type == 'IDPropertyArray':
                        # Show current values first
                        current_rot_anim = list(current_value)
                        current_degrees = [math.degrees(rad) for rad in current_rot_anim]
                        print(f"    Current Socket_9 (RotationAnimation): X={current_degrees[0]:.1f}°, Y={current_degrees[1]:.1f}°, Z={current_degrees[2]:.1f}°")

                        new_rot_anim_degrees = [random.uniform(-0.4, 0.4) for _ in range(3)]
                        new_rot_anim_radians = [math.radians(deg) for deg in new_rot_anim_degrees]
                        modifier[input_key] = new_rot_anim_radians
                        print(f"    Set Socket_9 (RotationAnimation): X={new_rot_anim_degrees[0]:.3f}°, Y={new_rot_anim_degrees[1]:.3f}°, Z={new_rot_anim_degrees[2]:.3f}°")

                    # Socket_14: PostTranslation (-0.5 to +0.5 for each axis, separate values)
                    elif input_key == 'Socket_14' and input_type == 'IDPropertyArray':
                        new_post_trans = [random.uniform(-0.5, 0.5) for _ in range(3)]
                        modifier[input_key] = new_post_trans
                        print(f"    Set Socket_14 (PostTranslation): X={new_post_trans[0]:.3f}, Y={new_post_trans[1]:.3f}, Z={new_post_trans[2]:.3f}")

                except Exception as e:
                    print(f"    Error setting {input_key}: {str(e)}")

            # Force Geometry Nodes to re-evaluate (like in your working script)
            prev_view = modifier.show_viewport
            modifier.show_viewport = False
            bpy.context.view_layer.update()
            modifier.show_viewport = prev_view
            obj.update_tag()
            bpy.context.view_layer.update()

            print(f"    Forced geometry nodes re-evaluation for {obj.name}")

            # Check and adjust bounds to keep X dimension under 6 units and Y within ±2 units
            try:
                adjust_post_translation_for_bounds(modifier, obj, target_max_x=6.0, target_y_range=2.0)
            except Exception as e:
                print(f"    Warning: Could not adjust bounds for {obj.name}: {e}")

def run_variation(seed: int, particle_objects, content_objects):
    """Run a single variation with the given seed"""
    random.seed(seed)
    print(f"Using seed: {seed}")

    # Process each particle object
    for i, obj in enumerate(particle_objects):
        print(f"\n--- Processing object {i+1}/{len(particle_objects)}: {obj.name} ---")
        randomize_geo_nodes_properties(obj, content_objects)

    # Force scene update
    bpy.context.view_layer.update()

    # Save file with seed and set render output path
    if bpy.data.filepath:
        directory = os.path.dirname(bpy.data.filepath)
        base_name_full = os.path.splitext(os.path.basename(bpy.data.filepath))[0]
        base_name = _strip_seed_suffix(base_name_full) or base_name_full
    else:
        directory = os.path.expanduser("~/Desktop")
        base_name = "ParticleVariations"

    # Set render output path to include seed
    scene = bpy.context.scene
    original_render_path = scene.render.filepath
    scene.render.filepath = os.path.join(directory, f"{base_name}_seed_{seed}_")

    # Save a copy of the file with seed in the filename
    filename = f"{base_name}_seed_{seed}.blend"
    filepath = os.path.join(directory, filename)
    bpy.ops.wm.save_as_mainfile(filepath=filepath, copy=True)

    print(f"Saved copy as: {filepath}")
    print(f"Set render output to: {scene.render.filepath}")
    print(f"Randomization complete with seed: {seed}")

    # Restore the original render path for the current session
    scene.render.filepath = original_render_path

class SCENE_OT_RandomizeGeoNodesParticles(Operator):
    """Randomize geometry nodes properties for particle objects and save multiple variations"""
    bl_idname = "scene.randomize_geo_nodes_particles"
    bl_label = "Randomize Geo Nodes Particles"
    bl_options = {'REGISTER', 'UNDO'}

    variations: IntProperty(
        name="Number of Variations",
        description="Number of variations to generate",
        default=24,  # Changed from 12 to 24
        min=1,
        max=100
    )

    base_seed: IntProperty(
        name="Base Seed",
        description="Base seed for random generation (0 = use current time)",
        default=0,
        min=0
    )

    def execute(self, context):
        print("=== Randomize Geo Nodes Particles ===")

        # Set base seed
        if self.base_seed == 0:
            base_seed = int(datetime.now().timestamp())
        else:
            base_seed = self.base_seed

        print(f"Base seed: {base_seed}, variations: {self.variations}")

        # Get the Particles collection
        particles_collection = get_particles_collection()
        if not particles_collection:
            self.report({'ERROR'}, "Collection 'Particles' not found!")
            return {'CANCELLED'}

        # Get the Content collection
        content_collection = get_content_collection()
        if not content_collection:
            self.report({'ERROR'}, "Collection 'Content' not found!")
            return {'CANCELLED'}

        # Get objects with geometry nodes from Particles collection
        particle_objects = get_objects_with_geo_nodes(particles_collection)
        if not particle_objects:
            self.report({'WARNING'}, "No objects with geometry nodes found in 'Particles' collection!")
            return {'CANCELLED'}

        # Get objects from Content collection for random selection
        content_objects = list(content_collection.objects)
        if not content_objects:
            self.report({'WARNING'}, "No objects found in 'Content' collection!")
            return {'CANCELLED'}

        print(f"Found {len(particle_objects)} particle objects with geometry nodes")
        print(f"Found {len(content_objects)} content objects for randomization")

        # Run N variations
        for i in range(self.variations):
            print(f"\n=== VARIATION {i+1}/{self.variations} ===")
            run_variation(base_seed + i, particle_objects, content_objects)

        print(f"\n=== Process Complete ===")
        print(f"Generated {self.variations} variations with base seed {base_seed}")

        self.report({'INFO'}, f"Generated {self.variations} variations")
        return {'FINISHED'}

    def invoke(self, context, event):
        return context.window_manager.invoke_props_dialog(self)

def register():
    bpy.utils.register_class(SCENE_OT_RandomizeGeoNodesParticles)

def unregister():
    bpy.utils.unregister_class(SCENE_OT_RandomizeGeoNodesParticles)


register()
# Show the operator dialog
try:
    if bpy.context.window_manager:
        bpy.ops.scene.randomize_geo_nodes_particles('INVOKE_DEFAULT')
    else:
        print("No UI context available. Use F3 search menu and type 'Randomize Geo Nodes Particles' to run the operator.")
except Exception as e:
    print(f"Could not invoke operator dialog: {e}")
    print("Alternative ways to run:")
    print("1. Press F3 and search for 'Randomize Geo Nodes Particles'")
    print("2. Run: bpy.ops.scene.randomize_geo_nodes_particles('INVOKE_DEFAULT')")

