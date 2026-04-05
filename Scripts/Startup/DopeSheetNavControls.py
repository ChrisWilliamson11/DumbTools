# Tooltip: Add navigation controls to the Dope Sheet for quick keyframe browsing
import bpy
from bpy.types import Header, Menu, Panel, Operator

def draw_timeline_header(self, context):
    # Only draw in the actual Timeline editor, not Dope Sheet etc.
    if context.area.ui_type == 'TIMELINE':
        layout = self.layout
        row = layout.row(align=True)
        row.operator("scene.set_start_frame", text="Set Start", icon='TRIA_RIGHT')
        row.operator("scene.set_end_frame", text="Set End", icon='TRIA_LEFT')

def draw_footer_controls(self, context):
    layout = self.layout
    # Draw Set Start/Set End in the playback controls area
    row = layout.row(align=True)
    row.operator("scene.set_start_frame", text="Set Start", icon='TRIA_RIGHT')
    row.operator("scene.set_end_frame", text="Set End", icon='TRIA_LEFT')

# Define operators for setting start and end frames
class SetStartFrameOperator(bpy.types.Operator):
    bl_idname = "scene.set_start_frame"
    bl_label = "Set Start Frame"

    def execute(self, context):
        context.scene.frame_start = context.scene.frame_current
        return {'FINISHED'}

class SetEndFrameOperator(bpy.types.Operator):
    bl_idname = "scene.set_end_frame"
    bl_label = "Set End Frame"

    def execute(self, context):
        context.scene.frame_end = context.scene.frame_current
        return {'FINISHED'}

class MarkerSetStartFrameOperator(bpy.types.Operator):
    bl_idname = "scene.marker_set_start_frame"
    bl_label = "Set Start"

    @classmethod
    def poll(cls, context):
        if not context.scene:
            return False
        return any(m.select for m in context.scene.timeline_markers)

    def execute(self, context):
        selected_markers = [m for m in context.scene.timeline_markers if m.select]
        if selected_markers:
            context.scene.frame_start = selected_markers[0].frame
        return {'FINISHED'}

class MarkerSetEndFrameOperator(bpy.types.Operator):
    bl_idname = "scene.marker_set_end_frame"
    bl_label = "Set End"

    @classmethod
    def poll(cls, context):
        if not context.scene:
            return False
        return any(m.select for m in context.scene.timeline_markers)

    def execute(self, context):
        selected_markers = [m for m in context.scene.timeline_markers if m.select]
        if selected_markers:
            context.scene.frame_end = selected_markers[0].frame
        return {'FINISHED'}

class MarkersFromSceneRangeOperator(bpy.types.Operator):
    bl_idname = "scene.markers_from_scene_range"
    bl_label = "Markers from Scene Range"

    def execute(self, context):
        scene = context.scene
        scene.timeline_markers.new(name="scene start", frame=scene.frame_start)
        scene.timeline_markers.new(name="scene end", frame=scene.frame_end)
        return {'FINISHED'}

def draw_marker_menu_additions(self, context):
    layout = self.layout
    layout.separator()
    layout.operator("scene.marker_set_start_frame", text="Set Start")
    layout.operator("scene.marker_set_end_frame", text="Set End")
    layout.operator("scene.markers_from_scene_range", text="Markers from Scene Range")

