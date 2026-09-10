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

def get_image_node_from_material(mat):
    if not mat or not mat.use_nodes:
        return None, None
    for node in mat.node_tree.nodes:
        if node.type == 'BSDF_PRINCIPLED':
            base_color = node.inputs.get("Base Color")
            if base_color and base_color.is_linked:
                link = base_color.links[0]
                if link.from_node.type == 'TEX_IMAGE':
                    return link.from_node, link.from_node.image
    # Fallback to any TEX_IMAGE node if principled isn't found/linked
    for node in mat.node_tree.nodes:
        if node.type == 'TEX_IMAGE':
            return node, node.image
    return None, None

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
    
    use_animation: bpy.props.BoolProperty(
        name="Process Animation",
        default=False,
        description="Create a sequence of objects and animate visibility via constraints"
    )
    
    frame_start: bpy.props.IntProperty(
        name="Frame Start",
        default=1
    )
    
    frame_end: bpy.props.IntProperty(
        name="Frame End",
        default=250
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
            
        node, img = get_image_node_from_material(mat)
        if not img:
            self.report({'ERROR'}, "No Image Texture linked to Principled BSDF found in the first material.")
            return {'CANCELLED'}
            
        self.frame_start = context.scene.frame_start
        self.frame_end = context.scene.frame_end
            
        return context.window_manager.invoke_props_dialog(self)

    def execute(self, context):
        import os
        obj = context.active_object
        mat = obj.data.materials[0]
        node, img = get_image_node_from_material(mat)
        
        if not img:
            self.report({'ERROR'}, "Could not find image in material.")
            return {'CANCELLED'}
            
        cv2 = ensure_cv2()
        
        original_frame = context.scene.frame_current

        if self.use_animation:
            frames = range(self.frame_start, self.frame_end + 1)
            
            # create Root Empty
            root_empty = bpy.data.objects.new(f"{img.name}_Root", None)
            context.collection.objects.link(root_empty)
            root_empty.location = obj.location
            
            # create Hide Empty
            hide_empty = bpy.data.objects.new(f"{img.name}_Hide", None)
            context.collection.objects.link(hide_empty)
            hide_empty.parent = root_empty
            hide_empty.location = (0, 0, -100) # local offset
            
        else:
            frames = [original_frame]

        meshes_created = 0

        for f in frames:
            alpha_8u = None
            width, height = 0, 0
            
            if self.use_animation:
                context.scene.frame_set(f)
                if mat and mat.use_nodes:
                    mat.node_tree.update_tag()
                img.update_tag()
                context.view_layer.update() # Force depsgraph
                
                # Force Blender's UI and video decoding threads to process the frame
                bpy.ops.wm.redraw_timer(type='DRAW_WIN_SWAP', iterations=1)
                
            # 1. Try reading directly from disk if it's a sequence
            if img.source == 'SEQUENCE' and node and hasattr(node, "image_user"):
                filepath = ""
                # A: Try Blender's evaluated path
                if hasattr(img, "filepath_from_user"):
                    try: filepath = bpy.path.abspath(img.filepath_from_user(image_user=node.image_user))
                    except: pass
                
                # B: If Blender returns same/wrong path, force regex calculation
                base_path = bpy.path.abspath(img.filepath)
                import re
                m = re.search(r'(\d+)(?=[^\d]*$)', base_path)
                if m:
                    image_frame = f - node.image_user.frame_start + node.image_user.frame_offset + 1
                    frame_str = m.group(1)
                    new_frame_str = str(image_frame).zfill(len(frame_str))
                    regex_path = base_path[:m.start()] + new_frame_str + base_path[m.end():]
                    if os.path.exists(regex_path):
                        filepath = regex_path
                        
                if filepath and os.path.exists(filepath):
                    img_cv = cv2.imread(filepath, cv2.IMREAD_UNCHANGED)
                    if img_cv is not None and len(img_cv.shape) == 3 and img_cv.shape[2] == 4:
                        height, width = img_cv.shape[:2]
                        alpha_8u = img_cv[:, :, 3]
            
            # 2. Fallback to OpenCV VideoCapture for MOVIE files (if supported by OS/FFmpeg)
            if alpha_8u is None and img.source == 'MOVIE':
                movie_path = bpy.path.abspath(img.filepath)
                if os.path.exists(movie_path):
                    cap = cv2.VideoCapture(movie_path)
                    if cap.isOpened():
                        movie_frame = f - 1 # OpenCV is 0-indexed
                        if node and hasattr(node, "image_user"):
                            movie_frame = f - node.image_user.frame_start + node.image_user.frame_offset
                        cap.set(cv2.CAP_PROP_POS_FRAMES, movie_frame)
                        ret, img_cv = cap.read()
                        if ret and img_cv is not None and len(img_cv.shape) == 3 and img_cv.shape[2] == 4:
                            height, width = img_cv.shape[:2]
                            alpha_8u = img_cv[:, :, 3]
                    cap.release()
                    
            # 3. Ultimate Fallback to Blender's pixel cache
            if alpha_8u is None:
                if self.use_animation:
                    try: img.gl_load()
                    except: pass
                    img.update()
                    
                width, height = img.size
                if width == 0 or height == 0:
                    continue
                    
                pixels = np.empty(width * height * 4, dtype=np.float32)
                img.pixels.foreach_get(pixels)
                if len(pixels) != width * height * 4:
                    continue
                    
                alpha = pixels[3::4].reshape((height, width))
                alpha = np.flipud(alpha) # OpenCV y is top-down
                alpha_8u = (alpha * 255).astype(np.uint8)
            
            thresh_val = int(self.alpha_threshold * 255)
            _, binary = cv2.threshold(alpha_8u, thresh_val, 255, cv2.THRESH_BINARY)
            
            contours, _ = cv2.findContours(binary, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
            
            if not contours:
                continue
            
            curve_name = f"{img.name}_F{f}" if self.use_animation else f"{img.name}_Mesh"
            curve_data = bpy.data.curves.new(name=curve_name, type='CURVE')
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

            curve_obj = bpy.data.objects.new(name=curve_name, object_data=curve_data)
            context.collection.objects.link(curve_obj)
            
            if self.use_animation:
                curve_obj.parent = root_empty
                curve_obj.location = (0, 0, 0)
            else:
                curve_obj.location = obj.location
            
            bpy.ops.object.select_all(action='DESELECT')
            curve_obj.select_set(True)
            context.view_layer.objects.active = curve_obj
            
            # Convert to mesh
            bpy.ops.object.convert(target='MESH')
            new_mesh_obj = context.active_object
            
            # Fix normals for Solidify modifier (ensure all face +Z)
            bm = bmesh.new()
            bm.from_mesh(new_mesh_obj.data)
            for face in bm.faces:
                if face.normal.z < 0:
                    face.normal_flip()
            bm.normal_update()
            bm.to_mesh(new_mesh_obj.data)
            bm.free()
            
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

            # Setup animation constraints
            if self.use_animation:
                constraint = new_mesh_obj.constraints.new('COPY_LOCATION')
                constraint.target = hide_empty
                
                # Frame 0 -> 1.0
                constraint.influence = 1.0
                constraint.keyframe_insert(data_path='influence', frame=0)
                
                # Frame f -> 0.0
                constraint.influence = 0.0
                constraint.keyframe_insert(data_path='influence', frame=f)
                
                # Frame f+1 -> 1.0
                constraint.influence = 1.0
                constraint.keyframe_insert(data_path='influence', frame=f+1)
                
                # Set interpolation to CONSTANT, accounting for Blender 5 Animation API (Slots, Bindings, etc)
                if new_mesh_obj.animation_data and new_mesh_obj.animation_data.action:
                    action = new_mesh_obj.animation_data.action
                    found_fcurves = set()
                    
                    def find_fcurves(obj, depth=0):
                        if depth > 4 or obj is None: return
                        
                        if hasattr(obj, "fcurves"):
                            try:
                                for fc in obj.fcurves:
                                    if hasattr(fc, "keyframe_points"):
                                        found_fcurves.add(fc)
                            except Exception: pass
                                
                        for attr in ("slots", "bindings", "layers", "strips"):
                            if hasattr(obj, attr):
                                try:
                                    for item in getattr(obj, attr):
                                        find_fcurves(item, depth + 1)
                                except Exception: pass
                                
                    find_fcurves(action)
                    
                    for fcurve in found_fcurves:
                        for kf in fcurve.keyframe_points:
                            kf.interpolation = 'CONSTANT'
            
            meshes_created += 1

        if self.use_animation:
            context.scene.frame_set(original_frame)

        if meshes_created == 0:
            self.report({'WARNING'}, "No meshes were created. Check threshold and image data.")
        else:
            self.report({'INFO'}, f"Successfully created {meshes_created} mesh(es) from {img.name}")
            
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
