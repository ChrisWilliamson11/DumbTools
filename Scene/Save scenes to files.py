# Tooltip: Save each scene in the current blend as its own .blend containing only that scene
import bpy
import os
import re
import subprocess
from bpy.types import Operator
from bpy.props import StringProperty, BoolProperty


def sanitize_filename(name: str) -> str:
    # Replace characters invalid on most filesystems
    name = re.sub(r'[<>:"/\\|?*\n\r\t]', '_', name)
    name = name.strip().rstrip('.')
    return name or "Scene"


def unique_path(path: str) -> str:
    if not os.path.exists(path):
        return path
    base, ext = os.path.splitext(path)
    i = 1
    while True:
        candidate = f"{base}_{i:03d}{ext}"
        if not os.path.exists(candidate):
            return candidate
        i += 1


def get_blender_path() -> str:
    return bpy.app.binary_path


def strip_copy_to_single_scene(copy_path: str, scene_name: str) -> bool:
    """Open the saved copy headless, remove all scenes except `scene_name`, purge orphans, save."""
    blender_exe = get_blender_path()
    if not blender_exe or not os.path.exists(blender_exe):
        return False

    # Prepare a python expression to run in background Blender
    # Use repr to safely embed the scene name
    keep_expr = repr(scene_name)
    py_expr = (
        "import bpy;"
        f"keep={keep_expr};"
        "scs=list(bpy.data.scenes);"
        "[bpy.data.scenes.remove(sc) for sc in scs if sc.name!=keep];"
        "bpy.ops.wm.save_mainfile()"
    )

    try:
        # Run Blender in background to modify the copy
        result = subprocess.run(
            [blender_exe, "-b", copy_path, "--python-expr", py_expr],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            check=False,
        )
        return result.returncode == 0
    except Exception:
        return False


class SCENE_OT_save_scenes_to_files(Operator):
    bl_idname = "scene.save_scenes_to_files"
    bl_label = "Save Scenes to Files"
    bl_description = "For each scene in this .blend, save a .blend that contains only that scene"
    bl_options = {'REGISTER'}

    directory: StringProperty(
        name="Output Directory",
        description="Folder to write the per‑scene .blend files",
        subtype='DIR_PATH',
        default="",
    )

    overwrite: BoolProperty(
        name="Overwrite Existing",
        description="If a file exists, overwrite it instead of adding a numbered suffix",
        default=False,
    )

    def invoke(self, context, event):
        # Default to the current file's folder if available
        if not self.directory and bpy.data.filepath:
            self.directory = os.path.dirname(bpy.data.filepath)
        context.window_manager.fileselect_add(self)
        return {'RUNNING_MODAL'}

    def execute(self, context):
        if not self.directory:
            self.report({'ERROR'}, "Please choose an output directory")
            return {'CANCELLED'}

        try:
            os.makedirs(self.directory, exist_ok=True)
        except Exception:
            self.report({'ERROR'}, f"Could not create/access directory: {self.directory}")
            return {'CANCELLED'}

        scenes = list(bpy.data.scenes)
        if not scenes:
            self.report({'WARNING'}, "No scenes found in this file")
            return {'CANCELLED'}

        blender_exe = get_blender_path()
        if not blender_exe or not os.path.exists(blender_exe):
            self.report({'ERROR'}, "Blender executable path not found")
            return {'CANCELLED'}

        success_count = 0
        # Save a per‑scene copy and strip it down in a background process
        for sc in scenes:
            scene_name = sc.name
            safe_name = sanitize_filename(scene_name)
            out_path = os.path.join(self.directory, f"SH_{safe_name}.blend")
            if not self.overwrite:
                out_path = unique_path(out_path)

            # Save copy of the current file to the target path (does not change current file path)
            try:
                bpy.ops.wm.save_as_mainfile(filepath=out_path, copy=True)
            except Exception:
                # print(f"Failed to save copy for scene: {scene_name}")
                continue

            # Strip the copy down to just this scene
            ok = strip_copy_to_single_scene(out_path, scene_name)
            if ok:
                success_count += 1
            else:
                # print(f"Failed to strip file for scene: {scene_name}")
                pass

        msg = f"Saved {success_count}/{len(scenes)} scene files to: {self.directory}"
        self.report({'INFO'}, msg)
        return {'FINISHED'}


def register():
    try:
        bpy.utils.register_class(SCENE_OT_save_scenes_to_files)
    except Exception:
        # Already registered
        pass


def unregister():
    try:
        bpy.utils.unregister_class(SCENE_OT_save_scenes_to_files)
    except Exception:
        pass


register()
# Try to show the directory picker; if no UI, just stay registered
try:
    if bpy.context.window_manager:
        bpy.ops.scene.save_scenes_to_files('INVOKE_DEFAULT')
except Exception:
    # print("Could not invoke operator UI. You can run it via F3: 'Save Scenes to Files'.")
    pass
