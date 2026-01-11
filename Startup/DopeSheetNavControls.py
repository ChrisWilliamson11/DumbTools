import bpy
from bpy.types import Header, Menu, Panel, Operator

class ANIM_MT_keyframe_options(Menu):
    bl_label = "Keyframe Options"

    def draw(self, context):
        layout = self.layout
        tool_settings = context.tool_settings

        layout.prop(tool_settings, "use_keyframe_insert_keyingset", text="Only Active Keying Set")
        layout.prop(tool_settings, "use_record_with_nla", text="Layered Recording")

def draw_navigation_controls(self, context):
    layout = self.layout
    # Draw Set Start/Set End wherever this is appended (Timeline header, Dope Sheet footer)
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

class TIME_PT_auto_keyframing(Panel):
    bl_label = "Auto Keyframing"
    bl_options = {'HIDE_HEADER'}
    bl_region_type = 'HEADER'
    bl_space_type = 'DOPESHEET_EDITOR'  # Set to Dope Sheet Editor
    bl_ui_units_x = 9

    @classmethod
    def poll(cls, context):
        # Only for Dope Sheet, Action Editor, and Graph Editor
        return (context.space_data.type == 'DOPESHEET_EDITOR' and context.space_data.mode in {'DOPESHEET', 'ACTION'}) or context.space_data.type == 'GRAPH_EDITOR'

    def draw(self, context):
        layout = self.layout

        tool_settings = context.tool_settings
        prefs = context.preferences

        layout.active = tool_settings.use_keyframe_insert_auto

        layout.prop(tool_settings, "auto_keying_mode", expand=True)

        col = layout.column(align=True)
        col.prop(tool_settings, "use_keyframe_insert_keyingset", text="Only Active Keying Set", toggle=False)
        if not prefs.edit.use_keyframe_insert_available:
            col.prop(tool_settings, "use_record_with_nla", text="Layered Recording")

class ANIM_PT_keyframe_type_options(bpy.types.Panel):
    bl_label = "Keyframe Type Options"
    bl_space_type = 'DOPESHEET_EDITOR'
    bl_region_type = 'HEADER'
    bl_ui_units_x = 8

    def draw(self, context):
        layout = self.layout
        tool_settings = context.tool_settings

        layout.prop(tool_settings, "keyframe_type", text="")

def register():
    # Preemptively unregister to avoid Blender 'registered before' info on reload
    for cls in [ANIM_MT_keyframe_options,
                ANIM_PT_keyframe_type_options,
                TIME_PT_auto_keyframing,
                SetStartFrameOperator,
                SetEndFrameOperator]:
        try:
            bpy.utils.unregister_class(cls)
        except Exception:
            pass

    bpy.utils.register_class(ANIM_MT_keyframe_options)
    bpy.utils.register_class(ANIM_PT_keyframe_type_options)
    bpy.utils.register_class(TIME_PT_auto_keyframing)  # Register the new panel
    bpy.utils.register_class(SetStartFrameOperator)  # Register the new operator
    bpy.utils.register_class(SetEndFrameOperator)    # Register the new operator

    # Add to Timeline header and footers for relevant editors (conditional on Blender 5.0+ footer classes)
    if hasattr(bpy.types, "TIME_HT_header"):
        bpy.types.TIME_HT_header.append(draw_navigation_controls)
    if hasattr(bpy.types, "DOPESHEET_HT_footer"):
        bpy.types.DOPESHEET_HT_footer.append(draw_navigation_controls)
    if hasattr(bpy.types, "GRAPH_HT_footer"):
        bpy.types.GRAPH_HT_footer.append(draw_navigation_controls)
    if hasattr(bpy.types, "NLA_HT_footer"):
        bpy.types.NLA_HT_footer.append(draw_navigation_controls)
    if hasattr(bpy.types, "SEQUENCER_HT_footer"):
        bpy.types.SEQUENCER_HT_footer.append(draw_navigation_controls)

def unregister():
    bpy.utils.unregister_class(ANIM_MT_keyframe_options)
    bpy.utils.unregister_class(ANIM_PT_keyframe_type_options)
    bpy.utils.unregister_class(TIME_PT_auto_keyframing)  # Unregister the new panel
    bpy.utils.unregister_class(SetStartFrameOperator)  # Unregister the new operator
    bpy.utils.unregister_class(SetEndFrameOperator)    # Unregister the new operator

    # Remove our additions from the headers/footers
    if hasattr(bpy.types, "TIME_HT_header"):
        bpy.types.TIME_HT_header.remove(draw_navigation_controls)
    if hasattr(bpy.types, "DOPESHEET_HT_footer"):
        bpy.types.DOPESHEET_HT_footer.remove(draw_navigation_controls)
    if hasattr(bpy.types, "GRAPH_HT_footer"):
        bpy.types.GRAPH_HT_footer.remove(draw_navigation_controls)
    if hasattr(bpy.types, "NLA_HT_footer"):
        bpy.types.NLA_HT_footer.remove(draw_navigation_controls)
    if hasattr(bpy.types, "SEQUENCER_HT_footer"):
        bpy.types.SEQUENCER_HT_footer.remove(draw_navigation_controls)

register()
