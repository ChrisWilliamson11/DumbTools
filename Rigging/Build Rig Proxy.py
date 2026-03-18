# Tooltip: Create renderable proxy meshes for armature bones - select an armature and run to generate shapes that match each bone's position, rotation, and length

import bpy
import bmesh
from bpy.props import EnumProperty, FloatProperty, BoolProperty, StringProperty
from bpy.types import Panel, Operator, PropertyGroup
from mathutils import Vector, Matrix


def create_bone_mesh(name, shape_type='OCTAHEDRAL', thickness=0.1, bone_length=1.0):
    """Create a mesh that represents a bone shape.

    Mesh is built with origin at bone TAIL (0,0,0) and extends to HEAD at (0, -bone_length, 0).
    This matches Blender's BONE parent type which places children at the tail.
    """
    mesh = bpy.data.meshes.new(name)
    bm = bmesh.new()

    # Scale thickness relative to bone length for consistent proportions
    t = thickness * bone_length

    if shape_type == 'CUBE':
        # Simple cube - from tail (0,0,0) to head (0, -bone_length, 0)
        verts = [
            Vector((-t, 0, -t)),
            Vector((t, 0, -t)),
            Vector((t, 0, t)),
            Vector((-t, 0, t)),
            Vector((-t, -bone_length, -t)),
            Vector((t, -bone_length, -t)),
            Vector((t, -bone_length, t)),
            Vector((-t, -bone_length, t)),
        ]
        for v in verts:
            bm.verts.new(v)
        bm.verts.ensure_lookup_table()

        faces = [
            (0, 1, 2, 3), (4, 7, 6, 5),  # Top/bottom
            (0, 4, 5, 1), (2, 6, 7, 3),  # Front/back
            (0, 3, 7, 4), (1, 5, 6, 2),  # Sides
        ]
        for f in faces:
            bm.faces.new([bm.verts[i] for i in f])

    elif shape_type == 'OCTAHEDRAL':
        # Classic bone shape - octahedron
        # Origin at tail (0,0,0), head at (0, -bone_length, 0)
        # Wide point at 10% from head toward tail
        wide_y = -bone_length * 0.9  # 90% along from tail to head = 10% from head

        verts = [
            # Wide square
            Vector((-t, wide_y, 0)),
            Vector((t, wide_y, 0)),
            Vector((0, wide_y, -t)),
            Vector((0, wide_y, t)),
            # Tail point (origin)
            Vector((0, 0, 0)),
            # Head point
            Vector((0, -bone_length, 0)),
        ]
        for v in verts:
            bm.verts.new(v)
        bm.verts.ensure_lookup_table()

        # Faces
        faces = [
            (0, 2, 4), (2, 1, 4), (1, 3, 4), (3, 0, 4),  # Tail pyramid
            (0, 5, 2), (2, 5, 1), (1, 5, 3), (3, 5, 0),  # Head pyramid
        ]
        for f in faces:
            bm.faces.new([bm.verts[i] for i in f])

    elif shape_type == 'STICK':
        # Cylinder from tail to head
        bmesh.ops.create_cone(bm, cap_ends=True, cap_tris=False, segments=8,
                              radius1=t, radius2=t, depth=bone_length)
        # Reposition: cone is centered at origin, we need tail at 0, head at -bone_length
        for v in bm.verts:
            # Rotate so length is along Y, then shift
            v.co.y, v.co.z = -v.co.z, v.co.y
            v.co.y -= bone_length / 2  # Shift so tail is at 0

    elif shape_type == 'TAPERED':
        # Tapered from tail (wider) to head (narrower)
        bmesh.ops.create_cone(bm, cap_ends=True, cap_tris=False, segments=4,
                              radius1=t * 0.3, radius2=t * 1.5, depth=bone_length)
        for v in bm.verts:
            # Rotate so length is along Y
            v.co.y, v.co.z = -v.co.z, v.co.y
            v.co.y -= bone_length / 2
            # Rotate 45 degrees around Y for diamond cross-section
            x, z = v.co.x, v.co.z
            v.co.x = x * 0.707 - z * 0.707
            v.co.z = x * 0.707 + z * 0.707

    bm.to_mesh(mesh)
    bm.free()
    return mesh


