import bpy
import os
import subprocess
import struct

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




def read_exr_metadata(filepath):
    """
    Minimal EXR header parser to extract metadata.
    Returns a dict of key/value pairs found in the header.
    """
    if not os.path.exists(filepath):
        return {}

    metadata = {}
    try:
        with open(filepath, "rb") as f:
            # Check Magic: 0x76, 0x2f, 0x31, 0x01
            magic = f.read(4)
            if magic != b"\x76\x2f\x31\x01":
                return {}

            f.read(4)  # Version and flags, skip

            # Parse attributes
            while True:
                # Read Name
                name_bytes = bytearray()
                while True:
                    b = f.read(1)
                    if not b or b == b"\x00":
                        break
                    name_bytes.extend(b)

                if not name_bytes:
                    break  # End of header

                attr_name = name_bytes.decode("utf-8", errors="ignore")

                # Read Type
                type_bytes = bytearray()
                while True:
                    b = f.read(1)
                    if not b or b == b"\x00":
                        break
                    type_bytes.extend(b)
                attr_type = type_bytes.decode("utf-8", errors="ignore")

                # Read Size
                size_data = f.read(4)
                if len(size_data) < 4:
                    break
                attr_size = struct.unpack("<I", size_data)[0]

                # Read Value
                attr_value_raw = f.read(attr_size)

                # Store value if it's likely a string, or just store raw bytes if wanted.
                # For our purpose (finding blend file path), strictly looking for string attributes is safest,
                # but sometimes "string" type isn't explicitly used if it's a known attribute?
                # Actually, OpenEXR attributes generally use "string" type for text.
                if attr_type == "string":
                    try:
                        # OpenEXR strings might be null terminated or just raw bytes.
                        # Usually raw bytes of length 'attr_size'.
                        val = attr_value_raw.decode("utf-8", errors="ignore")
                        metadata[attr_name] = val
                    except:
                        pass
                else:
                    # Keep raw bytes just in case we need to debug other types,
                    # but for now we only care about strings.
                    pass

    except Exception as e:
        print(f"VSE Tools: Error parsing EXR header: {e}")

    return metadata


class VSEOpenSourceBlend(bpy.types.Operator):
    """Open the source .blend file from strip metadata"""

    bl_idname = "sequencer.open_source_blend"
    bl_label = "Open Source Blend"
    bl_options = {"REGISTER", "UNDO"}

    def execute(self, context):
        strip = context.scene.sequence_editor.active_strip
        if not strip:
            self.report({"WARNING"}, "No active strip")
            return {"CANCELLED"}

        filepath = None
        if strip.type == "IMAGE":
            # Ensure directory is absolute
            directory = bpy.path.abspath(strip.directory)
            # Find first existing file in sequence (handle missing frames/phantom handles)
            if strip.elements:
                for elem in strip.elements:
                    candidate = os.path.join(directory, elem.filename)
                    if os.path.exists(candidate):
                        filepath = candidate
                        break
                # Fallback to first element if none exist, for error reporting
                if not filepath:
                    filepath = os.path.join(directory, strip.elements[0].filename)

        elif strip.type == "MOVIE":
            filepath = bpy.path.abspath(strip.filepath)

        if not filepath or not os.path.exists(filepath):
            self.report({"WARNING"}, f"Could not find file: {filepath}")
            return {"CANCELLED"}
        
        # Only try parsing if it looks like an EXR
        if not filepath.lower().endswith(".exr"):
             self.report({"WARNING"}, "Metadata parsing currently only supports EXR files.")
             return {"CANCELLED"}

        # Read metadata directly from file
        metadata = read_exr_metadata(filepath)
        
        # Look for metadata
        blend_path = None
        keys_to_check = ["File", "Blender", "blender", "filename"]
        for key in keys_to_check:
            if key in metadata:
                blend_path = metadata[key]
                break
        
        if not blend_path:
            # Fallback: Check if any value looks like a blend file path
            for val in metadata.values():
                if isinstance(val, str) and val.endswith(".blend"):
                    blend_path = val
                    break

        if not blend_path:
            self.report({"WARNING"}, f"No .blend file usage found in metadata (checked {keys_to_check})")
            return {"CANCELLED"}

        # Resolve path
        final_path = bpy.path.abspath(blend_path)
        if not os.path.exists(final_path):
            # Try resolving relative to the image file
            if blend_path.startswith("//"):
                alt_path = os.path.normpath(
                    os.path.join(os.path.dirname(filepath), blend_path[2:])
                )
                if os.path.exists(alt_path):
                    final_path = alt_path

        if not os.path.exists(final_path):
            self.report({"ERROR"}, f"Blend file not found: {final_path}")
            return {"CANCELLED"}

        # Open Blender
        self.report({"INFO"}, f"Opening {os.path.basename(final_path)}")
        subprocess.Popen([bpy.app.binary_path, final_path])

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
        layout.separator()
        layout.operator("sequencer.open_source_blend", text="Open Source Blend")


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
    VSEOpenSourceBlend,
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