def register():
    # Preemptively unregister to avoid Blender 'registered before' info on reload
    for cls in [SetStartFrameOperator,
                SetEndFrameOperator,
                MarkerSetStartFrameOperator,
                MarkerSetEndFrameOperator,
                MarkersFromSceneRangeOperator]:
        try:
            bpy.utils.unregister_class(cls)
        except Exception:
            pass

    bpy.utils.register_class(SetStartFrameOperator)
    bpy.utils.register_class(SetEndFrameOperator)
    bpy.utils.register_class(MarkerSetStartFrameOperator)
    bpy.utils.register_class(MarkerSetEndFrameOperator)
    bpy.utils.register_class(MarkersFromSceneRangeOperator)

    # Add to Timeline header (via DopeSheet header with check)
    if hasattr(bpy.types, "DOPESHEET_HT_header"):
        bpy.types.DOPESHEET_HT_header.append(draw_timeline_header)
    
    # Add to Playback Controls in footers
    if hasattr(bpy.types, "DOPESHEET_HT_playback_controls"):
        bpy.types.DOPESHEET_HT_playback_controls.append(draw_footer_controls)
    if hasattr(bpy.types, "GRAPH_HT_playback_controls"):
        bpy.types.GRAPH_HT_playback_controls.append(draw_footer_controls)
    if hasattr(bpy.types, "NLA_HT_playback_controls"):
        bpy.types.NLA_HT_playback_controls.append(draw_footer_controls)
    if hasattr(bpy.types, "SEQUENCER_HT_playback_controls"):
        bpy.types.SEQUENCER_HT_playback_controls.append(draw_footer_controls)

    # Add to Editor Context menus
    if hasattr(bpy.types, "DOPESHEET_MT_context_menu"):
        bpy.types.DOPESHEET_MT_context_menu.append(draw_marker_menu_additions)
    if hasattr(bpy.types, "TIME_MT_context_menu"):
        bpy.types.TIME_MT_context_menu.append(draw_marker_menu_additions)
    if hasattr(bpy.types, "GRAPH_MT_context_menu"):
        bpy.types.GRAPH_MT_context_menu.append(draw_marker_menu_additions)
    if hasattr(bpy.types, "NLA_MT_context_menu"):
        bpy.types.NLA_MT_context_menu.append(draw_marker_menu_additions)
    if hasattr(bpy.types, "SEQUENCER_MT_context_menu"):
        bpy.types.SEQUENCER_MT_context_menu.append(draw_marker_menu_additions)

def unregister():
    bpy.utils.unregister_class(SetStartFrameOperator)
    bpy.utils.unregister_class(SetEndFrameOperator)
    bpy.utils.unregister_class(MarkerSetStartFrameOperator)
    bpy.utils.unregister_class(MarkerSetEndFrameOperator)
    bpy.utils.unregister_class(MarkersFromSceneRangeOperator)

    # Remove our additions
    if hasattr(bpy.types, "DOPESHEET_HT_header"):
        bpy.types.DOPESHEET_HT_header.remove(draw_timeline_header)
    
    if hasattr(bpy.types, "DOPESHEET_HT_playback_controls"):
        bpy.types.DOPESHEET_HT_playback_controls.remove(draw_footer_controls)
    if hasattr(bpy.types, "GRAPH_HT_playback_controls"):
        bpy.types.GRAPH_HT_playback_controls.remove(draw_footer_controls)
    if hasattr(bpy.types, "NLA_HT_playback_controls"):
        bpy.types.NLA_HT_playback_controls.remove(draw_footer_controls)
    if hasattr(bpy.types, "SEQUENCER_HT_playback_controls"):
        bpy.types.SEQUENCER_HT_playback_controls.remove(draw_footer_controls)

    if hasattr(bpy.types, "DOPESHEET_MT_context_menu"):
        bpy.types.DOPESHEET_MT_context_menu.remove(draw_marker_menu_additions)
    if hasattr(bpy.types, "TIME_MT_context_menu"):
        bpy.types.TIME_MT_context_menu.remove(draw_marker_menu_additions)
    if hasattr(bpy.types, "GRAPH_MT_context_menu"):
        bpy.types.GRAPH_MT_context_menu.remove(draw_marker_menu_additions)
    if hasattr(bpy.types, "NLA_MT_context_menu"):
        bpy.types.NLA_MT_context_menu.remove(draw_marker_menu_additions)
    if hasattr(bpy.types, "SEQUENCER_MT_context_menu"):
        bpy.types.SEQUENCER_MT_context_menu.remove(draw_marker_menu_additions)

register()
