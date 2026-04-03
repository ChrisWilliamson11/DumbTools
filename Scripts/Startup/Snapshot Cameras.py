import bpy
import os
import json

def is_serializable(v):
    return isinstance(v, (str, int, float, bool, list, dict, tuple))

active_snapshot_name = ""

def update_presets_collection(scene):
    # Load presets from the JSON file
    json_presets = load_presets()

    # Clear the existing collection
    scene.my_presets.clear()

    # Populate the collection with presets from the JSON file
    for preset_name in json_presets.keys():
        preset_item = scene.my_presets.add()
        preset_item.name = preset_name
        # Set the default state of 'enabled' here if needed

class SetActiveCameraOperator(bpy.types.Operator):
    """Set the selected camera as the active camera for the scene."""
    bl_idname = "scene.set_active_camera"
    bl_label = "Set Active Camera"
    bl_options = {'REGISTER', 'UNDO'}

    camera_name: bpy.props.StringProperty()

    def execute(self, context):
        # Find the camera object using the camera_name property
        camera = bpy.data.objects.get(self.camera_name)

        # If the camera is found and it is of type 'CAMERA', set it as active
        if camera and camera.type == 'CAMERA':
            context.scene.camera = camera
            self.report({'INFO'}, f"Active camera set to: {camera.name}")
            return {'FINISHED'}
        else:
            self.report({'ERROR'}, f"Camera '{self.camera_name}' not found or is not a camera")
            return {'CANCELLED'}

def get_active_camera_snapshot_name(context):
    active_camera = context.active_object
    if active_camera and active_camera.type == 'CAMERA':
        for snapshot in context.scene.transform_snapshots:
            if snapshot.object_name == active_camera.name:
                return snapshot.name
    return ""

def update_display_json_list(self, context):
    if self.display_json_list:
        update_presets_collection(context.scene)



def find_associated_camera(snapshot):
    if snapshot.object_name in bpy.data.objects:
        return bpy.data.objects[snapshot.object_name]
    return None

def select_associated_camera(context, snapshot):
    camera = find_associated_camera(snapshot)
    if camera:
        for obj in bpy.context.view_layer.objects:
            obj.select_set(False)
        camera.select_set(True)
        context.view_layer.objects.active = camera

def get_appdata_folder():
    return bpy.utils.user_resource('CONFIG')

def load_presets():
    file_path = os.path.join(get_appdata_folder(), "overlay_presets.json")
    try:
        with open(file_path, 'r') as file:
            return json.load(file)
    except FileNotFoundError:
        return {}

def save_space_data_settings(context):
    space = context.space_data
    settings = {attr: getattr(space, attr) for attr in dir(space)
                if not attr.startswith("__") and not callable(getattr(space, attr))
                and is_serializable(getattr(space, attr))}

    # Special handling for nested property groups like 'shading'
    shading_settings = {attr: getattr(space.shading, attr) for attr in dir(space.shading)
                        if not attr.startswith("__") and not callable(getattr(space.shading, attr))
                        and is_serializable(getattr(space.shading, attr))}

    if shading_settings:
        settings['shading'] = shading_settings

    return settings

def load_space_data_settings(context, settings):
    space = context.space_data
    for attr, value in settings.items():
        if attr == 'shading':
            for shading_attr, shading_value in value.items():
                setattr(space.shading, shading_attr, shading_value)
        elif hasattr(space, attr) and not callable(getattr(space, attr)):
            setattr(space, attr, value)

def save_viewport_settings(context, save_space=True, save_shading=True, save_overlay=True):
    space = context.space_data
    settings = {}
    if space.type == 'VIEW_3D':
        if save_overlay:
            overlay = space.overlay
            settings['overlay'] = {attr: getattr(overlay, attr) for attr in dir(overlay)
                                   if not attr.startswith("__") and not callable(getattr(overlay, attr))
                                   and is_serializable(getattr(overlay, attr))}
        if save_space:
            settings['space'] = {attr: getattr(space, attr) for attr in dir(space)
                                 if not attr.startswith("__") and not callable(getattr(space, attr))
                                 and is_serializable(getattr(space, attr))}
        if save_shading:
            shading = space.shading
            settings['shading'] = {attr: getattr(shading, attr) for attr in dir(shading)
                                   if not attr.startswith("__") and not callable(getattr(shading, attr))
                                   and is_serializable(getattr(shading, attr))}
    return settings

