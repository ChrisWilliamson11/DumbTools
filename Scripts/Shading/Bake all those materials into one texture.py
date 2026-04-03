# Tooltip: Given an object with multiple materials assigned, will bake them all to 1 PBR texture
import bpy

class BakeDialogOperator(bpy.types.Operator):
    bl_idname = "object.bake_dialog_operator"
    bl_label = "Bake All Materials into One"

    # Property for user input
    resolution: bpy.props.IntProperty(
        name="Resolution",
        description="Resolution of the image (both width and height)",
        default=1024,
        min=256,
        max=8192
    )

    def execute(self, context):
        main(context, self.resolution)
        return {'FINISHED'}

    def invoke(self, context, event):
        return context.window_manager.invoke_props_dialog(self)

def main(context, resolution):
    original_samples = bpy.context.scene.cycles.samples
    bpy.context.scene.cycles.samples = 1

    if not bpy.context.selected_objects:
        print("No object selected")
        return

    obj = bpy.context.active_object
    if obj.type != 'MESH':
        print("Selected object is not a mesh")
        return

    uv_map_name = "BakeUVMap"
    new_uv_map = obj.data.uv_layers.new(name=uv_map_name)
    #new_uv_map.active_render = True
    new_uv_map.active = True
    bpy.context.view_layer.objects.active = obj
    bpy.ops.object.mode_set(mode='EDIT')
    bpy.ops.mesh.select_all(action='SELECT')
    bpy.ops.uv.smart_project()
    bpy.ops.object.mode_set(mode='OBJECT')

    # Create a new blank image for baking
    image_name = "BakedTexture"
    new_image = bpy.data.images.new(image_name, width=resolution, height=resolution)

    # Iterate over all materials and set the new image as the bake target
    for mat in obj.data.materials:
        if not mat.use_nodes:
            continue

        nodes = mat.node_tree.nodes
        img_tex_node = nodes.new(type='ShaderNodeTexImage')
        img_tex_node.image = new_image
        img_tex_node.select = True
        nodes.active = img_tex_node

    # Bake settings
    bpy.context.scene.cycles.bake_type = 'DIFFUSE'
    bpy.context.scene.render.bake.use_selected_to_active = False
    bpy.context.scene.render.bake.use_clear = True
    bpy.context.scene.render.bake.use_pass_direct = False
    bpy.context.scene.render.bake.use_pass_indirect = False
    bpy.context.scene.render.bake.use_pass_color = True

    # Perform baking
    bpy.ops.object.bake('INVOKE_DEFAULT')

    # Restore the original render samples
    #bpy.context.scene.cycles.samples = original_samples

def register():
    # Check if the class is already registered
    if "BakeDialogOperator" not in bpy.types.Operator.__subclasses__():
        bpy.utils.register_class(BakeDialogOperator)
    else:
        print("BakeDialogOperator is already registered")

# Unregister function remains the same
def unregister():
    if "BakeDialogOperator" in bpy.types.Operator.__subclasses__():
        bpy.utils.unregister_class(BakeDialogOperator)


register()

# Test call
bpy.ops.object.bake_dialog_operator('INVOKE_DEFAULT')
