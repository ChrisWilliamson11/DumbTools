import bpy

class VSEGoToNextClipStart(bpy.types.Operator):
    """Go to the First Frame of the Next Clip"""
    bl_idname = "sequencer.goto_next_clip_start"
    bl_label = "Go to Next Clip Start"

    def execute(self, context):
        current_frame = context.scene.frame_current
        next_clip_frame = None
        for seq in context.scene.sequence_editor.sequences:
            if seq.frame_final_start > current_frame:
                if next_clip_frame is None or seq.frame_final_start < next_clip_frame:
                    next_clip_frame = seq.frame_final_start
        if next_clip_frame is not None:
            context.scene.frame_set(next_clip_frame)
        return {'FINISHED'}

class VSEGoToPreviousClipStart(bpy.types.Operator):
    """Go to the First Frame of the Previous Clip"""
    bl_idname = "sequencer.goto_previous_clip_start"
    bl_label = "Go to Previous Clip Start"

    def execute(self, context):
        current_frame = context.scene.frame_current
        previous_clip_frame = None
        for seq in context.scene.sequence_editor.sequences:
            if seq.frame_final_start < current_frame:
                if previous_clip_frame is None or seq.frame_final_start > previous_clip_frame:
                    previous_clip_frame = seq.frame_final_start
        if previous_clip_frame is not None:
            context.scene.frame_set(previous_clip_frame)
        return {'FINISHED'}

class VSESelectClipsAfterCurrentFrame(bpy.types.Operator):
    """Select All Clips That Start After Current Frame"""
    bl_idname = "sequencer.select_clips_after_current_frame"
    bl_label = "Select Clips After Current Frame"
    bl_options = {'REGISTER', 'UNDO'}

    def execute(self, context):
        current_frame = context.scene.frame_current

        for seq in context.scene.sequence_editor.sequences:
            if seq.frame_final_start > current_frame:
                seq.select = True
            else:
                seq.select = False

        self.report({'INFO'}, "Clips selection updated.")
        return {'FINISHED'}

class VSESetClipToCurrentFrame(bpy.types.Operator):
    """Set selected clips to start at the current frame"""
    bl_idname = "sequencer.set_clip_to_current_frame"
    bl_label = "Set Clip to Current Frame"
    bl_options = {'REGISTER', 'UNDO'}

    def execute(self, context):
        current_frame = context.scene.frame_current
        selected_clips = [seq for seq in context.scene.sequence_editor.sequences if seq.select]

        if not selected_clips:
            self.report({'WARNING'}, "No clips selected")
            return {'CANCELLED'}

        # Find the earliest clip among the selected
        first_clip = min(selected_clips, key=lambda s: s.frame_final_start)
        offset = (current_frame - first_clip.frame_final_start) // 2  # Divide the offset by 2

        # Move all selected clips by the calculated offset
        for clip in selected_clips:
            clip.frame_start += offset
            clip.frame_final_start += offset
            clip.frame_final_end += offset

            # Adjust the strip channel to ensure it's visible
            clip.channel = max(clip.channel, context.scene.sequence_editor.active_strip.channel)

        return {'FINISHED'}

class VSESetDurationToSelected(bpy.types.Operator):
    """Set Scene Start and End Time to Selected Clip"""
    bl_idname = "sequencer.set_duration_to_selected"
    bl_label = "Set Duration to Selected"
    bl_options = {'REGISTER', 'UNDO'}

    def execute(self, context):
        selected_clips = [seq for seq in context.scene.sequence_editor.sequences if seq.select]
        
        if not selected_clips:
            self.report({'WARNING'}, "No clips selected")
            return {'CANCELLED'}

        # Set scene start and end based on the selected clip
        first_clip = min(selected_clips, key=lambda s: s.frame_final_start)
        last_clip = max(selected_clips, key=lambda s: s.frame_final_end)
        
        context.scene.frame_start = first_clip.frame_final_start
        context.scene.frame_end = last_clip.frame_final_end

        return {'FINISHED'}

class VSEMoveSelectedToStart(bpy.types.Operator):
    """Move Selected Clips to Start at Current Frame"""
    bl_idname = "sequencer.move_selected_to_start"
    bl_label = "Move Selected to Start"
    bl_options = {'REGISTER', 'UNDO'}

    def execute(self, context):
        current_frame = context.scene.frame_current
        selected_clips = [seq for seq in context.scene.sequence_editor.sequences if seq.select]

        for clip in selected_clips:
            offset = current_frame - clip.frame_final_start
            clip.frame_start += offset
            clip.frame_final_start += offset
            clip.frame_final_end += offset

        return {'FINISHED'}

class VSEMoveSelectedToEnd(bpy.types.Operator):
    """Move Selected Clips to End at Current Frame"""
    bl_idname = "sequencer.move_selected_to_end"
    bl_label = "Move Selected to End"
    bl_options = {'REGISTER', 'UNDO'}

    def execute(self, context):
        current_frame = context.scene.frame_current
        selected_clips = [seq for seq in context.scene.sequence_editor.sequences if seq.select]

        for clip in selected_clips:
            offset = current_frame - clip.frame_final_end
            clip.frame_start += offset
            clip.frame_final_start += offset
            clip.frame_final_end += offset

        return {'FINISHED'}

class VSEDumbToolsMenu(bpy.types.Menu):
    bl_label = "Dumbtools"
    bl_idname = "SEQUENCER_MT_dumbtools"

    def draw(self, context):
        layout = self.layout
        layout.operator("sequencer.goto_next_clip_start", text="Go to Next Clip Start")
        layout.operator("sequencer.goto_previous_clip_start", text="Go to Previous Clip Start")
        layout.operator("sequencer.select_clips_after_current_frame", text="Select Clips After Current Frame")
        layout.operator("sequencer.set_clip_to_current_frame", text="Set Clip to Current Frame")
        layout.operator("sequencer.set_duration_to_selected", text="Set Duration to Selected")  # New tool
        layout.operator("sequencer.move_selected_to_start", text="Move Selected to Start")  # New tool
        layout.operator("sequencer.move_selected_to_end", text="Move Selected to End")  # New tool

def sequencer_menu_func(self, context):
    self.layout.menu("SEQUENCER_MT_dumbtools")

def register():
    bpy.utils.register_class(VSEGoToNextClipStart)
    bpy.utils.register_class(VSEGoToPreviousClipStart)
    bpy.utils.register_class(VSESelectClipsAfterCurrentFrame)
    bpy.utils.register_class(VSESetClipToCurrentFrame)
    bpy.utils.register_class(VSESetDurationToSelected)  # New tool
    bpy.utils.register_class(VSEMoveSelectedToStart)  # New tool
    bpy.utils.register_class(VSEMoveSelectedToEnd)  # New tool
    bpy.utils.register_class(VSEDumbToolsMenu)

    bpy.types.SEQUENCER_MT_editor_menus.append(sequencer_menu_func)

def unregister():
    bpy.utils.unregister_class(VSEGoToNextClipStart)
    bpy.utils.unregister_class(VSEGoToPreviousClipStart)
    bpy.utils.unregister_class(VSESelectClipsAfterCurrentFrame)
    bpy.utils.unregister_class(VSESetClipToCurrentFrame)
    bpy.utils.unregister_class(VSESetDurationToSelected)  # New tool
    bpy.utils.unregister_class(VSEMoveSelectedToStart)  # New tool
    bpy.utils.unregister_class(VSEMoveSelectedToEnd)  # New tool
    bpy.utils.unregister_class(VSEDumbToolsMenu)
    bpy.types.SEQUENCER_MT_editor_menus.remove(sequencer_menu_func)


register()