def load_viewport_settings(context, settings):
    space = context.space_data
    if space.type == 'VIEW_3D':
        # Apply overlay settings
        if 'overlay' in settings:
            overlay = space.overlay
            for attr, value in settings['overlay'].items():
                if hasattr(overlay, attr) and not callable(getattr(overlay, attr)):
                    try:
                        setattr(overlay, attr, value)
                    except AttributeError as e:
                        print(f"Could not set overlay attribute {attr}: {e}")

        # Apply space settings
        if 'space' in settings:
            for attr, value in settings['space'].items():
                if hasattr(space, attr) and not callable(getattr(space, attr)):
                    try:
                        setattr(space, attr, value)
                    except AttributeError as e:
                        print(f"Could not set space attribute {attr}: {e}")

        # Apply shading settings
        if 'shading' in settings:
            shading = space.shading
            for attr, value in settings['shading'].items():
                if hasattr(shading, attr) and not callable(getattr(shading, attr)):
                    try:
                        # Check if the attribute is an enum and the value is a valid option
                        prop = getattr(shading, attr)
                        if isinstance(prop, bpy.types.EnumProperty) and value not in prop[1]['items']:
                            print(f"Invalid enum value for {attr}: {value}")
                        else:
                            setattr(shading, attr, value)
                    except AttributeError as e:
                        print(f"Could not set shading attribute {attr}: {e}")
                    except TypeError as e:
                        print(f"Invalid type for shading attribute {attr}: {e}")

class PresetItem(bpy.types.PropertyGroup):
    enabled: bpy.props.BoolProperty(name="Enabled", default=False)

bpy.utils.register_class(PresetItem)
bpy.types.Scene.my_presets = bpy.props.CollectionProperty(type=PresetItem)

class RenderSnapshotsProperties(bpy.types.PropertyGroup):
    display_json_list: bpy.props.BoolProperty(
        name="Display JSON List",
        default=False,
        update=update_display_json_list
    )

    # You can add other properties here if needed

class RenderSnapshotsOperator(bpy.types.Operator):
    bl_idname = "scene.render_snapshots"
    bl_label = "Render Snapshots"
    bl_description = "Render snapshots one after another in the current Blender instance"
    bl_options = {'REGISTER'}

    directory: bpy.props.StringProperty(
        name="Output Directory",
        subtype='DIR_PATH'
    )

    file_format: bpy.props.EnumProperty(
        name="File Format",
        items=(
            ('PNG', "PNG", "Output in PNG format"),
            ('JPEG', "JPEG", "Output in JPEG format"),
            ('TIFF', "TIFF", "Output in TIFF format"),
            ('OPEN_EXR', "EXR", "Output in OpenEXR format"),
        ),
        default='OPEN_EXR'
    )

    display_json_list: bpy.props.BoolProperty(
        name="Display JSON List",
        default=False,
        update=update_display_json_list
    )

    json_file_path: bpy.props.StringProperty(
        name="JSON File",
        subtype='FILE_PATH',
        default="",
    )

    def execute(self, context):
        scene = context.scene

        if not self.directory:
            self.report({'ERROR'}, "No output directory provided.")
            return {'CANCELLED'}

        # Ensure the output directory exists
        if not os.path.exists(self.directory):
            os.makedirs(self.directory)

        original_camera = scene.camera
        original_filepath = scene.render.filepath
        original_format = scene.render.image_settings.file_format

        # Save the original viewport settings
        original_viewport_settings = save_viewport_settings(context, True, True, True)

        try:
            # Load presets from the JSON file
            presets = load_presets()

            # Store original area type
            original_area_type = context.area.type

            # Iterate over each camera
            for obj in bpy.data.objects:
                if obj.type == 'CAMERA':
                    scene.camera = obj

                    # Set the context to the current camera
                    bpy.context.view_layer.update()
                    # Ensure the camera is the active object
                    bpy.context.view_layer.objects.active = obj

                    # Set the active object as the camera for the view
                    bpy.ops.view3d.object_as_camera()


                    # Iterate over each preset
                    for preset_name, preset_settings in presets.items():
                        # Check if the preset is enabled
                        if preset_name in context.scene.my_presets and context.scene.my_presets[preset_name].enabled:
                            # Apply the viewport settings for this preset
                            load_viewport_settings(context, preset_settings)

                            # Perform a viewport render
                            bpy.ops.render.opengl(write_still=True)

                            # Define file path and save the rendered image
                            file_extension = 'exr' if self.file_format == 'OPEN_EXR' else self.file_format.lower()
                            render_filepath = os.path.join(self.directory, obj.name + "___" + preset_name + "." + file_extension)
                            bpy.data.images['Render Result'].save_render(filepath=render_filepath)

                    # Reset the context to the original area type
                    context.area.type = original_area_type


            # Iterate over each camera
            snapshot_cameras_collection = bpy.data.collections.get('SnapshotCameras')

            if snapshot_cameras_collection is not None:
                for obj in snapshot_cameras_collection.objects:

                    if obj.type == 'CAMERA':
                        scene.camera = obj

                        # Your existing logic for standard rendering
                        file_extension = 'exr' if self.file_format == 'OPEN_EXR' else self.file_format.lower()
                        scene.render.filepath = os.path.join(self.directory, obj.name + "." + file_extension)
                        scene.render.image_settings.file_format = self.file_format
                        bpy.ops.render.render(write_still=True)

        finally:
            # Revert to the original viewport settings
            load_viewport_settings(context, original_viewport_settings)
            scene.camera = original_camera
            scene.render.filepath = original_filepath
            scene.render.image_settings.file_format = original_format

        self.report({'INFO'}, "Finished rendering all cameras.")
        return {'FINISHED'}

    def invoke(self, context, event):
        context.window_manager.fileselect_add(self)
        return {'RUNNING_MODAL'}

