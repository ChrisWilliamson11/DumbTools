import bpy

# Blender 5+ VSE helpers and operators
# - Uses SequenceEditor.strips instead of deprecated .sequences
# - Avoids writing to read-only frame_final_* properties
# - Provides safe access to the Sequence Editor and active strip/channel
# - Keeps operators lightweight and undo-friendly


# ---------- Helpers ----------


def ensure_sequencer(context):
    """Ensure the scene has a SequenceEditor and return it."""
    se = context.scene.sequence_editor
    if se is None:
        se = context.scene.sequence_editor_create()
    return se


def vse_strips(context):
    """Return top-level VSE strips from the current scene."""
    return ensure_sequencer(context).strips


def vse_selected_strips(context):
    """Return selected VSE strips from the current scene."""
    return [s for s in vse_strips(context) if getattr(s, "select", False)]


def active_channel(context, default=1):
    """Return the active strip channel if available, else default."""
    se = ensure_sequencer(context)
    strip = getattr(se, "active_strip", None)
    return getattr(strip, "channel", default) if strip else default


# ---------- Operators ----------


class VSEGoToNextClipStart(bpy.types.Operator):
    """Go to the First Frame of the Next Clip"""

    bl_idname = "sequencer.goto_next_clip_start"
    bl_label = "Go to Next Clip Start"
    bl_options = {"REGISTER", "UNDO"}

    def execute(self, context):
        current_frame = context.scene.frame_current
        next_clip_frame = None

        for seq in vse_strips(context):
            if seq.frame_final_start > current_frame:
                if next_clip_frame is None or seq.frame_final_start < next_clip_frame:
                    next_clip_frame = seq.frame_final_start

        if next_clip_frame is not None:
            context.scene.frame_set(next_clip_frame)
            return {"FINISHED"}

        self.report({"INFO"}, "No next clip found")
        return {"CANCELLED"}


class VSEGoToPreviousClipStart(bpy.types.Operator):
    """Go to the First Frame of the Previous Clip"""

    bl_idname = "sequencer.goto_previous_clip_start"
    bl_label = "Go to Previous Clip Start"
    bl_options = {"REGISTER", "UNDO"}

    def execute(self, context):
        current_frame = context.scene.frame_current
        previous_clip_frame = None

        for seq in vse_strips(context):
            if seq.frame_final_start < current_frame:
                if (
                    previous_clip_frame is None
                    or seq.frame_final_start > previous_clip_frame
                ):
                    previous_clip_frame = seq.frame_final_start

        if previous_clip_frame is not None:
            context.scene.frame_set(previous_clip_frame)
            return {"FINISHED"}

        self.report({"INFO"}, "No previous clip found")
        return {"CANCELLED"}


class VSESelectClipsAfterCurrentFrame(bpy.types.Operator):
    """Select All Clips That Start After Current Frame"""

    bl_idname = "sequencer.select_clips_after_current_frame"
    bl_label = "Select Clips After Current Frame"
    bl_options = {"REGISTER", "UNDO"}

    def execute(self, context):
        current_frame = context.scene.frame_current
        strips = list(vse_strips(context))
        if not strips:
            self.report({"INFO"}, "No strips in sequencer")
            return {"CANCELLED"}

        for seq in strips:
            seq.select = bool(seq.frame_final_start > current_frame)

        self.report({"INFO"}, "Clips selection updated")
        return {"FINISHED"}


class VSESetClipToCurrentFrame(bpy.types.Operator):
    """Align selected clips so the earliest selected starts at the current frame"""

    bl_idname = "sequencer.set_clip_to_current_frame"
    bl_label = "Set Clip to Current Frame"
    bl_options = {"REGISTER", "UNDO"}

    def execute(self, context):
        current_frame = context.scene.frame_current
        selected = vse_selected_strips(context)

        if not selected:
            self.report({"WARNING"}, "No clips selected")
            return {"CANCELLED"}

        # Find earliest selected by final start
        first_clip = min(selected, key=lambda s: s.frame_final_start)
        offset = current_frame - first_clip.frame_final_start

        # Move all selected by the same offset (preserve spacing)
        for clip in selected:
            clip.frame_start += offset
            # Optionally ensure at least the active channel (if any)
            clip.channel = max(
                clip.channel, active_channel(context, default=clip.channel)
            )

        return {"FINISHED"}


