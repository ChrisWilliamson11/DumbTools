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
    tool_settings = context.tool_settings
    scene = context.scene

    # Add spacer to push controls to the center
    # Check if the current area is the Dope Sheet or Action Editor
    if (context.space_data.type == 'DOPESHEET_EDITOR' and context.space_data.mode in {'DOPESHEET', 'ACTION'}) or context.space_data.type == 'GRAPH_EDITOR':
        scene = context.scene
        tool_settings = context.tool_settings
        screen = context.screen



        layout.separator_spacer()

        row = layout.row(align=True)
        row.prop(tool_settings, "use_keyframe_insert_auto", text="", toggle=True)
        sub = row.row(align=True)
        sub.active = tool_settings.use_keyframe_insert_auto
        sub.popover(
            panel="TIME_PT_auto_keyframing",
            text="",
        )

        row = layout.row(align=True)
        row.operator("screen.frame_jump", text="", icon='REW').end = False
        row.operator("screen.keyframe_jump", text="", icon='PREV_KEYFRAME').next = False
        if not screen.is_animation_playing:
            # if using JACK and A/V sync:
            #   hide the play-reversed button
            #   since JACK transport doesn't support reversed playback
            if scene.sync_mode == 'AUDIO_SYNC' and context.preferences.system.audio_device == 'JACK':
                row.scale_x = 2
                row.operator("screen.animation_play", text="", icon='PLAY')
                row.scale_x = 1
            else:
                row.operator("screen.animation_play", text="", icon='PLAY_REVERSE').reverse = True
                row.operator("screen.animation_play", text="", icon='PLAY')
        else:
            row.scale_x = 2
            row.operator("screen.animation_play", text="", icon='PAUSE')
            row.scale_x = 1
        row.operator("screen.keyframe_jump", text="", icon='NEXT_KEYFRAME').next = True
        row.operator("screen.frame_jump", text="", icon='FF').end = True

        layout.separator_spacer()

        row = layout.row()
        if scene.show_subframe:
            row.scale_x = 1.15
            row.prop(scene, "frame_float", text="")
        else:
            row.scale_x = 0.95
            row.prop(scene, "frame_current", text="")

        row = layout.row(align=True)
        row.prop(scene, "use_preview_range", text="", toggle=True)
        sub = row.row(align=True)
        sub.scale_x = 0.8
        if not scene.use_preview_range:
            sub.prop(scene, "frame_start", text="Start")
            sub.prop(scene, "frame_end", text="End")
        else:
            sub.prop(scene, "frame_preview_start", text="Start")
            sub.prop(scene, "frame_preview_end", text="End")

    if (context.space_data.type == 'DOPESHEET_EDITOR'):
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
    bpy.utils.register_class(ANIM_MT_keyframe_options)
    bpy.utils.register_class(ANIM_PT_keyframe_type_options)
    bpy.utils.register_class(TIME_PT_auto_keyframing)  # Register the new panel
    bpy.utils.register_class(SetStartFrameOperator)  # Register the new operator
    bpy.utils.register_class(SetEndFrameOperator)    # Register the new operator
    
    # Extend existing headers
    bpy.types.DOPESHEET_HT_header.append(draw_navigation_controls)
    bpy.types.GRAPH_HT_header.append(draw_navigation_controls)

def unregister():
    bpy.utils.unregister_class(ANIM_MT_keyframe_options)
    bpy.utils.unregister_class(ANIM_PT_keyframe_type_options)
    bpy.utils.unregister_class(TIME_PT_auto_keyframing)  # Unregister the new panel
    bpy.utils.unregister_class(SetStartFrameOperator)  # Unregister the new operator
    bpy.utils.unregister_class(SetEndFrameOperator)    # Unregister the new operator
    
    # Remove our additions from the headers
    bpy.types.DOPESHEET_HT_header.remove(draw_navigation_controls)
    bpy.types.GRAPH_HT_header.remove(draw_navigation_controls)

register()
