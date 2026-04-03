# Tooltip:  Select a Photoshop file, it will try and save each layer into a PNG file and import them as planes. Positions them in 3D space and parents them to an empty.
import pip
import os
import time
import random
import string

try:    
    import psd_tools
except ModuleNotFoundError:
    pip.main(['install', 'psd_tools', '--user'])    
    
import bpy
try:    
    import pillow
except ModuleNotFoundError:
    pip.main(['install', 'pillow', '--user']) 

from mathutils import Vector
from bpy.props import (BoolProperty,
                       StringProperty,
                       FloatProperty,
                       EnumProperty,
                       CollectionProperty)
from bpy_extras.io_utils import (ImportHelper,
                                 orientation_helper,
                                 axis_conversion)


def generate_random_id(length=8):
    chars = ''.join((string.digits,
                     string.ascii_lowercase,
                     string.ascii_uppercase))
    return ''.join(random.choice(chars) for _ in range(length))


def print_progress(progress, min=0, max=100, barlen=50, prefix='', suffix='', line_width=80):
    total_len = max - min
    progress_float = (progress - min) / total_len
    bar_progress = int(progress_float * barlen) * '='
    bar_empty = (barlen - len(bar_progress)) * ' '
    percentage = ''.join((str(int(progress_float * 100)), '%'))
    progress_string = ''.join((prefix, '[', bar_progress, bar_empty, ']', ' ', percentage, suffix))[:line_width]
    print_string = ''.join((progress_string, ' ' * (line_width - len(progress_string))))
    print(print_string, end='\r')


def parse_psd(self, psd_file):
    '''
    parse_psd(string psd_file) -> list layers, list bboxes, tuple image_size, string png_dir

        Reads psd_file and exports all layers to png's.
        Returns a list of all the layer objects, the image size and
        the png export directory.

        string psd_file - the filepath of the psd file
    '''

    def get_layers(layer, all_layers=[]):
        if not layer.is_group():
            return
        for sub_layer in reversed(layer):  # reversed() since psd_tools 1.8
            all_layers.append(sub_layer)
            get_layers(sub_layer, all_layers=all_layers)
        return all_layers

    def export_layers_as_png(layers, png_dir):
        bboxes = []
        for i, layer in enumerate(layers):
            if (layer.is_group() or (not self.hidden_layers and not layer.is_visible())):
                bboxes.append(None)
                continue
            prefix = '  - exporting: '
            suffix = ' - {}'.format(layer.name)
            print_progress(i+1, max=(len(layers)), barlen=40, prefix=prefix, suffix=suffix, line_width=120)
            if self.clean_name:
                name = bpy.path.clean_name(layer.name).rstrip('_')
            else:
                name = layer.name.replace('\x00', '')
            name = name.rstrip('_')
            if self.layer_index_name:
                name = name + '_' + str(i)
            png_file = os.path.join(png_dir, ''.join((name, '.png')))
            try:
                layer_image = layer.topil()
            except ValueError:
                print("Could not process layer " + layer.name)
                bboxes.append(None)
                continue
            if layer_image is None:
                bboxes.append(None)
                continue
            ## AUTOCROP
            if self.crop_layers:
                bbox = layer_image.getbbox()
                bboxes.append(bbox)
                layer_image = layer_image.crop(bbox)
            else:
                bboxes.append(None)
            layer_image.save(png_file)
        return bboxes

    print('parsing: {}'.format(psd_file))
    psd_dir, psd_name = os.path.split(psd_file)
    psd_name = os.path.splitext(psd_name)[0]
    png_dir = os.path.join(psd_dir, '_'.join((psd_name, 'pngs')))
    if not os.path.isdir(png_dir):
        os.mkdir(png_dir)
    psd = psd_tools.PSDImage.open(psd_file)

    layers = get_layers(psd)
    bboxes = export_layers_as_png(layers, png_dir)
    bb = psd.bbox
    image_size = (bb[2] - bb[0], bb[3] - bb[1])

    return (layers, bboxes, image_size, png_dir)