class VSESetDurationToSelected(bpy.types.Operator):
    """Set Scene Start and End Time based on Selected Clips"""

    bl_idname = "sequencer.set_duration_to_selected"
    bl_label = "Set Duration to Selected"
    bl_options = {"REGISTER", "UNDO"}

    def execute(self, context):
        selected = vse_selected_strips(context)

        if not selected:
            self.report({"WARNING"}, "No clips selected")
            return {"CANCELLED"}

        # Compute range from selection
        frame_start = min(selected, key=lambda s: s.frame_final_start).frame_final_start
        frame_end = max(selected, key=lambda s: s.frame_final_end).frame_final_end

        context.scene.frame_start = frame_start
        context.scene.frame_end = frame_end
        return {"FINISHED"}


class VSEMoveSelectedToStart(bpy.types.Operator):
    """Move Selected Clips so their Start equals Current Frame"""

    bl_idname = "sequencer.move_selected_to_start"
    bl_label = "Move Selected to Start"
    bl_options = {"REGISTER", "UNDO"}

    def execute(self, context):
        current_frame = context.scene.frame_current
        selected = vse_selected_strips(context)

        if not selected:
            self.report({"WARNING"}, "No clips selected")
            return {"CANCELLED"}

        for clip in selected:
            offset = current_frame - clip.frame_final_start
            clip.frame_start += offset

        return {"FINISHED"}


class VSEMoveSelectedToEnd(bpy.types.Operator):
    """Move Selected Clips so their End equals Current Frame"""

    bl_idname = "sequencer.move_selected_to_end"
    bl_label = "Move Selected to End"
    bl_options = {"REGISTER", "UNDO"}

    def execute(self, context):
        current_frame = context.scene.frame_current
        selected = vse_selected_strips(context)

        if not selected:
            self.report({"WARNING"}, "No clips selected")
            return {"CANCELLED"}

        for clip in selected:
            offset = current_frame - clip.frame_final_end
            clip.frame_start += offset

        return {"FINISHED"}


# ---------- UI ----------


class VSEDumbToolsMenu(bpy.types.Menu):
    bl_label = "Dumbtools"
    bl_idname = "SEQUENCER_MT_dumbtools"

    def draw(self, context):
        layout = self.layout
        layout.operator("sequencer.goto_next_clip_start", text="Go to Next Clip Start")
        layout.operator(
            "sequencer.goto_previous_clip_start", text="Go to Previous Clip Start"
        )
        layout.operator(
            "sequencer.select_clips_after_current_frame",
            text="Select Clips After Current Frame",
        )
        layout.operator(
            "sequencer.set_clip_to_current_frame", text="Set Clip to Current Frame"
        )
        layout.operator(
            "sequencer.set_duration_to_selected", text="Set Duration to Selected"
        )
        layout.operator(
            "sequencer.move_selected_to_start", text="Move Selected to Start"
        )
        layout.operator("sequencer.move_selected_to_end", text="Move Selected to End")


def sequencer_menu_func(self, context):
    self.layout.menu("SEQUENCER_MT_dumbtools")


# ---------- Registration ----------

_classes = (
    VSEGoToNextClipStart,
    VSEGoToPreviousClipStart,
    VSESelectClipsAfterCurrentFrame,
    VSESetClipToCurrentFrame,
    VSESetDurationToSelected,
    VSEMoveSelectedToStart,
    VSEMoveSelectedToEnd,
    VSEDumbToolsMenu,
)


def register():
    # Preemptively unregister to avoid re-register spam on reloads
    for cls in _classes:
        try:
            bpy.utils.unregister_class(cls)
        except Exception:
            pass

    for cls in _classes:
        bpy.utils.register_class(cls)

    bpy.types.SEQUENCER_MT_editor_menus.append(sequencer_menu_func)


def unregister():
    for cls in reversed(_classes):
        try:
            bpy.utils.unregister_class(cls)
        except Exception:
            pass
    try:
        bpy.types.SEQUENCER_MT_editor_menus.remove(sequencer_menu_func)
    except Exception:
        pass


# Auto-register
register()
