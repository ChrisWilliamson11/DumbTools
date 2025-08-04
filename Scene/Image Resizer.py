# Tooltip: Lets you resize the images in your scene to a specified dimension, keeping the aspect ratio if desired.
import bpy

class ImageItem(bpy.types.PropertyGroup):
    name: bpy.props.StringProperty(name="Name", default="")
    width: bpy.props.IntProperty(name="Width", default=0)
    height: bpy.props.IntProperty(name="Height", default=0)
    selected: bpy.props.BoolProperty(name="Selected", default=False)

class IMAGE_UL_items(bpy.types.UIList):
    def draw_item(self, context, layout, data, item, icon, active_data, active_property, index):
        if self.layout_type in {'DEFAULT', 'COMPACT'}:
            layout.prop(item, "selected", text="")
            layout.label(text=item.name)
            layout.label(text=f"{item.width} x {item.height}")
        elif self.layout_type == 'GRID':
            layout.alignment = 'CENTER'
            layout.label(text="")

class IMAGE_OT_resize(bpy.types.Operator):
    bl_idname = "image.resize_images"
    bl_label = "Resize Images"
    
    def execute(self, context):
        scn = context.scene
        resize_dim = scn.image_resize_dimension
        keep_aspect_ratio = scn.image_keep_aspect_ratio
        images = [item for item in scn.image_list if item.selected]
        
        for img_item in images:
            img = bpy.data.images[img_item.name]
            width, height = img.size
            if width == 0 or height == 0:
                self.report({'WARNING'}, f"Image '{img.name}' has zero width or height and cannot be resized.")
                continue

            if keep_aspect_ratio:
                if width > height:
                    new_width = min(resize_dim, width)
                    new_height = int(height * (new_width / width))
                else:
                    new_height = min(resize_dim, height)
                    new_width = int(width * (new_height / height))
            else:
                new_width = min(resize_dim, width)
                new_height = min(resize_dim, height)
            
            img.scale(new_width, new_height)
        
        return {'FINISHED'}

class IMAGE_OT_select_all(bpy.types.Operator):
    bl_idname = "image.select_all"
    bl_label = "Select All Images"
    
    def execute(self, context):
        scn = context.scene
        for item in scn.image_list:
            item.selected = True
        return {'FINISHED'}

class IMAGE_OT_refresh_list(bpy.types.Operator):
    bl_idname = "image.refresh_list"
    bl_label = "Refresh List"
    
    def execute(self, context):
        update_image_list()
        return {'FINISHED'}

class IMAGE_PT_resize_panel(bpy.types.Panel):
    bl_label = "Image Resizer"
    bl_idname = "IMAGE_PT_resize_panel"
    bl_space_type = 'VIEW_3D'
    bl_region_type = 'UI'
    bl_category = 'Image Resizer'
    
    def draw(self, context):
        layout = self.layout
        scn = context.scene

        row = layout.row()
        row.template_list("IMAGE_UL_items", "", scn, "image_list", scn, "image_list_index", type='DEFAULT')
        
        layout.operator("image.select_all", text="Select All")
        layout.prop(scn, "image_resize_dimension")
        layout.prop(scn, "image_keep_aspect_ratio", text="Keep Aspect Ratio")
        layout.prop(scn, "image_limit_to_selected_objects", text="Limit to Selected Objects")
        layout.operator("image.refresh_list", text="Refresh List")
        layout.operator("image.resize_images")

def register():
    bpy.utils.register_class(ImageItem)
    bpy.utils.register_class(IMAGE_UL_items)
    bpy.utils.register_class(IMAGE_OT_resize)
    bpy.utils.register_class(IMAGE_OT_select_all)
    bpy.utils.register_class(IMAGE_OT_refresh_list)
    bpy.utils.register_class(IMAGE_PT_resize_panel)
    
    bpy.types.Scene.image_list = bpy.props.CollectionProperty(type=ImageItem)
    bpy.types.Scene.image_list_index = bpy.props.IntProperty()
    bpy.types.Scene.image_resize_dimension = bpy.props.IntProperty(
        name="Resize Dimension",
        description="Dimension to resize the longest side of the image",
        default=1024,
        min=1
    )
    bpy.types.Scene.image_keep_aspect_ratio = bpy.props.BoolProperty(
        name="Keep Aspect Ratio",
        description="Keep the aspect ratio when resizing images",
        default=True
    )
    bpy.types.Scene.image_limit_to_selected_objects = bpy.props.BoolProperty(
        name="Limit to Selected Objects",
        description="Limit the image list to images linked to the selected objects",
        default=False
    )
    
    update_image_list()

def unregister():
    bpy.utils.unregister_class(ImageItem)
    bpy.utils.unregister_class(IMAGE_UL_items)
    bpy.utils.unregister_class(IMAGE_OT_resize)
    bpy.utils.unregister_class(IMAGE_OT_select_all)
    bpy.utils.unregister_class(IMAGE_OT_refresh_list)
    bpy.utils.unregister_class(IMAGE_PT_resize_panel)
    
    del bpy.types.Scene.image_list
    del bpy.types.Scene.image_list_index
    del bpy.types.Scene.image_resize_dimension
    del bpy.types.Scene.image_keep_aspect_ratio
    del bpy.types.Scene.image_limit_to_selected_objects

def update_image_list():
    scn = bpy.context.scene
    scn.image_list.clear()
    
    if scn.image_limit_to_selected_objects:
        selected_objects = bpy.context.selected_objects
        used_images = {slot.texture.image for obj in selected_objects if obj.type == 'MESH' for slot in obj.material_slots if slot.material and slot.material.use_nodes for node in slot.material.node_tree.nodes if node.type == 'TEX_IMAGE' and node.image}
    else:
        used_images = set(bpy.data.images)

    for img in used_images:
        item = scn.image_list.add()
        item.name = img.name
        item.width = img.size[0]
        item.height = img.size[1]


register()