class CustomTransformPanel(bpy.types.Panel):
    bl_label = "Snapshot Cameras"
    bl_idname = "VIEW3D_PT_save_snapshot_cameras"
    bl_space_type = 'VIEW_3D'
    bl_region_type = 'UI'
    bl_category = 'View'

    def draw(self, context):
        layout = self.layout
        scene = context.scene

        # Get the 'SnapshotCameras' collection
        snapshot_collection = bpy.data.collections.get('SnapshotCameras')

        # Draw the UIList only if the 'SnapshotCameras' collection exists
        if snapshot_collection:
            layout.label(text="Snapshot Cameras:")
            box = layout.box()
            row = box.row()
            row.template_list("CUSTOM_UL_transform_snapshots", "", snapshot_collection, "objects", scene, "snapshot_cameras_index", rows=3)


            row = box.row()
            if scene.snapshot_cameras_index >= 0 and len(snapshot_collection.objects) > scene.snapshot_cameras_index:
                camera_name = snapshot_collection.objects[scene.snapshot_cameras_index].name
                row.operator("scene.set_active_camera", text="Set Active Camera").camera_name = camera_name


        if active_snapshot_name:
            layout.label(text="Active Viewport Snapshot")
            layout.box().label(text=active_snapshot_name, icon='CAMERA_DATA')


        layout.separator()
        layout.operator("scene.save_transform_snapshot", text="Take Snapshot", icon='CAMERA_DATA')
        layout.separator()
        layout.operator("scene.render_snapshots", text="Render Snapshots", icon='RENDERLAYERS')


        # Checkbox to toggle the display of the JSON list
        layout.prop(scene.render_snapshots, "display_json_list", text="Render Passes")

        if scene.render_snapshots.display_json_list:
            for preset in scene.my_presets:
                row = layout.row()
                row.prop(preset, "enabled", text=preset.name)

