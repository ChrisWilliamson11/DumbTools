# Tooltip: View all registered Blender handlers in a treeview, grouped by type, with removal support

import bpy
from bpy.types import Panel, Operator, PropertyGroup
from bpy.props import StringProperty, IntProperty, BoolProperty

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

# All handler lists available on bpy.app.handlers, grouped for readability.
# Each tuple is (attribute_name, display_label).
HANDLER_CATEGORIES = [
    ("Animation", [
        ("frame_change_pre", "Frame Change Pre"),
        ("frame_change_post", "Frame Change Post"),
        ("animation_playback_pre", "Animation Playback Pre"),
        ("animation_playback_post", "Animation Playback Post"),
    ]),
    ("File / Scene", [
        ("load_pre", "Load Pre"),
        ("load_post", "Load Post"),
        ("load_factory_preferences_post", "Load Factory Preferences Post"),
        ("load_factory_startup_post", "Load Factory Startup Post"),
        ("save_pre", "Save Pre"),
        ("save_post", "Save Post"),
    ]),
    ("Render", [
        ("render_pre", "Render Pre"),
        ("render_post", "Render Post"),
        ("render_write", "Render Write"),
        ("render_init", "Render Init"),
        ("render_complete", "Render Complete"),
        ("render_cancel", "Render Cancel"),
        ("render_stats", "Render Stats"),
    ]),
    ("Depsgraph", [
        ("depsgraph_update_pre", "Depsgraph Update Pre"),
        ("depsgraph_update_post", "Depsgraph Update Post"),
    ]),
    ("Undo / Redo", [
        ("undo_pre", "Undo Pre"),
        ("undo_post", "Undo Post"),
        ("redo_pre", "Redo Pre"),
        ("redo_post", "Redo Post"),
    ]),
    ("Composite", [
        ("composite_pre", "Composite Pre"),
        ("composite_post", "Composite Post"),
        ("composite_cancel", "Composite Cancel"),
    ]),
    ("Misc", [
        ("version_update", "Version Update"),
        ("xr_session_start_pre", "XR Session Start Pre"),
        ("object_bake_pre", "Object Bake Pre"),
        ("object_bake_complete", "Object Bake Complete"),
        ("object_bake_cancel", "Object Bake Cancel"),
    ]),
]

# Module-level state for category expand/collapse.
# Using a plain dict avoids writing to Scene data inside draw(), which Blender
# forbids (the cause of the "Writing to ID classes in this context" error).
_category_expanded = {cat_label: True for cat_label, _ in HANDLER_CATEGORIES}


def _get_handler_list(handler_attr):
    """Safely get a handler list by attribute name. Returns None if it doesn't exist."""
    return getattr(bpy.app.handlers, handler_attr, None)


def _handler_label(handler_func):
    """Build a human-readable label for a handler function."""
    module = getattr(handler_func, "__module__", None) or "?"
    qualname = getattr(handler_func, "__qualname__", None) or getattr(handler_func, "__name__", repr(handler_func))
    return f"{module}.{qualname}"


def _is_persistent(handler_func):
    """Check whether a handler was decorated with @persistent."""
    return getattr(handler_func, "_bpy_persistent", False)


# ---------------------------------------------------------------------------
# Properties – only the persistent-filter toggle needs to live on the Scene
# ---------------------------------------------------------------------------

class HandlerViewerProps(PropertyGroup):
    show_persistent_only: BoolProperty(
        name="Persistent Only",
        description="Show only handlers marked @persistent",
        default=False,
    )


# ---------------------------------------------------------------------------
# Operators
# ---------------------------------------------------------------------------

class HANDLERVIEWER_OT_toggle_category(Operator):
    """Expand or collapse a handler category"""
    bl_idname = "handler_viewer.toggle_category"
    bl_label = "Toggle Category"
    bl_options = {'INTERNAL'}

    category: StringProperty()

    def execute(self, context):
        _category_expanded[self.category] = not _category_expanded.get(self.category, True)
        return {'FINISHED'}


class HANDLERVIEWER_OT_remove_handler(Operator):
    """Remove a handler from its handler list"""
    bl_idname = "handler_viewer.remove_handler"
    bl_label = "Remove Handler"
    bl_description = "Unregister this handler callback"
    bl_options = {'INTERNAL'}

    handler_attr: StringProperty()
    handler_index: IntProperty()

    def execute(self, context):
        handler_list = _get_handler_list(self.handler_attr)
        if handler_list is None:
            self.report({'ERROR'}, f"Handler list '{self.handler_attr}' not found")
            return {'CANCELLED'}
        if self.handler_index < 0 or self.handler_index >= len(handler_list):
            self.report({'WARNING'}, "Handler index out of range (list may have changed)")
            return {'CANCELLED'}

        removed = handler_list[self.handler_index]
        handler_list.remove(removed)
        self.report({'INFO'}, f"Removed handler: {_handler_label(removed)}")
        return {'FINISHED'}

    def invoke(self, context, event):
        return context.window_manager.invoke_confirm(self, event)


class HANDLERVIEWER_OT_refresh(Operator):
    """Force the panel to redraw with fresh handler data"""
    bl_idname = "handler_viewer.refresh"
    bl_label = "Refresh"
    bl_description = "Refresh the handler list"
    bl_options = {'INTERNAL'}

    def execute(self, context):
        # Tagging a redraw is enough – the panel's draw() always reads live data.
        for area in context.screen.areas:
            area.tag_redraw()
        return {'FINISHED'}