def create_objects(self, psd_layers, bboxes, image_size, img_dir, psd_name, import_id, collection):
    '''
    create_objects(class self, list psd_layers, tuple image_size,
                  string img_dir, string psd_name, list layers, string import_id)

        Imports all png images that are in psd_layers from img_dir
        into Blender as planes and places these planes correctly.

        class self        - the import operator class
        list psd_layers   - info about the layer like position and index
        list bboxes       - layers' bounding boxes if need to crop
        tuple image_size  - the width and height of the image
        string img_dir    - the path to the png images
        string psd_name   - the name of the psd file
        string import_id  - used to identify this import
    '''

    def get_parent(parent, import_id):
        if parent.name == '_RootGroup':
            return root_empty
        if self.clean_name:
            parent_name = bpy.path.clean_name(parent.name).rstrip('_')
        else:
            parent_name = parent.name.replace('\x00', '').rstrip('_')

        if parent in psd_layers:
            parent_index = psd_layers.index(parent)
            for obj in bpy.context.scene.objects:
                if (parent_name in obj.name and obj.type == 'EMPTY' and
                        obj['2d_animation_tools']['import_id'] == import_id and
                        obj['2d_animation_tools']['layer_index'] == str(parent_index)):
                    return obj
        else:
            return root_empty

    def group_object(obj, parent, import_id):
        bpy.context.view_layer.update()
        parent_empty = get_parent(parent, import_id)
        matrix_parent_inverse = parent_empty.matrix_world.inverted()
        obj.parent = parent_empty
        obj.matrix_parent_inverse = matrix_parent_inverse

    def get_dimensions(layer, bbox):
        if self.crop_layers and bbox is not None:
            x = layer.bbox[0] + bbox[0]
            y = layer.bbox[1] + bbox[1]
            width = bbox[2] - bbox[0]
            height = bbox[3] - bbox[1]
        else:
            x = layer.bbox[0]
            y = layer.bbox[1]
            width = layer.bbox[2] - x
            height = layer.bbox[3] - y
        return x, y, width, height

    def get_transforms(layer, bbox, i_offset):
        x, y, width, height = get_dimensions(layer, bbox)
        if self.size_mode == 'RELATIVE':
            scaling = self.scale_fac
        if self.size_mode == 'ABSOLUTE':
            if self.size_mode_absolute == 'WIDTH':
                scaling = image_width / self.absolute_size
            else:
                scaling = image_height / self.absolute_size
        loc_x = (-image_width / 2 + width / 2 + x) / scaling
        loc_y = self.offset * i_offset
        loc_z = (image_height - height / 2 - y) / scaling
        scale_x = width / scaling / 2
        scale_y = height / scaling / 2
        scale_z = 1
        location = Vector((loc_x, loc_y, loc_z))
        scale = Vector((scale_x, scale_y, scale_z))
        return (location, scale)

    def get_children_median(obj):
        children = [c for c in obj.children if c.type == 'MESH']
        if not children:
            return Vector()
        child_locations = [c.matrix_world.to_translation() for c in children]
        median = sum(child_locations, Vector()) / len(children)
        return median

    def move_to_children_median(obj):
        median = get_children_median(obj)
        obj.location = median
        bpy.context.view_layer.update()
        matrix_parent_inverse = obj.matrix_world.inverted()
        # for c in [c for c in obj.children if c.type == 'MESH']:
        for c in obj.children:
            c.matrix_parent_inverse = matrix_parent_inverse

    def create_image(img_path):
        img_name = os.path.basename(img_path)
        # Check if image already exists
        for i in bpy.data.images:
            if img_name in i.name and (i.filepath == img_path or i.filepath == bpy.path.relpath(img_path)):
                i.reload()
                return i
        # Image not found, create a new one
        try:
            img = bpy.data.images.load(img_path)
        except RuntimeError:
            return None
        if rel_path:
            if os.path.exists(bpy.path.abspath("//")) and os.path.commonprefix([img.filepath, bpy.path.abspath("//")]):
                img.filepath = bpy.path.relpath(img.filepath)

        return img

    def create_cycles_material(name, img, import_id):
        # Check if material already exists
        for m in bpy.data.materials:
            if name in m.name and m.use_nodes:
                for node in m.node_tree.nodes:
                    if node.type == 'TEX_IMAGE' and node.image == img:
                        return m
        # Create new material
        mat = bpy.data.materials.new(name)
        mat.use_nodes = True
        nodes = mat.node_tree.nodes
        nodes.clear()  # Clear all default nodes

        # Add a new Principled BSDF shader node
        shader = nodes.new(type='ShaderNodeBsdfPrincipled')
        shader.location = (0, 0)

        # Add a new image texture node and load the image
        texture_node = nodes.new('ShaderNodeTexImage')
        texture_node.location = (-300, 0)
        texture_node.image = img

        # Add Material Output node
        material_output = nodes.new(type='ShaderNodeOutputMaterial')
        material_output.location = (200, 0)

        # Connect the texture node to the Principled shader
        links = mat.node_tree.links
        links.new(texture_node.outputs['Color'], shader.inputs['Base Color'])
        links.new(texture_node.outputs['Alpha'], shader.inputs['Alpha'])

        # Connect the Principled shader to material output
        links.new(shader.outputs['BSDF'], material_output.inputs['Surface'])

        # Enable alpha blending for transparency
        mat.blend_method = 'BLEND'

        return mat



    def create_textured_plane(name, transforms, global_matrix, import_id, layer_index, psd_layer_name, img_path, create_original_uvs, dimensions):
        # Add UV's and add image to UV's
        img = create_image(img_path)
        if img is None:
            return
        # Create plane with 'forward: -y' and 'up: z'
        # Then use axis conversion to change to orientation specified by user
        loc, scale = transforms
        verts = [(-scale.x, 0, scale.y),
                 (scale.x, 0, scale.y),
                 (scale.x, 0, -scale.y),
                 (-scale.x, 0, -scale.y)]
        verts = [global_matrix @ Vector(v) for v in verts]
        faces = [(3, 2, 1, 0)]
        mesh = bpy.data.meshes.new(name)
        mesh.from_pydata(verts, [], faces)
        plane = bpy.data.objects.new(name, mesh)
        plane.location = global_matrix @ loc
        animation_tools_prop = {'import_id': import_id, 'layer_index': layer_index, 'psd_layer_name': psd_layer_name}
        plane['2d_animation_tools'] = animation_tools_prop
        plane.data.uv_layers.new()
        if create_original_uvs:
            x, y, width, height = dimensions
            original_uvs = plane.data.uv_layers.new(name="Original")
            original_uvs.data[0].uv = Vector((x / image_width,
                                              (image_height-y-height) / image_height))
            original_uvs.data[1].uv = Vector(((x+width) / image_width,
                                              (image_height-y-height) / image_height))
            original_uvs.data[2].uv = Vector(((x+width) / image_width,
                                              (image_height-y) / image_height))
            original_uvs.data[3].uv = Vector((x / image_width,
                                              (image_height-y) / image_height))
        # Create and assign material
        mat = create_cycles_material(name, img, import_id)
        plane.data.materials.append(mat)
        return plane

    rel_path = self.rel_path
    group_empty = self.group_empty
    axis_forward = self.axis_forward
    axis_up = self.axis_up

    image_width = image_size[0]
    image_height = image_size[1]

    global_matrix = axis_conversion(from_forward='-Y',
                                    from_up='Z',
                                    to_forward=axis_forward,
                                    to_up=axis_up).to_4x4()

    root_name = os.path.splitext(psd_name)[0]

    if group_empty:
        root_empty = bpy.data.objects.new(root_name, None)
        root_empty['2d_animation_tools'] = {'import_id': import_id, 'layer_index': 'root'}
        collection.objects.link(root_empty)
    i_offset = 0
    groups = []
    for i, layer in enumerate(psd_layers):
        prefix = '  - creating objects: '
        suffix = ' - {}'.format(layer.name)
        print_progress(i+1, max=(len(psd_layers)), barlen=40, prefix=prefix, suffix=suffix, line_width=120)

        if self.clean_name:
            name = bpy.path.clean_name(layer.name).rstrip('_')
        else:
            name = layer.name.replace('\x00', '').rstrip('_')

        psd_layer_name = layer.name
        layer_index = str(i)
        parent = layer.parent

        if layer.is_group() and group_empty:
            empty = bpy.data.objects.new(name, None)
            animation_tools_prop = {'import_id': import_id,
                                    'layer_index': layer_index,
                                    'psd_layer_name': psd_layer_name}
            empty['2d_animation_tools'] = animation_tools_prop
            group_object(empty, parent, import_id)
            groups.append(empty)
            collection.objects.link(empty)
        else:
            bbox = bboxes[i]
            transforms = get_transforms(layer, bbox, i_offset)
            dimensions = get_dimensions(layer, bbox)
            filename = name
            if self.layer_index_name:
                filename += '_' + layer_index
            img_path = os.path.join(img_dir, ''.join((filename, '.png')))
            plane = create_textured_plane(name, transforms, global_matrix,
                                          import_id, layer_index,
                                          psd_layer_name, img_path,
                                          self.create_original_uvs, dimensions)
            if plane is None:
                continue
            if group_empty:
                group_object(plane, parent, import_id)
            collection.objects.link(plane)
            i_offset += 1

    if group_empty:
        # Position empty at median of children
        groups.reverse()
        for group in groups:
            move_to_children_median(group)
        # Select root empty and make active object
        bpy.ops.object.select_all(action='DESELECT')
        root_empty.select_set(True)
        bpy.context.view_layer.objects.active = root_empty
        # Move root empty to cursor position
        root_empty.location = bpy.context.scene.cursor.location

