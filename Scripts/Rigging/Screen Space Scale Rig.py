# Tooltip: Select objects and run - creates a controlling empty whose 'Screen Size' property uniformly drives all selected objects to appear the same size in screen space through the active camera. Accounts for each object's distance to camera and (optionally) focal length changes.

import bpy
from mathutils import Vector
from bpy.props import FloatProperty, BoolProperty
from bpy.types import Operator, Panel, PropertyGroup


# --------------------------------------------------------------------------
# Core maths
#
# For a perspective camera, the apparent angular size of an object is:
#   apparent = world_size / distance
#
# To keep apparent size constant as distance changes, we scale by:
#   scale = screen_size * (distance / reference_distance)
#
# When accounting for focal length (zoom), apparent size also scales with
# focal length, so to compensate:
#   scale = screen_size * (distance / reference_distance) * (reference_focal / focal_length)
#
# The controlling empty stores:
#   screen_size        – desired size multiplier (user-facing knob)
#   reference_distance – camera distance recorded at rig creation
#   reference_focal    – focal length recorded at rig creation
# --------------------------------------------------------------------------


# --------------------------------------------------------------------------
# Helpers
# --------------------------------------------------------------------------

def get_active_camera(context):
    """Return the scene's active camera object, or None."""
    return context.scene.camera


def get_centroid(objects):
    """Return the average world-space location of a list of objects."""
    total = Vector((0.0, 0.0, 0.0))
    for obj in objects:
        total += obj.matrix_world.translation
    return total / len(objects)


def add_screen_scale_driver(obj, ctrl_empty, camera, axis_idx, use_focal):
    """
    Set a screen-space scale driver on one axis of *obj*.

    LOC_DIFF measures the world-space distance between two objects directly,
    which means the driver stays live as objects or the camera move.
    """
    # Remove any pre-existing driver on this axis
    obj.driver_remove("scale", axis_idx)

    fcurve = obj.driver_add("scale", axis_idx)
    driver = fcurve.driver
    driver.type = 'SCRIPTED'

    # ---- screen_size property from the controlling empty ----
    v_sz = driver.variables.new()
    v_sz.name = "sz"
    v_sz.type = 'SINGLE_PROP'
    v_sz.targets[0].id_type = 'OBJECT'
    v_sz.targets[0].id = ctrl_empty
    v_sz.targets[0].data_path = '["screen_size"]'

    # ---- world-space distance between this object and the camera ----
    v_dist = driver.variables.new()
    v_dist.name = "dist"
    v_dist.type = 'LOC_DIFF'
    v_dist.targets[0].id_type = 'OBJECT'
    v_dist.targets[0].id = obj
    v_dist.targets[0].transform_space = 'WORLD_SPACE'
    v_dist.targets[1].id_type = 'OBJECT'
    v_dist.targets[1].id = camera
    v_dist.targets[1].transform_space = 'WORLD_SPACE'

    # ---- reference distance (stored on the empty at rig creation) ----
    v_refd = driver.variables.new()
    v_refd.name = "refd"
    v_refd.type = 'SINGLE_PROP'
    v_refd.targets[0].id_type = 'OBJECT'
    v_refd.targets[0].id = ctrl_empty
    v_refd.targets[0].data_path = '["reference_distance"]'

    if use_focal:
        # ---- live focal length from camera data ----
        v_fl = driver.variables.new()
        v_fl.name = "fl"
        v_fl.type = 'SINGLE_PROP'
        v_fl.targets[0].id_type = 'CAMERA'
        v_fl.targets[0].id = camera.data
        v_fl.targets[0].data_path = 'lens'

        # ---- reference focal length (stored on the empty at rig creation) ----
        v_rfl = driver.variables.new()
        v_rfl.name = "rfl"
        v_rfl.type = 'SINGLE_PROP'
        v_rfl.targets[0].id_type = 'OBJECT'
        v_rfl.targets[0].id = ctrl_empty
        v_rfl.targets[0].data_path = '["reference_focal"]'

        # Guard against zero distance; scale proportionally to distance and
        # inversely proportionally to focal length
        driver.expression = "sz * (max(dist, 0.0001) / refd) * (rfl / fl)"
    else:
        driver.expression = "sz * (max(dist, 0.0001) / refd)"


def remove_screen_scale_drivers(obj):
    """Strip screen-space scale drivers from all three axes of *obj*."""
    for axis_idx in range(3):
        try:
            obj.driver_remove("scale", axis_idx)
        except Exception:
            pass


# --------------------------------------------------------------------------
# Rig builder
# --------------------------------------------------------------------------

