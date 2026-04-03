# Tooltip: Randomize geometry nodes properties for Glasshouse objects and save multiple versions

import bpy
import random
import os
import colorsys
import re
from datetime import datetime
from bpy.types import Operator
from bpy.props import IntProperty

def _strip_seed_suffix(name: str) -> str:
    """Remove one or more trailing "_seed_<digits>" groups"""
    return re.sub(r"(?:_seed_\d+)+$", "", name)

def randomize_hue(color):
    """Randomize the hue of a color while keeping saturation and value"""
    # Convert RGB to HSV
    r, g, b = color[0], color[1], color[2]
    h, s, v = colorsys.rgb_to_hsv(r, g, b)

    # Randomize hue (0.0 to 1.0)
    new_h = random.random()

    # Convert back to RGB
    new_r, new_g, new_b = colorsys.hsv_to_rgb(new_h, s, v)

    # Return as 4-component color (RGBA), preserving alpha if it exists
    alpha = color[3] if len(color) > 3 else 1.0
    return [new_r, new_g, new_b, alpha]

def randomize_glasshouse_object(obj):
    """Randomize the 'Glass' object in 'Glasshouse' collection"""
    print(f"Randomizing Glasshouse object: {obj.name}")

    # Find the second modifier (WrapToMesh)
    if len(obj.modifiers) < 2:
        print(f"  Error: Object {obj.name} doesn't have at least 2 modifiers")
        return

    modifier = obj.modifiers[1]  # Second modifier (index 1)

    if modifier.type != 'NODES' or not modifier.node_group:
        print(f"  Error: Second modifier is not a geometry nodes modifier")
        return

    if modifier.name != 'WrapToMesh':
        print(f"  Warning: Second modifier is '{modifier.name}', expected 'WrapToMesh'")

    print(f"  Processing modifier: {modifier.name}")

    # Randomize Socket_25 and Socket_27 (color inputs)
    for socket_key in ['Socket_25', 'Socket_27']:
        if socket_key in modifier:
            current_color = list(modifier[socket_key])
            new_color = randomize_hue(current_color)
            modifier[socket_key] = new_color
            print(f"    Randomized {socket_key} (color): RGB({new_color[0]:.3f}, {new_color[1]:.3f}, {new_color[2]:.3f})")
        else:
            print(f"    Warning: {socket_key} not found in modifier")

    # Randomize Socket_28 and Socket_29 (seed values, integers 0-1000)
    for socket_key in ['Socket_28', 'Socket_29']:
        if socket_key in modifier:
            new_seed = random.randint(0, 1000)
            modifier[socket_key] = new_seed
            print(f"    Randomized {socket_key} (seed): {new_seed}")
        else:
            print(f"    Warning: {socket_key} not found in modifier")

    # Force update
    bpy.context.view_layer.update()

def randomize_newsurrounds_cube(obj):
    """Randomize the 'Cube' object in 'NewSurrounds' collection"""
    print(f"Randomizing NewSurrounds Cube: {obj.name}")

    # Find the first modifier (Geometry Nodes.001)
    if len(obj.modifiers) < 1:
        print(f"  Error: Object {obj.name} doesn't have any modifiers")
        return

    modifier = obj.modifiers[0]  # First modifier (index 0)

    if modifier.type != 'NODES' or not modifier.node_group:
        print(f"  Error: First modifier is not a geometry nodes modifier")
        return

    if modifier.name != 'Geometry Nodes.001':
        print(f"  Warning: First modifier is '{modifier.name}', expected 'Geometry Nodes.001'")

    print(f"  Processing modifier: {modifier.name}")

    # Randomize Socket_3
    if 'Socket_3' in modifier:
        # Check what type Socket_3 is
        current_value = modifier['Socket_3']
        value_type = type(current_value).__name__

        print(f"    Socket_3 current value: {current_value} (type: {value_type})")

        # Randomize based on type
        if value_type in ['float', 'int']:
            # For numeric values, randomize from 0 to 1000
            new_value = random.uniform(0, 1000)
            modifier['Socket_3'] = new_value
            print(f"    Randomized Socket_3: {new_value:.3f}")
        elif value_type == 'IDPropertyArray':
            # For arrays (vectors, colors, etc.)
            array_len = len(current_value)
            if array_len == 3:
                # Could be vector or RGB
                new_value = [random.uniform(0, 1000) for _ in range(3)]
            elif array_len == 4:
                # Could be RGBA
                new_value = [random.uniform(0, 1000) for _ in range(4)]
            else:
                new_value = [random.uniform(0, 1000) for _ in range(array_len)]
            modifier['Socket_3'] = new_value
            print(f"    Randomized Socket_3: {new_value}")
        else:
            print(f"    Warning: Unknown type for Socket_3, skipping")
    else:
        print(f"    Warning: Socket_3 not found in modifier")

    # Force update
    bpy.context.view_layer.update()