def build_rig_proxy(armature, shape_type='OCTAHEDRAL', thickness=0.1,
                    collection_name=None, only_deform=False):
    """Build proxy meshes for all bones in the armature"""
    if armature.type != 'ARMATURE':
        return None, "Selected object is not an armature"

    # Create or get collection for proxies
    if collection_name is None or collection_name == "":
        collection_name = f"{armature.name}_Proxy"

    if collection_name in bpy.data.collections:
        proxy_collection = bpy.data.collections[collection_name]
    else:
        proxy_collection = bpy.data.collections.new(collection_name)
        bpy.context.scene.collection.children.link(proxy_collection)

    created_objects = []

    for bone in armature.data.bones:
        # Skip non-deform bones if filter is enabled
        if only_deform and not bone.use_deform:
            continue

        # Get pose bone for world transforms
        pose_bone = armature.pose.bones.get(bone.name)
        if pose_bone is None:
            print(f"Warning: Could not find pose bone '{bone.name}', skipping")
            continue

        # Get bone length (in armature local space)
        bone_length = bone.length

        # Create the mesh - built along local Y from 0 to 1
        mesh_name = f"{armature.name}_{bone.name}_proxy"
        mesh = create_bone_mesh(mesh_name, shape_type, thickness, bone_length)

        # Create the object
        obj = bpy.data.objects.new(mesh_name, mesh)
        proxy_collection.objects.link(obj)

        # Calculate the bone's tail position in world space
        # pose_bone.matrix is in armature space, with origin at bone head
        # Bone tail in armature space = pose_bone.tail
        bone_tail_world = armature.matrix_world @ pose_bone.tail

        # Get bone's world orientation from pose matrix
        bone_matrix_world = armature.matrix_world @ pose_bone.matrix

        # Position object at bone tail with bone's orientation
        # Extract rotation from bone matrix
        obj.matrix_world = bone_matrix_world
        obj.location = bone_tail_world

        # Parent to bone - use BONE_RELATIVE to keep current world transform
        obj.parent = armature
        obj.parent_type = 'BONE'
        obj.parent_bone = bone.name

        # Calculate proper parent inverse to maintain current world position
        # Parent matrix for BONE type is: armature.matrix_world @ pose_bone.matrix @ tail_offset
        tail_offset = Matrix.Translation((0, bone_length, 0))
        parent_matrix = armature.matrix_world @ pose_bone.matrix @ tail_offset
        obj.matrix_parent_inverse = parent_matrix.inverted()

        created_objects.append(obj)

    return created_objects, f"Created {len(created_objects)} proxy meshes in '{collection_name}'"


# --- Property Group ---
class RigProxyProperties(PropertyGroup):
    shape_type: EnumProperty(
        name="Shape",
        description="Shape of the proxy meshes",
        items=[
            ('OCTAHEDRAL', "Octahedral", "Classic bone shape - diamond/pyramid"),
            ('CUBE', "Cube", "Simple stretched cubes"),
            ('STICK', "Stick", "Cylindrical sticks"),
            ('TAPERED', "Tapered", "Tapered boxes - wider at root"),
        ],
        default='OCTAHEDRAL'
    )
    thickness: FloatProperty(
        name="Thickness",
        description="Relative thickness of the bone shapes",
        default=0.05,
        min=0.001,
        max=1.0,
        step=1,
        precision=3
    )
    only_deform: BoolProperty(
        name="Deform Bones Only",
        description="Only create proxies for bones marked as deform bones",
        default=False
    )
    collection_name: StringProperty(
        name="Collection",
        description="Name of collection to put proxies in (leave empty for auto)",
        default=""
    )


