# Tooltip: Convert active mesh's diffuse texture alpha to a new filled mesh with matching UVs.
import bpy
import bmesh
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

def get_image_from_material(mat):
    if not mat or not mat.use_nodes:
        return None
    for node in mat.node_tree.nodes:
        if node.type == 'BSDF_PRINCIPLED':
            base_color = node.inputs.get("Base Color")
            if base_color and base_color.is_linked:
                link = base_color.links[0]
                if link.from_node.type == 'TEX_IMAGE':
                    return link.from_node.image
    # Fallback to any TEX_IMAGE node if principled isn't found/linked
    for node in mat.node_tree.nodes:
        if node.type == 'TEX_IMAGE':
            return node.image
    return None

class DUMBTOOLS_OT_image_to_spline(bpy.types.Operator):
    bl_idname = "dumbtools.image_to_spline"
    bl_label = "Alpha to Mesh"
    bl_options = {'REGISTER', 'UNDO'}
    
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
    
    create_border: bpy.props.BoolProperty(
        name="Include Border Rectangle",
        default=False,
        description="Also create a rectangular outline for the full image size"
    )

    @classmethod
    def poll(cls, context):
        obj = context.active_object
        return obj and obj.type == 'MESH' and len(obj.data.materials) > 0

    def invoke(self, context, event):
        obj = context.active_object
        if not obj or obj.type != 'MESH' or not obj.data.materials:
            self.report({'ERROR'}, "Please select a mesh object with a material.")
            return {'CANCELLED'}
            
        mat = obj.data.materials[0]
        if not mat:
            self.report({'ERROR'}, "Active object has no material.")
            return {'CANCELLED'}
            
        img = get_image_from_material(mat)
        if not img:
            self.report({'ERROR'}, "No Image Texture linked to Principled BSDF found in the first material.")
            return {'CANCELLED'}
            
        return context.window_manager.invoke_props_dialog(self)

    def execute(self, context):
        obj = context.active_object
        mat = obj.data.materials[0]
        img = get_image_from_material(mat)
        
        if not img:
            self.report({'ERROR'}, "Could not find image in material.")
            return {'CANCELLED'}
            
        cv2 = ensure_cv2()
        
        width, height = img.size
        
        if width == 0 or height == 0:
            self.report({'ERROR'}, "Image has 0 dimensions.")
            return {'CANCELLED'}
            
        # Extract alpha channel using fast method
        pixels = np.empty(width * height * 4, dtype=np.float32)
        img.pixels.foreach_get(pixels)
        
        if len(pixels) != width * height * 4:
            self.report({'ERROR'}, "Image is not 4-channel RGBA.")
            return {'CANCELLED'}
            
        alpha = pixels[3::4].reshape((height, width))
        alpha = np.flipud(alpha) # OpenCV y is top-down
        
        alpha_8u = (alpha * 255).astype(np.uint8)
        
        thresh_val = int(self.alpha_threshold * 255)
        _, binary = cv2.threshold(alpha_8u, thresh_val, 255, cv2.THRESH_BINARY)
        
        contours, _ = cv2.findContours(binary, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
        
        if not contours:
            self.report({'WARNING'}, "No opaque areas found with given threshold.")
            return {'CANCELLED'}
        
        curve_data = bpy.data.curves.new(name=f"{img.name}_Splines", type='CURVE')
        curve_data.dimensions = '2D'
        curve_data.fill_mode = 'BOTH'
        
        if self.create_border:
            border_spline = curve_data.splines.new(type='POLY')
            border_spline.points.add(3)
            w_scaled = width * self.scale
            h_scaled = height * self.scale
            border_spline.points[0].co = (0, 0, 0, 1)
            border_spline.points[1].co = (w_scaled, 0, 0, 1)
            border_spline.points[2].co = (w_scaled, h_scaled, 0, 1)
            border_spline.points[3].co = (0, h_scaled, 0, 1)
            border_spline.use_cyclic_u = True
        
        for cnt in contours:
            if len(cnt) < 3:
                continue
                
            spline = curve_data.splines.new(type='POLY')
            spline.points.add(len(cnt) - 1)
            
            for i, pt in enumerate(cnt):
                x, y = pt[0]
                blender_y = height - y
                spline.points[i].co = (x * self.scale, blender_y * self.scale, 0, 1)
                
            spline.use_cyclic_u = True

        curve_obj = bpy.data.objects.new(name=f"{img.name}_Mesh", object_data=curve_data)
        context.collection.objects.link(curve_obj)
        
        curve_obj.location = obj.location
        
        bpy.ops.object.select_all(action='DESELECT')
        curve_obj.select_set(True)
        context.view_layer.objects.active = curve_obj
        
        # Convert to mesh
        bpy.ops.object.convert(target='MESH')
        new_mesh_obj = context.active_object
        
        # Assign material
        new_mesh_obj.data.materials.append(mat)
        
        # Generate UVs based on vertex positions
        mesh = new_mesh_obj.data
        if not mesh.uv_layers:
            mesh.uv_layers.new(name="UVMap")
        uv_layer = mesh.uv_layers.active.data
        
        for poly in mesh.polygons:
            for loop_index in poly.loop_indices:
                loop = mesh.loops[loop_index]
                v = mesh.vertices[loop.vertex_index]
                
                u = (v.co.x / self.scale) / width
                v_coord = (v.co.y / self.scale) / height
                
                uv_layer[loop_index].uv = (u, v_coord)
                
        self.report({'INFO'}, f"Successfully created filled mesh from {img.name}")
        return {'FINISHED'}

classes = (DUMBTOOLS_OT_image_to_spline,)

def register():
    for cls in classes:
        try:
            bpy.utils.register_class(cls)
        except ValueError:
            bpy.utils.unregister_class(cls)
            bpy.utils.register_class(cls)

register()
bpy.ops.dumbtools.image_to_spline('INVOKE_DEFAULT')