class HANDLERVIEWER_OT_expand_all(Operator):
    """Expand all handler categories"""
    bl_idname = "handler_viewer.expand_all"
    bl_label = "Expand All"
    bl_options = {'INTERNAL'}

    def execute(self, context):
        for key in _category_expanded:
            _category_expanded[key] = True
        return {'FINISHED'}


class HANDLERVIEWER_OT_collapse_all(Operator):
    """Collapse all handler categories"""
    bl_idname = "handler_viewer.collapse_all"
    bl_label = "Collapse All"
    bl_options = {'INTERNAL'}

    def execute(self, context):
        for key in _category_expanded:
            _category_expanded[key] = False
        return {'FINISHED'}


# ---------------------------------------------------------------------------
# Panel
# ---------------------------------------------------------------------------

class VIEW3D_PT_handler_viewer(Panel):
    """Handler Viewer – lists all registered bpy.app.handlers"""
    bl_label = "Handler Viewer"
    bl_idname = "VIEW3D_PT_handler_viewer"
    bl_space_type = 'VIEW_3D'
    bl_region_type = 'UI'
    bl_category = "Tool"
    bl_options = {'DEFAULT_CLOSED'}

    def draw(self, context):
        layout = self.layout
        props = context.scene.handler_viewer_props

        # Toolbar row
        toolbar = layout.row(align=True)
        toolbar.operator("handler_viewer.refresh", text="", icon='FILE_REFRESH')
        toolbar.operator("handler_viewer.expand_all", text="", icon='TRIA_DOWN')
        toolbar.operator("handler_viewer.collapse_all", text="", icon='TRIA_RIGHT')
        toolbar.separator()
        toolbar.prop(props, "show_persistent_only", text="", icon='PINNED')

        layout.separator(factor=0.5)

        total_handlers = 0

        for cat_label, handler_entries in HANDLER_CATEGORIES:
            # Gather handlers for this category
            cat_handlers = []  # list of (attr, display_label, handler_list)
            for attr, display_label in handler_entries:
                hlist = _get_handler_list(attr)
                if hlist is not None:
                    cat_handlers.append((attr, display_label, hlist))

            # Count handlers in this category
            cat_count = 0
            for _, _, hlist in cat_handlers:
                cat_count += len(hlist)
            total_handlers += cat_count

            if cat_count == 0:
                continue  # Skip empty categories entirely

            # Read expand state from module-level dict (safe in draw)
            expanded = _category_expanded.get(cat_label, True)

            # Category header
            header = layout.row(align=True)
            op = header.operator(
                "handler_viewer.toggle_category",
                text="",
                icon='TRIA_DOWN' if expanded else 'TRIA_RIGHT',
                emboss=False,
            )
            op.category = cat_label
            header.label(text=f"{cat_label}  ({cat_count})")

            if not expanded:
                continue

            # Draw each handler type within this category
            cat_box = layout.box()
            for attr, display_label, hlist in cat_handlers:
                if len(hlist) == 0:
                    continue

                # Handler-type sub-header
                type_row = cat_box.row()
                type_row.label(text=display_label, icon='LAYER_ACTIVE')
                type_row.label(text=str(len(hlist)))

                # Individual handlers
                for idx, handler_func in enumerate(hlist):
                    is_persistent = _is_persistent(handler_func)

                    if props.show_persistent_only and not is_persistent:
                        continue

                    row = cat_box.row(align=True)
                    row.alignment = 'EXPAND'

                    # Indent slightly
                    sub = row.row()
                    sub.separator(factor=1.0)

                    # Persistent icon
                    if is_persistent:
                        sub.label(text="", icon='PINNED')
                    else:
                        sub.label(text="", icon='BLANK1')

                    # Handler label
                    sub.label(text=_handler_label(handler_func))

                    # Remove button
                    remove_op = row.operator(
                        "handler_viewer.remove_handler",
                        text="",
                        icon='PANEL_CLOSE',
                    )
                    remove_op.handler_attr = attr
                    remove_op.handler_index = idx

            cat_box.separator(factor=0.3)

        # Summary footer
        layout.separator(factor=0.5)
        footer = layout.row()
        footer.label(text=f"Total: {total_handlers} handlers registered", icon='INFO')


# ---------------------------------------------------------------------------
# Registration
# ---------------------------------------------------------------------------

classes = [
    HandlerViewerProps,
    HANDLERVIEWER_OT_toggle_category,
    HANDLERVIEWER_OT_remove_handler,
    HANDLERVIEWER_OT_refresh,
    HANDLERVIEWER_OT_expand_all,
    HANDLERVIEWER_OT_collapse_all,
    VIEW3D_PT_handler_viewer,
]


def register():
    for cls in classes:
        bpy.utils.register_class(cls)
    bpy.types.Scene.handler_viewer_props = bpy.props.PointerProperty(type=HandlerViewerProps)


def unregister():
    for cls in reversed(classes):
        bpy.utils.unregister_class(cls)
    if hasattr(bpy.types.Scene, 'handler_viewer_props'):
        del bpy.types.Scene.handler_viewer_props


register()
