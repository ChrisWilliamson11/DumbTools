# Tooltip: Live shape key viewer that displays all shape keys and their current values for a selected object

import bpy
from bpy.types import Panel, PropertyGroup
from bpy.props import PointerProperty

class ShapeKeyViewerProperties(PropertyGroup):
    """Properties for the Shape Key Viewer"""
    target_object: PointerProperty(
        name="Target Object",
        type=bpy.types.Object,
        poll=lambda self, obj: obj.type == 'MESH' and obj.data.shape_keys is not None,
        description="Select a mesh object with shape keys to view"
    )

class SHAPEKEY_PT_viewer_panel(Panel):
    """Shape Key Viewer Panel in 3D View"""
    bl_label = "Shape Key Viewer"
    bl_idname = "VIEW3D_PT_shape_key_viewer"
    bl_space_type = 'VIEW_3D'
    bl_region_type = 'UI'
    bl_category = 'Shape Keys'

    def draw(self, context):
        layout = self.layout
        scene = context.scene
        props = scene.shape_key_viewer_props

        # Object selection
        layout.prop(props, "target_object", text="Object")

        # If no object selected, show message
        if not props.target_object:
            layout.label(text="Select an object with shape keys", icon='INFO')
            return

        obj = props.target_object

        # Check if object has shape keys
        if not obj.data.shape_keys:
            layout.label(text="Selected object has no shape keys", icon='ERROR')
            return

        # Display shape keys
        shape_keys = obj.data.shape_keys.key_blocks

        if len(shape_keys) <= 1:  # Only Basis key
            layout.label(text="No shape keys found (only Basis)", icon='INFO')
            return

        # Create a box for the shape key list
        box = layout.box()
        box.label(text=f"Shape Keys ({len(shape_keys) - 1}):", icon='SHAPEKEY_DATA')

        # Display each shape key (skip Basis)
        for i, key in enumerate(shape_keys):
            if key.name == "Basis":
                continue

            row = box.row(align=True)

            # Shape key name
            row.label(text=key.name)

            # Current value with color coding
            value = key.value
            if value > 0.01:
                row.alert = True  # Highlight active shape keys

            # Display value with precision
            row.label(text=f"{value:.3f}")

            # Min/Max range info
            if key.slider_min != 0.0 or key.slider_max != 1.0:
                row.label(text=f"[{key.slider_min:.1f}-{key.slider_max:.1f}]", icon='DRIVER')

        # Add refresh button and info
        layout.separator()
        row = layout.row()
        row.operator("wm.redraw_timer", text="Refresh", icon='FILE_REFRESH')

        # Show total count
        active_count = sum(1 for key in shape_keys if key.name != "Basis" and key.value > 0.01)
        layout.label(text=f"Active: {active_count} / {len(shape_keys) - 1}")

def register():
    """Register the addon"""
    bpy.utils.register_class(ShapeKeyViewerProperties)
    bpy.utils.register_class(SHAPEKEY_PT_viewer_panel)
    bpy.types.Scene.shape_key_viewer_props = PointerProperty(type=ShapeKeyViewerProperties)
    print("Shape Key Viewer registered successfully!")

def unregister():
    """Unregister the addon"""
    bpy.utils.unregister_class(SHAPEKEY_PT_viewer_panel)
    bpy.utils.unregister_class(ShapeKeyViewerProperties)
    del bpy.types.Scene.shape_key_viewer_props
    print("Shape Key Viewer unregistered")

register()