# Tooltip: Add OpenCV image processing nodes to Blender's compositor for advanced image manipulation
bl_info = {
    "author": "Peakz",
    "name": "OpenCV Image Processing Node v2.4.0",
    "blender": (3, 0, 0),
    "category": "Node",
}

import bpy
from bpy.types import Node, Operator, UILayout
from bpy.props import FloatProperty, EnumProperty, PointerProperty

from functools import cache

try:
    import cv2 as cv
except ImportError:
    from pip._internal import main as install
    install(["install", "opencv-python"])
    import cv2 as cv


# Define available OpenCV functions
opencv_functions = [
    ('GAUSSIAN_BLUR', 'Gaussian Blur', 'Apply Gaussian Blur'),
    ('MEDIAN_BLUR', 'Median Blur', 'Apply Median Blur'),
    ('BILATERAL_FILTER', 'Bilateral Filter', 'Apply Bilateral Filter'),
    # Add more OpenCV functions here as needed
]


@cache
def img_read(imagePath):
    img = cv.imread(imagePath, cv.IMREAD_UNCHANGED)
    return img


def apply_opencv_function(img, function, blur_scale):
    if function == 'GAUSSIAN_BLUR':
        ksize = int(blur_scale * 10) * 2 + 1
        return cv.GaussianBlur(img, (ksize, ksize), 0)
    elif function == 'MEDIAN_BLUR':
        ksize = int(blur_scale * 10) * 2 + 1
        return cv.medianBlur(img, ksize)
    elif function == 'BILATERAL_FILTER':
        d = int(blur_scale * 10)
        return cv.bilateralFilter(img, d, 75, 75)
    # Add more cases for other functions here
    return img


class OpenCVNode(Node):
    bl_idname = 'ShaderOpenCVNode'
    bl_label = 'OpenCV Image Processing'
    bl_icon = 'NODE'
    bl_options = {'REGISTER', 'UNDO'}

    # Properties
    function: EnumProperty(
        name="Function",
        description="Choose an OpenCV function",
        items=opencv_functions,
        default='GAUSSIAN_BLUR',
        update=lambda self, context: self.update()
    )

    blur_scale: FloatProperty(
        name="Blur Scale",
        default=1.0,
        min=0.1,
        max=10.0,
        update=lambda self, context: self.update()
    )

    image: PointerProperty(
        name="Image",
        type=bpy.types.Image,
        update=lambda self, context: self.update()
    )

    interpolation: EnumProperty(
        name="Interpolation",
        items=[
            ('Linear', "Linear", ""),
            ('Closest', "Closest", ""),
            ('Cubic', "Cubic", ""),
            ('Smart', "Smart", ""),
        ],
        default='Linear',
    )

    projection: EnumProperty(
        name="Projection",
        items=[
            ('Flat', "Flat", ""),
            ('Box', "Box", ""),
            ('Sphere', "Sphere", ""),
            ('Tube', "Tube", ""),
        ],
        default='Flat',
    )

    extension: EnumProperty(
        name="Extension",
        items=[
            ('Repeat', "Repeat", ""),
            ('Extend', "Extend", ""),
            ('Clip', "Clip", ""),
        ],
        default='Repeat',
    )

    def init(self, context):
        self.use_custom_color = True
        self.color = (0.188235, 0.188235, 0.188235)
        self.width = 150

        self.inputs.new('NodeSocketVector', "Vector")
        self.outputs.new('NodeSocketColor', "Color")
        self.outputs.new('NodeSocketColor', "Alpha")

    def update(self):
        if self.image:
            image_path = bpy.path.abspath(self.image.filepath)
            self.process_image(image_path)

    def process_image(self, image_path):
        cv_img = img_read(image_path)
        processed_img = apply_opencv_function(cv_img, self.function, self.blur_scale)

        image_name = image_path.split("\\")[-1]
        image_ext = image_name.split(".")[-1]
        processed_image_name = image_name.split(".")[0] + "_Processed." + image_ext
        processed_image_path = image_path.replace(image_name, "") + processed_image_name
        cv.imwrite(processed_image_path, processed_img)

        if processed_image_name in bpy.data.images:
            bpy.data.images.remove(bpy.data.images[processed_image_name])

        processed_image = bpy.data.images.load(processed_image_path)

        if self.outputs['Color'].is_linked:
            for link in self.outputs['Color'].links:
                link.to_socket.node.image = processed_image

    def draw_buttons(self, context, layout):
        layout.template_ID(self, "image", open="image.open", new="image.new")
        layout.prop(self, "interpolation", text="Interpolation")
        layout.prop(self, "projection", text="Projection")
        layout.prop(self, "extension", text="Extension")
        layout.prop(self, "function", text="Function")
        if self.function in {'GAUSSIAN_BLUR', 'MEDIAN_BLUR', 'BILATERAL_FILTER'}:
            layout.prop(self, "blur_scale", text="Scale")


class OpenCVNodeOperator(Operator):
    bl_idname = "customnodes.opencvnode"
    bl_label = "OpenCV Image Processing"
    bl_options = {'REGISTER', 'UNDO'}

    def execute(self, context):
        bpy.ops.node.add_node(type=OpenCVNode.bl_idname)
        return {'FINISHED'}


def Custom_Nodes_Draw(self, context):
    layout = self.layout
    layout.separator()
    layout.operator(OpenCVNodeOperator.bl_idname, text="OpenCV Image Processing")


def register():
    bpy.utils.register_class(OpenCVNode)
    bpy.utils.register_class(OpenCVNodeOperator)
    bpy.types.NODE_MT_add.append(Custom_Nodes_Draw)


def unregister():
    bpy.utils.unregister_class(OpenCVNode)
    bpy.utils.unregister_class(OpenCVNodeOperator)
    bpy.types.NODE_MT_add.remove(Custom_Nodes_Draw)


register()
