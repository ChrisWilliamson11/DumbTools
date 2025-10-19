# Tooltip: Offset bitmaps in materials using a mapping node with a UI to control location, rotation, and scale
import bpy
from bpy.props import FloatVectorProperty, EnumProperty, BoolProperty


class OffsetBitmapsOperator(bpy.types.Operator):
    """Offset Bitmaps in Materials"""
    bl_idname = "material.offset_bitmaps"
    bl_label = "Offset Bitmaps in Materials"
    bl_options = {'REGISTER', 'UNDO'}

    # Mapping node properties
    mapping_type: EnumProperty(
        name="Type",
        description="Mapping type",
        items=[
            ('POINT', "Point", ""),
            ('TEXTURE', "Texture", ""),
            ('VECTOR', "Vector", ""),
            ('NORMAL', "Normal", ""),
        ],
        default='POINT'
    )

    location: FloatVectorProperty(
        name="Location",
        description="Location offset",
        default=(0.0, 0.0, 0.0),
        subtype='TRANSLATION'
    )

    rotation: FloatVectorProperty(
        name="Rotation",
        description="Rotation",
        default=(0.0, 0.0, 0.0),
        subtype='EULER'
    )

    scale: FloatVectorProperty(
        name="Scale",
        description="Scale",
        default=(1.0, 1.0, 1.0),
        subtype='XYZ'
    )

    def update_preset_toggle(self, context):
        """Callback when preset toggle is changed"""
        if self.preset_toggle:
            # Apply preset values
            self.location = (0.5, 0.5, 0.0)
            self.rotation = (0.0, 0.0, 0.0)
            self.scale = (0.5, 0.5, 1.0)
        else:
            # Apply default values
            self.location = (0.0, 0.0, 0.0)
            self.rotation = (0.0, 0.0, 0.0)
            self.scale = (1.0, 1.0, 1.0)

    preset_toggle: BoolProperty(
        name="Use Preset",
        description="Toggle between default (0,0,0 / 1,1,1) and preset (.5,.5,0 / .5,.5,1)",
        default=False,
        update=update_preset_toggle
    )

    def draw(self, context):
        layout = self.layout

        layout.prop(self, "mapping_type")
        layout.separator()

        layout.label(text="Location:")
        layout.prop(self, "location", text="")

        layout.label(text="Rotation:")
        layout.prop(self, "rotation", text="")

        layout.label(text="Scale:")
        layout.prop(self, "scale", text="")

        layout.separator()

        # Toggle button for preset
        row = layout.row()
        row.prop(self, "preset_toggle", text="Toggle Preset (.5,.5,0 / .5,.5,1)", toggle=True)

    def execute(self, context):

        # Process all materials
        processed_count = 0
        for mat in bpy.data.materials:
            if mat.use_nodes:
                if self.process_material(mat):
                    processed_count += 1

        self.report({'INFO'}, f"Processed {processed_count} material(s)")
        return {'FINISHED'}

    def process_material(self, material):
        """Process a single material to add mapping nodes to color bitmaps"""
        nodes = material.node_tree.nodes
        links = material.node_tree.links

        # Check if material should be processed
        # Include if: has 'color' in name, OR starts with 'colony_simpleMaterialSG', OR ends with 'aMaterialSG'
        # Exclude anything with 'graphics' in the name
        mat_name_lower = material.name.lower()
        has_graphics = 'graphics' in mat_name_lower

        is_color_material = 'color' in mat_name_lower
        is_colony_material = material.name.startswith('colony_simpleMaterialSG')
        is_a_material = 'aMaterialSG' in material.name

        if has_graphics or not (is_color_material or is_colony_material or is_a_material):
            return False

        image_nodes = [node for node in nodes if node.type == 'TEX_IMAGE']

        if not image_nodes:
            return False

        # Create or find texture coordinate node
        tex_coord = None
        for node in nodes:
            if node.type == 'TEX_COORD':
                tex_coord = node
                break

        if not tex_coord:
            tex_coord = nodes.new('ShaderNodeTexCoord')
            tex_coord.location = (-800, 0)

        # Create mapping node
        mapping = nodes.new('ShaderNodeMapping')
        mapping.location = (-600, 0)

        # Set mapping properties
        mapping.vector_type = self.mapping_type
        mapping.inputs['Location'].default_value = self.location
        mapping.inputs['Rotation'].default_value = self.rotation
        mapping.inputs['Scale'].default_value = self.scale

        # Connect texture coordinate to mapping
        links.new(tex_coord.outputs['UV'], mapping.inputs['Vector'])

        # Connect mapping to all image texture nodes
        for img_node in image_nodes:
            # Check if the vector input is already connected
            if img_node.inputs['Vector'].is_linked:
                # Remove existing link
                for link in img_node.inputs['Vector'].links:
                    links.remove(link)

            # Connect mapping to image node
            links.new(mapping.outputs['Vector'], img_node.inputs['Vector'])

        return True

    def invoke(self, context, event):
        return context.window_manager.invoke_props_dialog(self, width=400)


def register():
    bpy.utils.register_class(OffsetBitmapsOperator)


def unregister():
    bpy.utils.unregister_class(OffsetBitmapsOperator)



register()

# Test call
bpy.ops.material.offset_bitmaps('INVOKE_DEFAULT')