class SaveTransformSnapshotOperator(bpy.types.Operator):
    bl_idname = "scene.save_transform_snapshot"
    bl_label = "Save Snapshot"
    bl_description = "Duplicate the active camera or create one from the current view and store it in the SnapshotCameras collection"
    bl_options = {'REGISTER', 'UNDO'}

    custom_name: bpy.props.StringProperty(name="Snapshot Name")

    def execute(self, context):
        scene = context.scene
        original_camera = scene.camera
        view_perspective = context.area.spaces.active.region_3d.view_perspective
        original_active_object = context.view_layer.objects.active

        # Deactivate the active camera
        scene.camera = None

        # Check if we are currently looking through a camera
        if view_perspective == 'CAMERA' and original_camera:
            # We are looking through the active camera
            if original_camera.type == 'CAMERA':
                # Duplicate the existing camera
                duplicated_camera = original_camera.copy()
                duplicated_camera.data = original_camera.data.copy()
                duplicated_camera.animation_data_clear()
            else:
                self.report({'ERROR'}, "Active object is not a camera object.")
                return {'CANCELLED'}
        else:
            # We are not looking through a camera, create a new camera
            bpy.ops.object.camera_add()
            duplicated_camera = context.active_object
            # Align the new camera to the view
            bpy.ops.view3d.camera_to_view()

            # Deselect the new camera
            duplicated_camera.select_set(False)

            # Reset the active object to what it was before creating the camera
            context.view_layer.objects.active = original_active_object

            # If there was an original active camera, reset it as active
            if original_camera:
                scene.camera = original_camera
            else:
                scene.camera = None  # Ensure no camera is active if there was none originally

            # Use the custom name provided by the user, or a default name
            duplicated_camera.name = self.custom_name if self.custom_name else "Viewport_Snapshot"
           # Unlink the new camera from all collections it's linked to

        for collection in duplicated_camera.users_collection:
            collection.objects.unlink(duplicated_camera)

        # Link the new or duplicated camera to the 'SnapshotCameras' collection
        snapshot_collection_name = 'SnapshotCameras'
        snapshot_collection = bpy.data.collections.get(snapshot_collection_name)
        if not snapshot_collection:
            snapshot_collection = bpy.data.collections.new(snapshot_collection_name)
            scene.collection.children.link(snapshot_collection)
        snapshot_collection.objects.link(duplicated_camera)

        # Select and activate the new camera
        for obj in bpy.context.view_layer.objects:
            obj.select_set(False)
        duplicated_camera.select_set(True)
        context.view_layer.objects.active = duplicated_camera

        # If we created a new camera from the view, switch back to the previous non-camera view
        if view_perspective != 'CAMERA':
            bpy.ops.view3d.view_camera()  # This toggles the current view to the camera view

        self.report({'INFO'}, f"Camera snapshot saved: {duplicated_camera.name}")
        return {'FINISHED'}

    def invoke(self, context, event):
        if context.area.spaces.active.region_3d.view_perspective != 'CAMERA':
            # No active camera, propose a name for the new one
            self.custom_name = "View_Snapshot"
        else:
            active_camera = context.scene.camera  # Get the active camera
            if active_camera and active_camera.type == 'CAMERA':
                self.custom_name = f"{active_camera.name}_Snapshot"
            else:
                self.custom_name = ""
                self.report({'ERROR'}, "No active camera to duplicate.")
                return {'CANCELLED'}
        return context.window_manager.invoke_props_dialog(self)

class CUSTOM_UL_transform_snapshots(bpy.types.UIList):
    def draw_item(self, context, layout, data, item, icon, active_data, active_propname, index):
        # Make sure your item is a camera object and draw it
        if item.type == 'CAMERA':
            layout.prop(item, "name", text="", emboss=False, icon_value=icon)

def register():
    # Preemptively unregister to avoid Blender 'registered before' info
    for cls in [CustomTransformPanel,
                SaveTransformSnapshotOperator,
                RenderSnapshotsOperator,
                SetActiveCameraOperator,
                CUSTOM_UL_transform_snapshots,
                RenderSnapshotsProperties]:
        try:
            bpy.utils.unregister_class(cls)
        except Exception:
            pass

    #print("Registering CameraSnapshot operators and panel.")
    bpy.utils.register_class(CustomTransformPanel)
    bpy.utils.register_class(SaveTransformSnapshotOperator)
    bpy.utils.register_class(RenderSnapshotsOperator)
    bpy.utils.register_class(SetActiveCameraOperator)
    bpy.utils.register_class(CUSTOM_UL_transform_snapshots)
    bpy.types.Scene.snapshot_cameras_index = bpy.props.IntProperty()
    bpy.types.Scene.display_json_list = bpy.props.BoolProperty(
        name="Display JSON List",
        default=False,
    )
    bpy.utils.register_class(RenderSnapshotsProperties)
    bpy.types.Scene.render_snapshots = bpy.props.PointerProperty(type=RenderSnapshotsProperties)



def unregister():
    #print("Unregistering CameraSnapshot operators and panel.")
    del bpy.types.Scene.display_json_list
    bpy.utils.unregister_class(CustomTransformPanel)
    bpy.utils.unregister_class(SaveTransformSnapshotOperator)
    bpy.utils.unregister_class(RenderSnapshotsOperator)
    bpy.utils.unregister_class(SetActiveCameraOperator)
    bpy.utils.unregister_class(CUSTOM_UL_transform_snapshots)
    del bpy.types.Scene.snapshot_cameras_index
    del bpy.types.Scene.render_snapshots
    bpy.utils.unregister_class(RenderSnapshotsProperties)

register()