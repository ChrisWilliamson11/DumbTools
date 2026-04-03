# Tooltip: Analyse the current scene's render output folder and report the last rendered frame based on modification time.
import os
import re
from datetime import datetime

import bpy
from bpy.props import BoolProperty, IntProperty
from bpy.types import Operator


def _abspath(path: str) -> str:
    try:
        return bpy.path.abspath(path)
    except Exception:
        return os.path.abspath(path)


def _file_extension_for_format(scene) -> str:
    # Map Blender's file formats to typical file extensions
    fmt = scene.render.image_settings.file_format
    if fmt == "FFMPEG":
        # Movie container - try to infer from ffmpeg container
        try:
            container = (
                scene.render.ffmpeg.format
            )  # e.g., 'MPEG4', 'MKV', 'QUICKTIME', 'AVI'
        except Exception:
            container = "MPEG4"
        mapping = {
            "MPEG4": ".mp4",
            "MKV": ".mkv",
            "QUICKTIME": ".mov",
            "AVI": ".avi",
            "WEBM": ".webm",
            "OGG": ".ogv",
            "FLASH": ".flv",
            "H264": ".mp4",  # legacy
        }
        return mapping.get(container, ".mp4")
    mapping = {
        "BMP": ".bmp",
        "IRIS": ".rgb",
        "PNG": ".png",
        "JPEG": ".jpg",
        "JPEG2000": ".jp2",
        "TARGA": ".tga",
        "TARGA_RAW": ".tga",
        "CINEON": ".cin",
        "DPX": ".dpx",
        "OPEN_EXR": ".exr",
        "OPEN_EXR_MULTILAYER": ".exr",
        "HDR": ".hdr",
        "TIFF": ".tif",
        "WEBP": ".webp",
    }
    return mapping.get(fmt, "")


def _split_dir_and_base(render_path: str, fallback_name: str):
    # Returns directory and base pattern (without extension)
    dirpath, base = os.path.split(render_path)
    if not dirpath:
        # When only a file name is provided, use the blend file's directory
        blend_dir = (
            os.path.dirname(bpy.data.filepath) if bpy.data.filepath else os.getcwd()
        )
        dirpath = blend_dir

    # If base is empty (render path ends with a slash), use scene name
    if base in (None, "", os.sep, "/"):
        base = fallback_name

    # If base has extension, strip it to get the prefix
    base_no_ext, _ = os.path.splitext(base)
    return dirpath, base_no_ext


def _friendly_output_name(base_prefix: str) -> str:
    # Strip common trailing separators for display
    return base_prefix.rstrip("_- ").strip() or base_prefix


def _collect_candidate_files(
    dirpath: str, base_prefix: str, ext_hint: str, use_file_extension: bool
):
    """
    Collect files in dirpath that look like they belong to the current render output.
    We accept:
      - Files starting with base_prefix and followed by optional separators and a frame number.
      - If use_file_extension is True and ext_hint is set, prefer files with that extension but
        still allow files without extension match to be safe in mixed folders.
    """
    try:
        entries = os.listdir(dirpath)
    except FileNotFoundError:
        return []

    candidates = []
    for f in entries:
        # Quick prefix check
        if not f.startswith(base_prefix):
            continue

        full = os.path.join(dirpath, f)
        if not os.path.isfile(full):
            continue

        root, ext = os.path.splitext(f)
        # If Blender is set to add file extensions, try to match extension, else allow everything
        if (
            use_file_extension
            and ext_hint
            and ext
            and (ext.lower() != ext_hint.lower())
        ):
            # Allow mismatched extension, but keep capturing (users may have toggled formats)
            pass

        # Extract the numeric part that represents the frame number from the remainder
        remainder = root[len(base_prefix) :]  # cut off base prefix (without extension)
        # Common case: "Myoutput_0001" or "Myoutput0001"
        # Find first group of digits in remainder
        m = re.search(r"(\d+)", remainder)
        if not m:
            continue

        try:
            frame = int(m.group(1))
        except Exception:
            continue

        try:
            mtime = os.path.getmtime(full)
        except Exception:
            continue

        candidates.append(
            {
                "file": f,
                "full": full,
                "frame": frame,
                "mtime": mtime,
                "ext": ext,
            }
        )

    return candidates


def _select_latest_run_frame(candidates, time_window_seconds: int):
    """
    Given a list of {frame, mtime}, find the frame that likely represents the latest render attempt.
    Strategy:
      - Find the max mtime across all candidates.
      - Select all frames whose mtime is within [max_mtime - window, max_mtime] and pick the max frame among them.
      - Fallback: if no frames in window, return the frame with max mtime.
    """
    if not candidates:
        return None, None

    max_mtime = max(c["mtime"] for c in candidates)
    threshold = max_mtime - time_window_seconds

    latest_batch = [c for c in candidates if c["mtime"] >= threshold]
    if latest_batch:
        best = max(latest_batch, key=lambda c: c["frame"])
    else:
        best = max(candidates, key=lambda c: c["mtime"])

    return best["frame"], max_mtime


