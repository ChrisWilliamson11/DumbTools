# Tooltip:  Select a plane with an image on it & select the image in the material editor - it will scale the plane to the aspect ration of the image
import bpy

# Ensure you're in object mode
bpy.ops.object.mode_set(mode='OBJECT')

# Get the active object
obj = bpy.context.active_object

# Ensure the object is a mesh and has a material with a texture node
if obj.type == 'MESH' and obj.material_slots:
    mat = obj.material_slots[0].material

    if mat.use_nodes:
        nodes = mat.node_tree.nodes
        image_node = next((node for node in nodes if node.type == 'TEX_IMAGE' and node.select), None)

        if image_node and image_node.image:
            image = image_node.image
            img_width, img_height = image.size[0], image.size[1]
            aspect_ratio = img_width / img_height

            # Apply scale to ensure dimensions are accurate
            bpy.ops.object.transform_apply(location=False, rotation=False, scale=True)

            # Get current dimensions
            current_aspect_ratio = obj.dimensions.x / obj.dimensions.y if obj.dimensions.y != 0 else 0

            # Determine which dimension to adjust based on the current and target aspect ratios
            if current_aspect_ratio > aspect_ratio:
                # Current is wider than it should be: adjust X based on Y
                obj.dimensions.x = obj.dimensions.y * aspect_ratio
            else:
                # Current is narrower than it should be: adjust Y based on X
                obj.dimensions.y = obj.dimensions.x / aspect_ratio

            print
