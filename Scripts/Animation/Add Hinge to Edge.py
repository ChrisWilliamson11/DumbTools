# Tooltip: Create an animated hinge empty aligned to selected edge(s) in Edit Mode
import bpy
import bmesh
import math
from mathutils import Vector


def iter_fcurves(action):
    """
    Yields fcurves from an Action, handling both Legacy Blender and Blender 5+ Layered Animation.
    """
    if not action:
        return
    if hasattr(action, "fcurves") and action.fcurves:
        for fc in action.fcurves:
            yield fc
    if hasattr(action, "layers"):
        for layer in action.layers:
            if hasattr(layer, "strips"):
                for strip in layer.strips:
                    if hasattr(strip, "channelbags"):
                        for bag in strip.channelbags:
                            if hasattr(bag, "fcurves"):
                                for fc in bag.fcurves:
                                    yield fc
                    if hasattr(strip, "fcurves"):
                        for fc in strip.fcurves:
                            yield fc
                    elif hasattr(strip, "channels"):
                        for fc in strip.channels:
                            yield fc


class ANIM_OT_add_hinge_to_edge(bpy.types.Operator):
    bl_idname = "animation.add_hinge_to_edge"
    bl_label = "Add Hinge to Edge"
    bl_description = "Create an animated hinge empty aligned to selected edge(s) in Edit Mode"
    bl_options = {'REGISTER', 'UNDO'}

    duration: bpy.props.IntProperty(
        name="Duration (Frames)",
        description="Number of frames for the rotation animation",
        default=15,
        min=1
    )

    rotation_angle: bpy.props.FloatProperty(
        name="Rotation Angle (deg)",
        description="Rotation angle around local Z axis in degrees",
        default=-300.0
    )

    anim_direction: bpy.props.EnumProperty(
        name="Animation Direction",
        items=[
            ('ANGLE_TO_REST', "Angle to Rest (0°)", "Starts at offset angle, finishes at rest orientation on current frame"),
            ('REST_TO_ANGLE', "Rest (0°) to Angle", "Starts at rest (0°), finishes at offset angle on current frame"),
        ],
        default='ANGLE_TO_REST',
        description="Direction of the rotation animation relative to the edge rest pose"
    )

    flip_tangent: bpy.props.BoolProperty(
        name="Flip Tangent Direction",
        description="Invert the direction of the local Z axis along the edge",
        default=False
    )

    empty_size: bpy.props.FloatProperty(
        name="Empty Size",
        description="Display size of the hinge empty",
        default=0.2,
        min=0.001
    )

    empty_type: bpy.props.EnumProperty(
        name="Display As",
        items=[
            ('ARROWS', "Arrows", "Display as coordinate arrows"),
            ('PLAIN_AXES', "Plain Axes", "Display as plain coordinate axes"),
            ('SINGLE_ARROW', "Single Arrow", "Display as a single arrow pointing along Z"),
            ('CIRCLE', "Circle", "Display as a circle"),
            ('SPHERE', "Sphere", "Display as a sphere"),
        ],
        default='ARROWS',
        description="Display type for the hinge empty"
    )

    parent_to_mesh: bpy.props.BoolProperty(
        name="Parent to Mesh",
        description="Parent the hinge empty to the source mesh object",
        default=False
    )

    select_empty: bpy.props.BoolProperty(
        name="Select Empty",
        description="Switch to Object Mode and select the created empty",
        default=True
    )

    def draw(self, context):
        layout = self.layout
        col = layout.column(align=True)
        col.prop(self, "duration")
        col.prop(self, "rotation_angle")
        col.prop(self, "anim_direction")

        layout.separator()
        box = layout.box()
        box.label(text="Empty Settings:", icon='EMPTY_AXIS')
        box.prop(self, "empty_type")
        box.prop(self, "empty_size")
        box.prop(self, "flip_tangent")
        box.prop(self, "parent_to_mesh")
        box.prop(self, "select_empty")

    def invoke(self, context, event):
        # Validate selection before opening dialog
        obj = context.edit_object or context.active_object
        if not obj or obj.type != 'MESH' or obj.mode != 'EDIT':
            self.report({'WARNING'}, "Please select an edge in Edit Mode on a mesh")
            return {'CANCELLED'}

        bm = bmesh.from_edit_mesh(obj.data)
        bm.edges.ensure_lookup_table()
        if not any(e.select for e in bm.edges):
            self.report({'WARNING'}, "Please select at least one edge in Edit Mode")
            return {'CANCELLED'}

        return context.window_manager.invoke_props_dialog(self)

    def execute(self, context):
        obj = context.edit_object or context.active_object
        if not obj or obj.type != 'MESH':
            self.report({'WARNING'}, "Active object must be a Mesh")
            return {'CANCELLED'}

        if obj.mode != 'EDIT':
            self.report({'WARNING'}, "Object must be in Edit Mode")
            return {'CANCELLED'}

        bm = bmesh.from_edit_mesh(obj.data)
        bm.edges.ensure_lookup_table()
        selected_edges = [e for e in bm.edges if e.select]

        if not selected_edges:
            self.report({'WARNING'}, "Please select at least one edge in Edit Mode")
            return {'CANCELLED'}

        mw = obj.matrix_world
        edge_data = []

        for edge in selected_edges:
            v1 = edge.verts[0]
            v2 = edge.verts[1]
            world_v1 = mw @ v1.co
            world_v2 = mw @ v2.co
            center = (world_v1 + world_v2) * 0.5
            tangent = world_v2 - world_v1

            if tangent.length < 1e-6:
                continue

            tangent = tangent.normalized()
            if self.flip_tangent:
                tangent = -tangent

            edge_data.append((center, tangent, edge.index))

        if not edge_data:
            self.report({'WARNING'}, "No valid edges found (selected edges may have zero length)")
            return {'CANCELLED'}

        end_frame = context.scene.frame_current
        start_frame = end_frame - self.duration
        rad_angle = math.radians(self.rotation_angle)

        target_collection = obj.users_collection[0] if obj.users_collection else context.collection
        created_empties = []

        for center, tangent, edge_idx in edge_data:
            name = f"Hinge_{obj.name}_e{edge_idx}" if len(edge_data) > 1 else f"Hinge_{obj.name}"
            empty = bpy.data.objects.new(name=name, object_data=None)
            empty.empty_display_type = self.empty_type
            empty.empty_display_size = self.empty_size
            target_collection.objects.link(empty)

            empty.location = center

            # Align local Z axis to the edge tangent
            up_axis = 'X' if abs(tangent.y) > 0.99 else 'Y'
            quat = tangent.to_track_quat('Z', up_axis)
            empty.rotation_mode = 'ZYX'
            base_euler = quat.to_euler('ZYX')
            empty.rotation_euler = base_euler.copy()

            # Optional parent to mesh
            if self.parent_to_mesh:
                empty.parent = obj
                empty.matrix_parent_inverse = obj.matrix_world.inverted()

            # Determine start and end rotation values on local Z axis
            rest_z = base_euler.z
            if self.anim_direction == 'ANGLE_TO_REST':
                start_z = rest_z + rad_angle
                end_z = rest_z
            else:
                start_z = rest_z
                end_z = rest_z + rad_angle

            # Keyframe at start_frame
            empty.rotation_euler.z = start_z
            empty.keyframe_insert(data_path="rotation_euler", index=2, frame=start_frame)

            # Keyframe at end_frame
            empty.rotation_euler.z = end_z
            empty.keyframe_insert(data_path="rotation_euler", index=2, frame=end_frame)

            # Leave empty at end_frame rotation
            empty.rotation_euler.z = end_z

            # Set keyframe interpolation to BEZIER
            if empty.animation_data and empty.animation_data.action:
                action = empty.animation_data.action
                for fc in iter_fcurves(action):
                    if fc.data_path == "rotation_euler" and fc.array_index == 2:
                        for kp in fc.keyframe_points:
                            kp.interpolation = 'BEZIER'
                            kp.handle_left_type = 'AUTO_CLAMPED'
                            kp.handle_right_type = 'AUTO_CLAMPED'
                        fc.update()

            created_empties.append(empty)

        if self.select_empty and created_empties:
            bpy.ops.object.mode_set(mode='OBJECT')
            bpy.ops.object.select_all(action='DESELECT')
            for emp in created_empties:
                emp.select_set(True)
            context.view_layer.objects.active = created_empties[-1]

        self.report({'INFO'}, f"Created {len(created_empties)} hinge empty(ies)")
        return {'FINISHED'}


def register():
    if not hasattr(bpy.types, "ANIM_OT_add_hinge_to_edge"):
        try:
            bpy.utils.register_class(ANIM_OT_add_hinge_to_edge)
        except ValueError:
            bpy.utils.unregister_class(ANIM_OT_add_hinge_to_edge)
            bpy.utils.register_class(ANIM_OT_add_hinge_to_edge)


def unregister():
    try:
        bpy.utils.unregister_class(ANIM_OT_add_hinge_to_edge)
    except ValueError:
        pass


register()
bpy.ops.animation.add_hinge_to_edge('INVOKE_DEFAULT')