def build_screen_space_rig(context, target_objects, use_focal, initial_screen_size):
    """
    Create the controlling empty and wire up drivers for all target objects.
    Returns (ctrl_empty, info_message) or (None, error_message).
    """
    camera = get_active_camera(context)
    if camera is None:
        return None, "No active camera found. Assign a camera in Scene Properties."

    cam_loc = camera.matrix_world.translation
    cam_data = camera.data

    # Average camera distance becomes the reference distance.
    # At exactly this distance an object's scale will equal screen_size.
    raw_distances = [
        max((obj.matrix_world.translation - cam_loc).length, 0.001)
        for obj in target_objects
    ]
    ref_distance = sum(raw_distances) / len(raw_distances)
    ref_focal = cam_data.lens

    # ---- Create the controlling empty ----
    centroid = get_centroid(target_objects)

    ctrl_empty = bpy.data.objects.new("ScreenSize_Control", None)
    ctrl_empty.empty_display_type = 'SPHERE'
    ctrl_empty.empty_display_size = 0.3
    ctrl_empty.location = centroid

    # Place in the active collection so it appears alongside the targets
    active_col = context.view_layer.active_layer_collection.collection
    active_col.objects.link(ctrl_empty)

    # ---- Custom properties ----
    ctrl_empty["screen_size"] = float(initial_screen_size)
    ctrl_empty["reference_distance"] = float(ref_distance)
    ctrl_empty["reference_focal"] = float(ref_focal)

    # Attach UI metadata (Blender 3.0+)
    try:
        ui = ctrl_empty.id_properties_ui("screen_size")
        ui.update(
            min=0.0001, max=1000.0,
            soft_min=0.01, soft_max=10.0,
            description="Apparent screen-space size multiplier for all driven objects. "
                        "At the reference distance this equals the object's world-space scale."
        )
        ui = ctrl_empty.id_properties_ui("reference_distance")
        ui.update(
            min=0.001,
            description="Average camera distance recorded at rig creation. "
                        "Objects at this distance will have scale == screen_size."
        )
        ui = ctrl_empty.id_properties_ui("reference_focal")
        ui.update(
            min=1.0,
            description="Camera focal length recorded at rig creation "
                        "(used for focal-length compensation)."
        )
    except AttributeError:
        pass  # Older Blender builds without id_properties_ui

    # ---- Add scale drivers to every target object ----
    for obj in target_objects:
        for axis_idx in range(3):
            add_screen_scale_driver(obj, ctrl_empty, camera, axis_idx, use_focal)

    n = len(target_objects)
    focal_note = f" | Focal compensation ON (ref {ref_focal:.1f} mm)" if use_focal else ""
    message = (
        f"Screen-space rig built for {n} object(s). "
        f"Ref distance: {ref_distance:.3f} m{focal_note}. "
        f"Adjust 'Screen Size' on '{ctrl_empty.name}'."
    )
    return ctrl_empty, message


# --------------------------------------------------------------------------
# Property group
# --------------------------------------------------------------------------

class ScreenSpaceScaleProps(PropertyGroup):
    use_focal_compensation: BoolProperty(
        name="Focal Length Compensation",
        description=(
            "Keep apparent size constant when the camera focal length changes "
            "(e.g. animated zoom). When OFF, only camera-to-object distance is compensated"
        ),
        default=True
    )
    initial_screen_size: FloatProperty(
        name="Initial Screen Size",
        description=(
            "Starting value for the 'screen_size' property on the control empty. "
            "1.0 means objects keep their current scale at the reference (average) camera distance"
        ),
        default=1.0,
        min=0.0001,
        soft_max=10.0,
        precision=4
    )


# --------------------------------------------------------------------------
# Operators
# --------------------------------------------------------------------------

class OBJECT_OT_screen_space_scale_rig(Operator):
    """Rig selected objects so they all appear the same size in screen space through the active camera"""
    bl_idname = "object.screen_space_scale_rig"
    bl_label = "Build Screen Space Scale Rig"
    bl_options = {'REGISTER', 'UNDO'}

    @classmethod
    def poll(cls, context):
        return (
            context.mode == 'OBJECT'
            and context.scene.camera is not None
            and any(
                obj.type in {'MESH', 'CURVE', 'SURFACE', 'META', 'FONT',
                             'GPENCIL', 'GREASEPENCIL', 'EMPTY', 'LATTICE',
                             'ARMATURE', 'LIGHT', 'SPEAKER'}
                for obj in context.selected_objects
            )
        )

    def execute(self, context):
        props = context.scene.screen_space_scale_props

        target_objects = [
            obj for obj in context.selected_objects
            if obj.type in {'MESH', 'CURVE', 'SURFACE', 'META', 'FONT',
                            'GPENCIL', 'GREASEPENCIL', 'EMPTY', 'LATTICE',
                            'ARMATURE', 'LIGHT', 'SPEAKER'}
        ]

        if not target_objects:
            self.report({'ERROR'}, "No supported objects are selected.")
            return {'CANCELLED'}

        ctrl_empty, message = build_screen_space_rig(
            context,
            target_objects,
            use_focal=props.use_focal_compensation,
            initial_screen_size=props.initial_screen_size,
        )

        if ctrl_empty is None:
            self.report({'ERROR'}, message)
            return {'CANCELLED'}

        # Leave the controlling empty selected and active for easy property editing
        bpy.ops.object.select_all(action='DESELECT')
        ctrl_empty.select_set(True)
        context.view_layer.objects.active = ctrl_empty

        self.report({'INFO'}, message)
        return {'FINISHED'}


