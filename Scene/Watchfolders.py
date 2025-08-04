# Tooltip: Specify a folder, it will import any files that are added to that folder
import bpy
from bpy.types import Panel, PropertyGroup, Operator
from bpy.props import StringProperty, EnumProperty, CollectionProperty, BoolProperty
import threading
import subprocess
import sys
import os
import json
import time

# Function to install packages
def install_package(package):
    subprocess.check_call([sys.executable, "-m", "pip", "install", package])

# Check and install watchdog
try:
    import watchdog
except ImportError:
    install_package("watchdog")
    import watchdog

from watchdog.observers import Observer
from watchdog.events import FileSystemEventHandler

# Function to check if file is fully written
def is_file_ready(filepath, wait_time=1, retries=3):
    for _ in range(retries):
        initial_size = os.path.getsize(filepath)
        time.sleep(wait_time)
        if initial_size == os.path.getsize(filepath):
            return True
    return False

# Event Handler for Watchdog
class WatchHandler(FileSystemEventHandler):
    def __init__(self, folder_type, imported_files):
        self.folder_type = folder_type
        self.imported_files = imported_files
        print(f"Initializing WatchHandler for folder type: {self.folder_type}")
    
    def on_created(self, event):
        print(f"File created: {event.src_path}")
        self.process(event)
    
    def on_modified(self, event):
        print(f"File modified: {event.src_path}")
        self.process(event)

    def process(self, event):
        if not event.is_directory:
            file_path = event.src_path
            file_name = os.path.basename(file_path)
            try:
                if not is_file_ready(file_path):
                    print(f"File {file_path} is still being copied, skipping for now")
                    return

                modified_time = os.path.getmtime(file_path)

                # Check if file has already been imported
                if file_name in self.imported_files and self.imported_files[file_name] >= modified_time:
                    print(f"File {file_name} already imported")
                    return

                print(f"Processing file: {file_path}")
                if self.folder_type == 'IMAGES' and file_path.lower().endswith(('.png', '.jpg', '.jpeg', '.bmp', '.tga')):
                    bpy.ops.image.open(filepath=file_path)
                elif self.folder_type == '3D' and file_path.lower().endswith(('.obj', '.fbx', '.stl')):
                    if file_path.lower().endswith('.obj'):
                        bpy.ops.import_scene.obj(filepath=file_path)
                    elif file_path.lower().endswith('.fbx'):
                        bpy.ops.import_scene.fbx(filepath=file_path)
                    elif file_path.lower().endswith('.stl'):
                        bpy.ops.import_mesh.stl(filepath=file_path)
                elif self.folder_type == 'AUDIO' and file_path.lower().endswith(('.wav', '.mp3', '.ogg')):
                    bpy.ops.sound.open(filepath=file_path)
                elif self.folder_type == 'VIDEO' and file_path.lower().endswith(('.mp4', '.avi', '.mov')):
                    bpy.ops.sequencer.movie_strip_add(filepath=file_path)

                # Record the imported file and its modification date
                self.imported_files[file_name] = modified_time
            except PermissionError as e:
                print(f"PermissionError: {e}")
            except Exception as e:
                print(f"Error processing file {file_path}: {e}")

# Utility functions to serialize and deserialize the dictionary
def serialize_imported_files(imported_files):
    return json.dumps(imported_files)

def deserialize_imported_files(serialized_data):
    if serialized_data:
        return json.loads(serialized_data)
    else:
        return {}

# Property Group to store folder data
class FolderWatcherProperties(PropertyGroup):
    folder_path: StringProperty(name="Folder Path", subtype='DIR_PATH')
    folder_type: EnumProperty(
        name="Type",
        items=[
            ('IMAGES', "Images", ""),
            ('3D', "3D", ""),
            ('AUDIO', "Audio", ""),
            ('VIDEO', "Video", "")
        ]
    )
    watching: BoolProperty(name="Watching", default=False)
    observer = None
    imported_files: StringProperty(name="Imported Files", default="{}")

# Operator to add a new folder watcher
class AddFolderWatcher(Operator):
    bl_idname = "scene.add_watchfolder"
    bl_label = "Add Folder Watcher"

    def execute(self, context):
        new_watcher = context.scene.watchfolders.add()
        new_watcher.folder_path = ""
        new_watcher.folder_type = 'IMAGES'
        new_watcher.watching = False
        new_watcher.imported_files = "{}"
        print("Added new folder watcher")
        return {'FINISHED'}

# Operator to remove a selected folder watcher
class RemoveFolderWatcher(Operator):
    bl_idname = "scene.remove_watchfolder"
    bl_label = "Remove Folder Watcher"

    index: bpy.props.IntProperty()

    def execute(self, context):
        watcher = context.scene.watchfolders[self.index]
        if watcher.watching and watcher.observer:
            watcher.observer.stop()
            watcher.observer.join()
        context.scene.watchfolders.remove(self.index)
        print(f"Removed folder watcher at index: {self.index}")
        return {'FINISHED'}

# Operator to start/stop watching a folder
class ToggleWatchFolder(Operator):
    bl_idname = "scene.toggle_watch_folder"
    bl_label = "Start/Stop Watching"
    index: bpy.props.IntProperty()

    def execute(self, context):
        watcher = context.scene.watchfolders[self.index]
        imported_files = deserialize_imported_files(watcher.imported_files)
        if watcher.watching:
            print(f"Stopping watcher for folder: {watcher.folder_path}")
            if watcher.observer:
                watcher.observer.stop()
                watcher.observer.join()
            watcher.watching = False
        else:
            print(f"Starting watcher for folder: {watcher.folder_path}")
            handler = WatchHandler(watcher.folder_type, imported_files)
            observer = Observer()
            observer.schedule(handler, watcher.folder_path, recursive=False)
            thread = threading.Thread(target=observer.start)
            thread.start()
            watcher.observer = observer
            watcher.watching = True

            # Check for new files and import them if necessary
            for file_name in os.listdir(watcher.folder_path):
                file_path = os.path.join(watcher.folder_path, file_name)
                if os.path.isfile(file_path):
                    event = watchdog.events.FileModifiedEvent(file_path)
                    handler.process(event)

            watcher.imported_files = serialize_imported_files(imported_files)

        return {'FINISHED'}

# Panel to display folder watchers
class FolderWatcherPanel(Panel):
    bl_label = "Watchfolders"
    bl_idname = "VIEW3D_PT_watchfolders"
    bl_space_type = 'VIEW_3D'
    bl_region_type = 'UI'
    bl_category = 'Watchfolders'

    def draw(self, context):
        layout = self.layout
        scene = context.scene

        for index, watcher in enumerate(scene.watchfolders):
            row = layout.row()
            row.prop(watcher, "folder_path", text="")
            row.prop(watcher, "folder_type", text="")
            row.operator("scene.toggle_watch_folder", text="", icon='PLAY' if not watcher.watching else 'PAUSE').index = index
            row.operator("scene.remove_watchfolder", text="", icon='REMOVE').index = index

        layout.operator("scene.add_watchfolder", text="Add Folder")

# Register classes and properties
classes = [
    FolderWatcherProperties,
    AddFolderWatcher,
    RemoveFolderWatcher,
    ToggleWatchFolder,
    FolderWatcherPanel
]

def register():
    for cls in classes:
        bpy.utils.register_class(cls)
    bpy.types.Scene.watchfolders = CollectionProperty(type=FolderWatcherProperties)
    print("Folder watcher addon registered")

def unregister():
    for cls in classes:
        bpy.utils.unregister_class(cls)
    del bpy.types.Scene.watchfolders
    print("Folder watcher addon unregistered")


register()
