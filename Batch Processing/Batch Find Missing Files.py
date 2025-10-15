# Tooltip: This script will batch find missing files in a directory and its subdirectories.

import bpy
import os
from datetime import datetime
from bpy.props import StringProperty, IntProperty
from bpy.types import Operator, Panel

class BatchFindMissingFilesOperator(Operator):
    """Process multiple blend files to find missing files"""
    bl_idname = "file.batch_find_missing"
    bl_label = "Batch Find Missing Files"
    bl_options = {'REGISTER'}

    def _log(self, log_path: str, message: str):
        print(message)
        try:
            with open(log_path, 'a', encoding='utf-8') as f:
                f.write(message + "\n")
        except Exception:
            pass

    def process_directory(self, directory, search_dir, current_depth, max_depth, log_path):
        """Recursively process blend files in directory and its subdirectories"""
        for entry in os.scandir(directory):
            if entry.is_file() and entry.name.endswith(".blend"):
                blend_path = entry.path
                self._log(log_path, f"[PROCESS] {blend_path}")
                # Open the blend file with error handling
                try:
                    res = bpy.ops.wm.open_mainfile(filepath=blend_path)
                    if isinstance(res, set) and 'FINISHED' not in res:
                        self._log(log_path, f"[ERROR] Open failed: {blend_path}; result={res}")
                        continue
                except Exception as e:
                    self._log(log_path, f"[ERROR] Failed to read blend file '{blend_path}': {e}")
                    continue
                # Find missing files
                try:
                    bpy.ops.file.find_missing_files(directory=search_dir)
                except Exception as e:
                    self._log(log_path, f"[WARN] find_missing_files failed for '{blend_path}': {e}")
                # Save the file
                try:
                    bpy.ops.wm.save_mainfile()
                    self._log(log_path, f"[SAVED] {blend_path}")
                except Exception as e:
                    self._log(log_path, f"[ERROR] Failed to save '{blend_path}': {e}")
            # Recurse into subdirectories if we haven't reached max depth
            elif entry.is_dir() and (max_depth == -1 or current_depth < max_depth):
                self.process_directory(entry.path, search_dir, current_depth + 1, max_depth, log_path)

    def execute(self, context):
        source_dir = context.scene.source_directory
        search_dir = context.scene.search_directory
        max_depth = context.scene.recursion_depth
        log_dir = getattr(context.scene, "log_directory", "") or source_dir

        if not source_dir or not search_dir:
            self.report({'ERROR'}, "Please select both directories")
            return {'CANCELLED'}

        # Prepare log
        try:
            os.makedirs(log_dir, exist_ok=True)
        except Exception:
            pass
        ts = datetime.now().strftime('%Y%m%d_%H%M%S')
        log_path = os.path.join(log_dir, f"BatchFindMissingFiles_{ts}.log")
        try:
            with open(log_path, 'a', encoding='utf-8') as f:
                f.write(f"# Batch Find Missing Files - {datetime.now().isoformat()}\n")
                f.write(f"# Source={source_dir}\n# Search={search_dir}\n# Depth={max_depth}\n")
        except Exception:
            pass

        # Process the source directory
        self.process_directory(source_dir, search_dir, 0, max_depth, log_path)

        self._log(log_path, "[DONE] Finished processing all blend files")
        self.report({'INFO'}, "Finished processing all blend files")
        return {'FINISHED'}

    def invoke(self, context, event):
        return context.window_manager.invoke_props_dialog(self, width=400)

    def draw(self, context):
        layout = self.layout
        scene = context.scene

        # Source directory selection
        box = layout.box()
        box.label(text="Blend Files Directory:", icon='FILE_BLEND')
        row = box.row(align=True)
        row.prop(scene, "source_directory", text="")

        # Search directory selection
        box = layout.box()
        box.label(text="Search Directory for Missing Files:", icon='VIEWZOOM')
        row = box.row(align=True)
        row.prop(scene, "search_directory", text="")

        # Recursion depth
        box = layout.box()
        box.label(text="Recursion Settings:", icon='NEWFOLDER')
        row = box.row(align=True)
        row.prop(scene, "recursion_depth")
        # Log directory
        box = layout.box()
        box.label(text="Logging:", icon='TEXT')
        row = box.row(align=True)
        row.prop(scene, "log_directory", text="Log Directory")


class SelectSourceDirectoryOperator(Operator):
    """Select the directory containing blend files"""
    bl_idname = "file.select_source_directory"
    bl_label = "Select Blend Files Directory"

    directory: StringProperty(subtype='DIR_PATH')

    def execute(self, context):
        context.scene.source_directory = self.directory
        return {'FINISHED'}

    def invoke(self, context, event):
        context.window_manager.fileselect_add(self)
        return {'RUNNING_MODAL'}

class SelectSearchDirectoryOperator(Operator):
    """Select the directory to search for missing files"""
    bl_idname = "file.select_search_directory"
    bl_label = "Select Search Directory"

    directory: StringProperty(subtype='DIR_PATH')

    def execute(self, context):
        context.scene.search_directory = self.directory
        return {'FINISHED'}

    def invoke(self, context, event):
        context.window_manager.fileselect_add(self)
        return {'RUNNING_MODAL'}

def register():
    bpy.types.Scene.source_directory = StringProperty(
        name="Source Directory",
        description="Directory containing blend files to process",
        subtype='DIR_PATH'
    )
    bpy.types.Scene.search_directory = StringProperty(
        name="Search Directory",
        description="Directory to search for missing files",
        subtype='DIR_PATH'
    )
    bpy.types.Scene.recursion_depth = IntProperty(
        name="Recursion Depth",
        description=(
            "How deep to recurse into subdirectories (-1 for unlimited, 0 for no recursion)"
        ),
        default=0,
        min=-1
    )
    bpy.types.Scene.log_directory = StringProperty(
        name="Log Directory",
        description="Directory to save the batch log (defaults to Source Directory)",
        subtype='DIR_PATH'
    )
    bpy.utils.register_class(BatchFindMissingFilesOperator)
    bpy.utils.register_class(SelectSourceDirectoryOperator)
    bpy.utils.register_class(SelectSearchDirectoryOperator)

def unregister():
    del bpy.types.Scene.source_directory
    del bpy.types.Scene.search_directory
    del bpy.types.Scene.recursion_depth
    del bpy.types.Scene.log_directory
    bpy.utils.unregister_class(BatchFindMissingFilesOperator)
    bpy.utils.unregister_class(SelectSourceDirectoryOperator)
    bpy.utils.unregister_class(SelectSearchDirectoryOperator)

register()
bpy.ops.file.batch_find_missing('INVOKE_DEFAULT')
