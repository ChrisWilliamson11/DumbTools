# Tooltip: Generate a spline from the alpha channel of an image, and a rectangular border for the full image size.
import bpy
import numpy as np
import subprocess
import sys

def ensure_cv2():
    try:
        import cv2
        return cv2
    except ImportError:
        print("OpenCV not found, attempting to install...")
        python_exe = sys.executable
        subprocess.check_call([python_exe, "-m", "pip", "install", "opencv-python"])
        import cv2
        return cv2

class DUMBTOOLS_OT_image_to_spline(bpy.types.Operator):
    bl_idname = "dumbtools.image_to_spline"
    bl_label = "Image to Spline"
    bl_options = {'REGISTER', 'UNDO'}

    image_name: bpy.props.EnumProperty(
        name="Image",
        items=lambda self, context: [(img.name, img.name, "") for img in bpy.data.images] if bpy.data.images else [("NONE", "None", "")]
    )
    
    alpha_threshold: bpy.props.FloatProperty(
        name="Alpha Threshold",
        default=0.5,
        min=0.0,
        max=1.0,
        description="Alpha value above which pixels are considered solid"
    )
    
    scale: bpy.props.FloatProperty(
        name="Scale Factor",
        default=0.01,
        min=0.0001,
        description="Scale pixels to Blender units"
    )

    def invoke(self, context, event):
        if not bpy.data.images:
            self.report({'ERROR'}, "No images found in the file.")
            return {'CANCELLED'}
        return context.window_manager.invoke_props_dialog(self)

    def execute(self, context):
        if self.image_name == "NONE" or self.image_name not in bpy.data.images:
            self.report({'ERROR'}, "Invalid image selected.")
            return {'CANCELLED'}
            
        cv2 = ensure_cv2()
        
        img = bpy.data.images[self.image_name]
        width, height = img.size
        
        if width == 0 or height == 0:
            self.report({'ERROR'}, "Image has 0 dimensions.")
            return {'CANCELLED'}
            
        # Extract alpha channel using fast method
        pixels = np.empty(width * height * 4, dtype=np.float32)
        img.pixels.foreach_get(pixels)
        # pixels is a 1D array of [r,g,b,a, r,g,b,a, ...]
        if len(pixels) != width * height * 4:
            self.report({'ERROR'}, "Image is not 4-channel RGBA.")
            return {'CANCELLED'}
            
        # Get alpha channel and reshape
        alpha = pixels[3::4].reshape((height, width))
        
        # In Blender, pixel [0,0] is bottom-left, in OpenCV it's top-left
        # Let's flip it so it matches OpenCV conventions, or just work with it.
        # Flipping vertically:
        alpha = np.flipud(alpha)
        
        # Convert to 8-bit image for OpenCV
        alpha_8u = (alpha * 255).astype(np.uint8)
        
        # Threshold
        thresh_val = int(self.alpha_threshold * 255)
        _, binary = cv2.threshold(alpha_8u, thresh_val, 255, cv2.THRESH_BINARY)
        
        # Find contours
        contours, _ = cv2.findContours(binary, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
        
        if not contours:
            self.report({'WARNING'}, "No opaque areas found with given threshold.")
        
        # Create Curve Data
        curve_data = bpy.data.curves.new(name=f"{img.name}_Splines", type='CURVE')
        curve_data.dimensions = '2D'
        curve_data.fill_mode = 'NONE' # 'NONE' so we can see the edges
        
        # 1. Create a rectangular border spline
        border_spline = curve_data.splines.new(type='POLY')
        border_spline.points.add(3) # 4 points total
        
        # We want the origin to be center or corner? Let's make bottom-left = (0,0)
        # Image coordinates: x goes 0 to width, y goes 0 to height
        w_scaled = width * self.scale
        h_scaled = height * self.scale
        
        border_spline.points[0].co = (0, 0, 0, 1)
        border_spline.points[1].co = (w_scaled, 0, 0, 1)
        border_spline.points[2].co = (w_scaled, h_scaled, 0, 1)
        border_spline.points[3].co = (0, h_scaled, 0, 1)
        border_spline.use_cyclic_u = True
        
        # 2. Create splines for contours
        for cnt in contours:
            if len(cnt) < 3:
                continue
                
            spline = curve_data.splines.new(type='POLY')
            spline.points.add(len(cnt) - 1)
            
            for i, pt in enumerate(cnt):
                x, y = pt[0]
                # OpenCV y is from top, so we invert it back for Blender
                blender_y = height - y
                
                spline.points[i].co = (x * self.scale, blender_y * self.scale, 0, 1)
                
            spline.use_cyclic_u = True

        # Create Object
        curve_obj = bpy.data.objects.new(name=f"{img.name}_Mesh", object_data=curve_data)
        context.collection.objects.link(curve_obj)
        
        # Select and make active
        bpy.ops.object.select_all(action='DESELECT')
        curve_obj.select_set(True)
        context.view_layer.objects.active = curve_obj

        self.report({'INFO'}, f"Created {len(contours)} alpha splines + 1 border spline.")
        return {'FINISHED'}

classes = (DUMBTOOLS_OT_image_to_spline,)

def register():
    for cls in classes:
        try:
            bpy.utils.register_class(cls)
        except ValueError:
            bpy.utils.unregister_class(cls)
            bpy.utils.register_class(cls)

def unregister():
    for cls in reversed(classes):
        try:
            bpy.utils.unregister_class(cls)
        except ValueError:
            pass

register()
bpy.ops.dumbtools.image_to_spline('INVOKE_DEFAULT')