class OBJECT_OT_remove_screen_space_scale_rig(Operator):
    """Remove screen-space scale drivers from all selected objects"""
    bl_idname = "object.remove_screen_space_scale_rig"
    bl_label = "Remove Screen Space Drivers"
    bl_options = {'REGISTER', 'UNDO'}

    @classmethod
    def poll(cls, context):
        return context.mode == 'OBJECT' and bool(context.selected_objects)

    def execute(self, context):
        removed = 0
        for obj in context.selected_objects:
            remove_screen_scale_drivers(obj)
            removed += 1

        self.report({'INFO'}, f"Removed scale drivers from {removed} object(s).")
        return {'FINISHED'}


# --------------------------------------------------------------------------
# Panel
# --------------------------------------------------------------------------

class VIEW3D_PT_screen_space_scale(Panel):
    bl_label = "Screen Space Scale Rig"
    bl_idname = "VIEW3D_PT_screen_space_scale"
    bl_space_type = 'VIEW_3D'
    bl_region_type = 'UI'
    bl_category = "Rigging"

    def draw(self, context):
        layout = self.layout
        props = context.scene.screen_space_scale_props
        scene = context.scene

        # ---- Camera status ----
        box = layout.box()
        if scene.camera:
            cam = scene.camera
            box.label(text=f"Camera:  {cam.name}", icon='CAMERA_DATA')
            box.label(text=f"Focal length:  {cam.data.lens:.1f} mm", icon='DRIVER_DISTANCE')
        else:
            box.label(text="No active camera in scene", icon='ERROR')

        layout.separator()

        # ---- Settings ----
        box = layout.box()
        box.label(text="Settings", icon='SETTINGS')
        box.prop(props, "initial_screen_size")
        box.prop(props, "use_focal_compensation")

        layout.separator()

        # ---- Selection summary ----
        eligible = [
            obj for obj in context.selected_objects
            if obj.type in {'MESH', 'CURVE', 'SURFACE', 'META', 'FONT',
                            'GPENCIL', 'GREASEPENCIL', 'EMPTY', 'LATTICE',
                            'ARMATURE', 'LIGHT', 'SPEAKER'}
        ]
        n = len(eligible)
        layout.label(
            text=f"{n} object(s) selected",
            icon='OBJECT_DATA' if n > 0 else 'INFO'
        )

        # ---- Build button ----
        row = layout.row()
        row.scale_y = 1.5
        row.enabled = scene.camera is not None and n > 0
        row.operator("object.screen_space_scale_rig", icon='DRIVER_DISTANCE')

        layout.separator()

        # ---- How it works note ----
        col = layout.column(align=True)
        col.label(text="After building:", icon='INFO')
        col.label(text="  Select the empty and open")
        col.label(text="  Object Properties > Custom")
        col.label(text="  Properties. 'Screen Size'")
        col.label(text="  scales all objects together.")

        layout.separator()

        # ---- Remove ----
        layout.operator("object.remove_screen_space_scale_rig", icon='X')


# --------------------------------------------------------------------------
# Registration
# --------------------------------------------------------------------------

classes = [
    ScreenSpaceScaleProps,
    OBJECT_OT_screen_space_scale_rig,
    OBJECT_OT_remove_screen_space_scale_rig,
    VIEW3D_PT_screen_space_scale,
]


def register():
    for cls in classes:
        bpy.utils.register_class(cls)
    bpy.types.Scene.screen_space_scale_props = bpy.props.PointerProperty(
        type=ScreenSpaceScaleProps
    )


def unregister():
    for cls in reversed(classes):
        bpy.utils.unregister_class(cls)
    if hasattr(bpy.types.Scene, 'screen_space_scale_props'):
        del bpy.types.Scene.screen_space_scale_props


register()