# --- Operators ---
class ARMATURE_OT_build_rig_proxy(Operator):
    """Create renderable proxy meshes for all bones in the selected armature"""
    bl_idname = "armature.build_rig_proxy"
    bl_label = "Build Rig Proxy"
    bl_options = {'REGISTER', 'UNDO'}

    @classmethod
    def poll(cls, context):
        return context.active_object and context.active_object.type == 'ARMATURE'

    def execute(self, context):
        props = context.scene.rig_proxy_props
        armature = context.active_object

        objects, message = build_rig_proxy(
            armature,
            shape_type=props.shape_type,
            thickness=props.thickness,
            collection_name=props.collection_name,
            only_deform=props.only_deform
        )

        if objects:
            # Select the created objects
            bpy.ops.object.select_all(action='DESELECT')
            for obj in objects:
                obj.select_set(True)
            context.view_layer.objects.active = objects[0]
            self.report({'INFO'}, message)
            return {'FINISHED'}
        else:
            self.report({'ERROR'}, message)
            return {'CANCELLED'}


class ARMATURE_OT_delete_rig_proxy(Operator):
    """Delete all proxy meshes in the proxy collection for the selected armature"""
    bl_idname = "armature.delete_rig_proxy"
    bl_label = "Delete Rig Proxy"
    bl_options = {'REGISTER', 'UNDO'}

    @classmethod
    def poll(cls, context):
        return context.active_object and context.active_object.type == 'ARMATURE'

    def execute(self, context):
        props = context.scene.rig_proxy_props
        armature = context.active_object

        # Determine collection name
        col_name = props.collection_name if props.collection_name else f"{armature.name}_Proxy"

        if col_name not in bpy.data.collections:
            self.report({'WARNING'}, f"Collection '{col_name}' not found")
            return {'CANCELLED'}

        collection = bpy.data.collections[col_name]

        # Delete all objects in the collection
        deleted_count = len(collection.objects)
        for obj in list(collection.objects):
            bpy.data.objects.remove(obj, do_unlink=True)

        # Optionally remove the empty collection
        bpy.data.collections.remove(collection)

        self.report({'INFO'}, f"Deleted {deleted_count} proxy meshes and collection '{col_name}'")
        return {'FINISHED'}


# --- Panel ---
class VIEW3D_PT_rig_proxy(Panel):
    """Rig Proxy panel in 3D viewport sidebar"""
    bl_label = "Build Rig Proxy"
    bl_idname = "VIEW3D_PT_rig_proxy"
    bl_space_type = 'VIEW_3D'
    bl_region_type = 'UI'
    bl_category = "Rigging"

    def draw(self, context):
        layout = self.layout
        props = context.scene.rig_proxy_props

        # Check if armature is selected
        armature = context.active_object
        if not armature or armature.type != 'ARMATURE':
            layout.label(text="Select an Armature", icon='ERROR')
            return

        layout.label(text=f"Armature: {armature.name}", icon='ARMATURE_DATA')

        # Settings
        box = layout.box()
        box.label(text="Settings:", icon='SETTINGS')
        box.prop(props, "shape_type")
        box.prop(props, "thickness")
        box.prop(props, "only_deform")
        box.prop(props, "collection_name", text="Collection")

        # Buttons
        layout.separator()
        layout.operator("armature.build_rig_proxy", icon='MESH_CUBE')
        layout.operator("armature.delete_rig_proxy", icon='TRASH')


# --- Registration ---
classes = [
    RigProxyProperties,
    ARMATURE_OT_build_rig_proxy,
    ARMATURE_OT_delete_rig_proxy,
    VIEW3D_PT_rig_proxy,
]

def register():
    for cls in classes:
        bpy.utils.register_class(cls)
    bpy.types.Scene.rig_proxy_props = bpy.props.PointerProperty(type=RigProxyProperties)

def unregister():
    for cls in reversed(classes):
        bpy.utils.unregister_class(cls)
    if hasattr(bpy.types.Scene, 'rig_proxy_props'):
        del bpy.types.Scene.rig_proxy_props

register()