def _format_time(ts: float) -> str:
    try:
        return datetime.fromtimestamp(ts).strftime("%Y-%m-%d %H:%M:%S")
    except Exception:
        return str(ts)


def _show_popup(lines, title="Analyse Output", icon="INFO"):
    """
    Show a simple popup with the provided lines.
    """

    def draw(self, context):
        for line in lines:
            self.layout.label(text=line)

    try:
        bpy.context.window_manager.popup_menu(draw, title=title, icon=icon)
    except Exception:
        # In background mode or if UI not available, silently ignore
        pass


class DUMBTOOLS_OT_analyse_output(Operator):
    """Analyse the current scene's render output and report the last rendered frame based on file modification times"""

    bl_idname = "render.analyse_output"
    bl_label = "Analyse Output (DumbTools)"
    bl_options = {"REGISTER", "UNDO"}

    time_window_seconds: IntProperty(
        name="Time Window (s)",
        description="Frames modified within this window from the newest file are considered part of the latest render attempt",
        default=600,
        min=0,
        max=86400,
    )

    show_file_details: BoolProperty(
        name="List Matched Files in Console",
        description="Print matched files with frame numbers and times to the console for debugging",
        default=False,
    )

    def execute(self, context):
        scene = context.scene
        frame_start = int(scene.frame_start)
        frame_end = int(scene.frame_end)
        render_path = _abspath(scene.render.filepath)

        dirpath, base_prefix = _split_dir_and_base(render_path, scene.name)
        friendly = _friendly_output_name(base_prefix)

        ext_hint = _file_extension_for_format(scene)
        use_ext = bool(getattr(scene.render, "use_file_extension", True))

        # Special handling for movie output (FFMPEG): can't infer partial progress reliably
        if scene.render.image_settings.file_format == "FFMPEG":
            movie_file_path = (
                os.path.join(dirpath, base_prefix + ext_hint)
                if ext_hint
                else os.path.join(dirpath, base_prefix)
            )
            exists = os.path.exists(movie_file_path)
            msg_lines = [
                f"Output: {friendly}",
                f"Frames: {frame_start}-{frame_end}",
                "Detected movie output (FFMPEG).",
                f"File: {movie_file_path}",
                f"Exists: {'Yes' if exists else 'No'}",
                "Last rendered frame: Not inferable for movie outputs (single container file).",
            ]

            summary = " | ".join(msg_lines[:3])
            print("\n".join(msg_lines))
            self.report({"INFO"}, summary)
            _show_popup(msg_lines[:3], title="Analyse Output")
            return {"FINISHED"}

        candidates = _collect_candidate_files(dirpath, base_prefix, ext_hint, use_ext)

        if self.show_file_details and candidates:
            print("Matched files:")
            for c in sorted(candidates, key=lambda d: (d["frame"], d["mtime"])):
                print(
                    f"  {c['file']}  -> frame {c['frame']}  mtime: {_format_time(c['mtime'])}"
                )

        last_frame, last_mtime = _select_latest_run_frame(
            candidates, self.time_window_seconds
        )

        if last_frame is None:
            msg_lines = [
                f"Output: {friendly}",
                f"Frames: {frame_start}-{frame_end}",
                "No frames found in the output directory.",
            ]
            summary = " | ".join(msg_lines)
            print("\n".join(msg_lines))
            self.report({"INFO"}, summary)
            _show_popup(msg_lines, title="Analyse Output")
            return {"FINISHED"}

        # Bound the last frame to the configured scene range if applicable
        bounded_last = max(frame_start, min(last_frame, frame_end))
        next_frame = min(bounded_last + 1, frame_end)

        msg_lines = [
            f"Output: {friendly}",
            f"Frames: {frame_start}-{frame_end}",
            f"Last rendered frame: {bounded_last}",
            f"Last modified: {_format_time(last_mtime)}",
            f"Next frame to render: {next_frame if next_frame > bounded_last else 'Completed'}",
            f"Folder: {dirpath}",
            f"Base prefix: {base_prefix}",
        ]
        # Concise report (first three lines)
        concise = "\n".join(msg_lines[:3])
        print("\n".join(msg_lines))
        self.report({"INFO"}, concise)
        _show_popup(msg_lines[:3], title="Analyse Output")
        return {"FINISHED"}

    def invoke(self, context, event):
        # Run immediately and show a small dialog with only the adjustable window, if desired.
        return self.execute(context)


def register():
    bpy.utils.register_class(DUMBTOOLS_OT_analyse_output)


def unregister():
    bpy.utils.unregister_class(DUMBTOOLS_OT_analyse_output)


# Register and invoke immediately when run from the Text Editor
register()
bpy.ops.render.analyse_output("INVOKE_DEFAULT")
