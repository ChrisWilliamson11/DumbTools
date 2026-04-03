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

def register():
    # Preemptively unregister to avoid Blender 'registered before' info on reload
    for cls in [SetStartFrameOperator,
                SetEndFrameOperator]:
        try:
            bpy.utils.unregister_class(cls)
        except Exception:
            pass

    bpy.utils.register_class(SetStartFrameOperator)
    bpy.utils.register_class(SetEndFrameOperator)

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

def unregister():
    bpy.utils.unregister_class(SetStartFrameOperator)
    bpy.utils.unregister_class(SetEndFrameOperator)

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

register()