def get_glasshouse_collection():
    """Get the 'Glasshouse' collection"""
    glasshouse_collection = bpy.data.collections.get('Glasshouse')
    if not glasshouse_collection:
        print("Error: Collection 'Glasshouse' not found!")
        return None
    return glasshouse_collection

def get_newsurrounds_collection():
    """Get the 'NewSurrounds' collection"""
    newsurrounds_collection = bpy.data.collections.get('NewSurrounds')
    if not newsurrounds_collection:
        print("Error: Collection 'NewSurrounds' not found!")
        return None
    return newsurrounds_collection

def run_variation(seed: int, glass_obj, cube_obj):
    """Run a single variation with the given seed"""
    random.seed(seed)
    print(f"Using seed: {seed}")

    # Randomize the Glass object
    print(f"\n--- Processing Glass object ---")
    randomize_glasshouse_object(glass_obj)

    # Randomize the Cube object
    print(f"\n--- Processing Cube object ---")
    randomize_newsurrounds_cube(cube_obj)

    # Force scene update
    bpy.context.view_layer.update()

    # Save file with seed and set render output path
    if bpy.data.filepath:
        directory = os.path.dirname(bpy.data.filepath)
        base_name_full = os.path.splitext(os.path.basename(bpy.data.filepath))[0]
        base_name = _strip_seed_suffix(base_name_full) or base_name_full
    else:
        directory = os.path.expanduser("~/Desktop")
        base_name = "GlasshouseVariations"

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

class SCENE_OT_RandomizeGeoNodesGlasshouse(Operator):
    """Randomize geometry nodes properties for Glasshouse objects and save multiple variations"""
    bl_idname = "scene.randomize_geo_nodes_glasshouse"
    bl_label = "Randomize Geo Nodes Glasshouse"
    bl_options = {'REGISTER', 'UNDO'}

    variations: IntProperty(
        name="Number of Variations",
        description="Number of variations to generate",
        default=24,
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
        print("=== Randomize Geo Nodes Glasshouse ===")

        # Set base seed
        if self.base_seed == 0:
            base_seed = int(datetime.now().timestamp())
        else:
            base_seed = self.base_seed

        print(f"Base seed: {base_seed}, variations: {self.variations}")

        # Get the Glasshouse collection
        glasshouse_collection = get_glasshouse_collection()
        if not glasshouse_collection:
            self.report({'ERROR'}, "Collection 'Glasshouse' not found!")
            return {'CANCELLED'}

        # Get the NewSurrounds collection
        newsurrounds_collection = get_newsurrounds_collection()
        if not newsurrounds_collection:
            self.report({'ERROR'}, "Collection 'NewSurrounds' not found!")
            return {'CANCELLED'}

        # Get the Glass object from Glasshouse collection
        glass_obj = glasshouse_collection.objects.get('Glass')
        if not glass_obj:
            self.report({'ERROR'}, "Object 'Glass' not found in 'Glasshouse' collection!")
            return {'CANCELLED'}

        # Get the Cube object from NewSurrounds collection
        cube_obj = newsurrounds_collection.objects.get('Cube')
        if not cube_obj:
            self.report({'ERROR'}, "Object 'Cube' not found in 'NewSurrounds' collection!")
            return {'CANCELLED'}

        print(f"Found Glass object: {glass_obj.name}")
        print(f"Found Cube object: {cube_obj.name}")

        # Run N variations
        for i in range(self.variations):
            print(f"\n=== VARIATION {i+1}/{self.variations} ===")
            run_variation(base_seed + i, glass_obj, cube_obj)

        print(f"\n=== Process Complete ===")
        print(f"Generated {self.variations} variations with base seed {base_seed}")

        self.report({'INFO'}, f"Generated {self.variations} variations")
        return {'FINISHED'}

    def invoke(self, context, event):
        return context.window_manager.invoke_props_dialog(self)

def register():
    bpy.utils.register_class(SCENE_OT_RandomizeGeoNodesGlasshouse)

def unregister():
    bpy.utils.unregister_class(SCENE_OT_RandomizeGeoNodesGlasshouse)


register()
# Show the operator dialog
try:
    if bpy.context.window_manager:
        bpy.ops.scene.randomize_geo_nodes_glasshouse('INVOKE_DEFAULT')
    else:
        print("No UI context available. Use F3 search menu and type 'Randomize Geo Nodes Glasshouse' to run the operator.")
except Exception as e:
    print(f"Could not invoke operator dialog: {e}")
    print("Alternative ways to run:")
    print("1. Press F3 and search for 'Randomize Geo Nodes Glasshouse'")
    print("2. Run: bpy.ops.scene.randomize_geo_nodes_glasshouse('INVOKE_DEFAULT')")