@orientation_helper(axis_forward='-Y', axis_up='Z')
class ImportPsdAsPlanes(bpy.types.Operator, ImportHelper):

    '''Import PSD as planes'''
    bl_idname = 'import_scene.psd'
    bl_label = 'Import PSD as planes'
    bl_options = {'PRESET', 'UNDO'}

    # List of operator properties, the attributes will be assigned
    # to the class instance from the operator settings before calling.
    directory: StringProperty(
        maxlen=1024,
        subtype='DIR_PATH',
        options={'HIDDEN', 'SKIP_SAVE'})
    files: CollectionProperty(
        type=bpy.types.OperatorFileListElement,
        options={'HIDDEN', 'SKIP_SAVE'})

    filename_ext = '.psd'
    filter_glob: StringProperty(default='*.psd', options={'HIDDEN'})
    offset: FloatProperty(
        name='Offset',
        description='Offset planes by this amount on the Y axis',
        default=0.01)
    crop_layers: BoolProperty(
        name='Crop layers',
        description='Crop each layer according to its transparency',
        default=True)
    create_original_uvs: BoolProperty(
        name='Create original UVS',
        description='Generate an additional UV layer for placing the uncropped image',
        default=False)
    hidden_layers: BoolProperty(
        name='Import hidden layers',
        description='Also import hidden layers',
        default=False)
    size_mode: EnumProperty(
        name='Size Mode',
        description='How the size of the planes is computed',
        items=(('RELATIVE', 'Relative', 'Use relative size'),
               ('ABSOLUTE', 'Absolute', 'Use absolute size')),
        default='RELATIVE')
    scale_fac: FloatProperty(
        name='Scale',
        description='Number of pixels per Blender unit',
        default=100)
    size_mode_absolute: EnumProperty(
        name='Absolute Size Mode',
        description='Use the width or the height for the absolute size',
        items=(('WIDTH', 'Width', 'Define the width of the image'),
               ('HEIGHT', 'Height', 'Define the height of the image')),
        default='WIDTH')
    absolute_size: FloatProperty(
        name='Size',
        description='The width or height of the image in Blender units',
        default=2)
    clean_name: BoolProperty(
        name='Clean name',
        description='Characters replaced in filename that '
                    'may cause problems under various circumstances',
        default=True)
    clip: BoolProperty(
        name='Clip texture',
        description='Use CLIP as image extension. Avoids fringes on the edges',
        default=True)
    texture_interpolation: EnumProperty(
        name='Interpolation',
        description='Texture Interpolation',
        items=(('Linear', 'Linear', 'Linear interpolation'),
               ('Closest', 'Closest', 'No interpolation (Sample closest texel)'),
               ('Cubic', 'Cubic', 'Cubic interpolation (CPU only)'),
               ('Smart', 'Smart', 'Bicubic when magnifying, else bilinear (OSL only')),
        default='Linear')
    group_empty: BoolProperty(
        name='Empty',
        description='Parent the images to an empty',
        default=True)
    rel_path: BoolProperty(
        name='Relative Path',
        description='Select the file relative to the blend file',
        default=True)
    layer_index_name: BoolProperty(
        name='Layer Index',
        description='Add layer index to the png name. If not, possible conflicts may arise',
        default=True)

    @classmethod
    def poll(self, context):
        return context.mode == 'OBJECT'

    def draw(self, context):
        layout = self.layout

        # Transformation options
        box = layout.box()
        box.label(text='Transformation options', icon='OBJECT_ORIGIN')
        col = box.column()
        sub_col = col.column(align=True)
        row = sub_col.row(align=True)
        row.prop(self, 'size_mode', expand=True)
        if self.size_mode == 'ABSOLUTE':
            row = sub_col.row(align=True)
            row.prop(self, 'size_mode_absolute', expand=True)
            sub_col.prop(self, 'absolute_size')
        else:
            sub_col.prop(self, 'scale_fac')
        col.separator()
        col.prop(self, 'axis_forward')
        col.prop(self, 'axis_up')
        col.separator()
        col.prop(self, 'offset')
        col.separator()
        sub_col = col.column(align=True)
        sub_col.prop(self, 'crop_layers', toggle=True)
        if self.crop_layers:
            sub_col.prop(self, 'create_original_uvs', toggle=True)
        # Grouping options
        box = layout.box()
        box.label(text='Grouping', icon='GROUP')
        row = box.row(align=True)
        row.prop(self, 'group_empty', toggle=True)
        # Material options (not much for now)
        box = layout.box()
        box.label(text='Material options', icon='MATERIAL_DATA')
        col = box.column()
        col.prop(self, 'texture_interpolation')
        col.prop(self, 'clip', toggle=True)
        # Import options
        box = layout.box()
        box.label(text='Import options', icon='FILTER')
        col = box.column()
        col.prop(self, 'rel_path')
        col.prop(self, 'clean_name')
        col.prop(self, 'hidden_layers', icon='GHOST_ENABLED')
        col.prop(self, 'layer_index_name')

    def execute(self, context):
        if context.view_layer.objects.active and context.view_layer.objects.active.mode == 'EDIT':
            bpy.ops.object.mode_set(mode='OBJECT')

        start_time = time.time()
        print()

        if self.files:
            files = [f.name for f in self.files]
            d = self.directory
        elif self.filepath:
            d, filename = os.path.split(self.filepath)
            files = [filename]
        else:
            return {'CANCELLED'}

        random.seed()
        import_id = generate_random_id()

        for i, f in enumerate(files):
            collection_name = os.path.splitext(f)[0]
            collection = bpy.data.collections.new(collection_name)
            context.scene.collection.children.link(collection)

            psd_file = os.path.join(d, f)
            try:
                psd_layers, bboxes, image_size, png_dir = parse_psd(self, psd_file)
            except TypeError:   # None is returned, so something went wrong.
                msg = "Something went wrong. '{f}' is not imported!".format(f=f)
                self.report({'ERROR'}, msg)
                print("*** {}".format(msg))
                continue
            create_objects(self, psd_layers, bboxes, image_size,
                           png_dir, f, import_id, collection)
            print(''.join(('  Done', 114 * ' ')))

        if len(files) > 1:
            print_f = 'Files'
        else:
            print_f = 'File'
        print('\n{print_f} imported in {s:.2f} seconds'.format(
            print_f=print_f, s=time.time() - start_time))

        return {'FINISHED'}

def register():
    # Check if the class is already registered
    if "ImportPsdAsPlanes" not in bpy.types.Operator.__subclasses__():
        bpy.utils.register_class(ImportPsdAsPlanes)
    else:
        print("ImportPsdAsPlanes is already registered")

# Unregister function
def unregister():
    if "ImportPsdAsPlanes" in bpy.types.Operator.__subclasses__():
        bpy.utils.unregister_class(ImportPsdAsPlanes)

register()

bpy.ops.import_scene.psd('INVOKE_DEFAULT')