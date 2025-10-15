# Tooltip: Batch render animation from multiple blend files using command-line rendering

import bpy
import os
import sys
import subprocess
from bpy.props import CollectionProperty, StringProperty
from bpy.types import Operator
from bpy_extras.io_utils import ImportHelper


class RENDER_OT_batch_animation(Operator, ImportHelper):
    """Batch render animation from multiple blend files using command-line rendering"""
    bl_idname = "render.batch_animation"
    bl_label = "Batch Render Animation"
    bl_description = "Select multiple blend files to render animation for each using command-line rendering"
    bl_options = {'REGISTER', 'UNDO'}

    # File browser properties
    filename_ext = ".blend"
    filter_glob: StringProperty(
        default="*.blend",
        options={'HIDDEN'},
        maxlen=255,
    )

    # Allow multiple file selection
    files: CollectionProperty(
        name="File Path",
        type=bpy.types.OperatorFileListElement,
    )

    directory: StringProperty(
        subtype='DIR_PATH',
    )

    def execute(self, context):
        """Execute the batch render operation using command-line Blender"""
        if not self.files:
            self.report({'WARNING'}, "No files selected")
            return {'CANCELLED'}

        # Get the Blender executable path
        blender_exe = bpy.app.binary_path

        total_files = len(self.files)
        print(f"\n=== Starting batch render for {total_files} file(s) ===\n")

        success_count = 0
        failed_count = 0

        # Process each selected blend file
        for idx, file_elem in enumerate(self.files, 1):
            filepath = os.path.join(self.directory, file_elem.name)

            if not os.path.exists(filepath):
                self.report({'WARNING'}, f"File not found: {filepath}")
                print(f"[{idx}/{total_files}] ✗ File not found: {filepath}")
                failed_count += 1
                continue

            if not filepath.lower().endswith('.blend'):
                self.report({'WARNING'}, f"Not a blend file: {filepath}")
                print(f"[{idx}/{total_files}] ✗ Not a blend file: {filepath}")
                failed_count += 1
                continue

            try:
                print(f"[{idx}/{total_files}] Processing: {file_elem.name}")

                # Build command-line arguments for Blender
                cmd = [
                    blender_exe,
                    "--background",  # Run in background mode (no UI)
                    filepath,        # The blend file to render
                    "--render-anim"  # Render animation
                ]

                print(f"  → Starting render...")

                # Run Blender in background mode to render
                result = subprocess.run(
                    cmd,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.PIPE,
                    text=True
                )

                if result.returncode == 0:
                    print(f"  ✓ Render complete")
                    success_count += 1
                else:
                    error_msg = f"Render failed with return code {result.returncode}"
                    print(f"  ✗ {error_msg}")
                    if result.stderr:
                        print(f"  Error output: {result.stderr}")
                    self.report({'WARNING'}, f"{file_elem.name}: {error_msg}")
                    failed_count += 1

            except Exception as e:
                error_msg = f"Failed to process {filepath}: {str(e)}"
                self.report({'ERROR'}, error_msg)
                print(f"[{idx}/{total_files}] ✗ {error_msg}")
                failed_count += 1

        print(f"\n=== Batch render complete ===")
        print(f"Success: {success_count}, Failed: {failed_count}")
        self.report({'INFO'}, f"Rendered {success_count}/{total_files} file(s) successfully")
        return {'FINISHED'}

    def invoke(self, context, event):
        """Invoke the file browser"""
        context.window_manager.fileselect_add(self)
        return {'RUNNING_MODAL'}


def register():
    """Register the operator"""
    try:
        bpy.utils.register_class(RENDER_OT_batch_animation)
    except ValueError:
        # Class already registered
        pass


def unregister():
    """Unregister the operator"""
    try:
        bpy.utils.unregister_class(RENDER_OT_batch_animation)
    except (ValueError, RuntimeError):
        # Class not registered or already removed
        pass


# Unregister first in case it's already registered
unregister()
# Then register
register()
# Run the operator
bpy.ops.render.batch_animation('INVOKE_DEFAULT')

