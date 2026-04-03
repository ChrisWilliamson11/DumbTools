import bpy
import json
import os


# Function to get the Blender appdata folder
def get_appdata_folder():
    return bpy.utils.user_resource("CONFIG")


def is_serializable(v):
    # Treat tuples of three floats (likely representing RGB colors) as non-serializable
    if (
        isinstance(v, tuple)
        and len(v) == 3
        and all(isinstance(element, float) for element in v)
    ):
        return False
    return isinstance(v, (str, int, float, bool, list, dict, tuple))


def convert_color_to_tuple(color):
    # If the color is a tuple of three floats, return it as-is
    if isinstance(color, tuple) and len(color) == 3:
        return color
    return color


def convert_tuple_to_color(value):
    # Simply return the value as color properties are already tuples
    return value


def save_space_data_settings(context):
    space = context.space_data
    settings = {
        attr: getattr(space, attr)
        for attr in dir(space)
        if not attr.startswith("__")
        and not callable(getattr(space, attr))
        and is_serializable(getattr(space, attr))
    }

    # Special handling for nested property groups like 'shading'
    shading_settings = {
        attr: getattr(space.shading, attr)
        for attr in dir(space.shading)
        if not attr.startswith("__")
        and not callable(getattr(space.shading, attr))
        and is_serializable(getattr(space.shading, attr))
    }

    if shading_settings:
        settings["shading"] = shading_settings

    return settings


def load_space_data_settings(context, settings):
    space = context.space_data
    for attr, value in settings.items():
        if attr == "shading":
            for shading_attr, shading_value in value.items():
                setattr(space.shading, shading_attr, shading_value)
        elif hasattr(space, attr) and not callable(getattr(space, attr)):
            setattr(space, attr, value)


def save_preset(preset_name, context, save_space, save_shading, save_overlay):
    viewport_settings = save_viewport_settings(
        context, save_space, save_shading, save_overlay
    )
    file_path = os.path.join(get_appdata_folder(), "overlay_presets.json")

    try:
        with open(file_path, "r") as file:
            presets = json.load(file)
    except FileNotFoundError:
        presets = {}

    presets[preset_name] = viewport_settings
    with open(file_path, "w") as file:
        json.dump(presets, file, indent=4)


def save_viewport_settings(context, save_space, save_shading, save_overlay):
    space = context.space_data
    settings = {}
    if space.type == "VIEW_3D":
        # Save overlay settings
        if save_overlay:
            overlay = space.overlay
            settings["overlay"] = serialize_settings(overlay)

        # Save space settings
        if save_space:
            settings["space"] = serialize_settings(space)

        # Save shading settings
        if save_shading:
            shading = space.shading
            settings["shading"] = serialize_settings(shading)

            # Explicitly handle the color properties
            if hasattr(shading, "single_color"):
                settings["shading"]["single_color"] = tuple(shading.single_color)
            if hasattr(shading, "background_color"):
                settings["shading"]["background_color"] = tuple(
                    shading.background_color
                )

    return settings


def serialize_settings(obj):
    data = {}
    for attr in dir(obj):
        value = getattr(obj, attr)
        # Serialize only JSON compatible data
        if not attr.startswith("__") and not callable(value):
            if isinstance(value, (str, int, float, bool, list, dict)) or (
                isinstance(value, tuple) and len(value) == 3
            ):
                data[attr] = value
    return data


def load_viewport_settings(context, settings):
    space = context.space_data
    if space.type == "VIEW_3D":
        # Apply overlay settings
        if "overlay" in settings:
            overlay = space.overlay
            for attr, value in settings["overlay"].items():
                if hasattr(overlay, attr) and not callable(getattr(overlay, attr)):
                    try:
                        setattr(overlay, attr, value)
                    except AttributeError as e:
                        print(f"Could not set overlay attribute {attr}: {e}")

        # Apply space settings
        if "space" in settings:
            for attr, value in settings["space"].items():
                if hasattr(space, attr) and not callable(getattr(space, attr)):
                    try:
                        setattr(space, attr, value)
                    except AttributeError as e:
                        print(f"Could not set space attribute {attr}: {e}")

        # Apply shading settings
        if "shading" in settings:
            shading = space.shading
            for attr, value in settings["shading"].items():
                if hasattr(shading, attr) and not callable(getattr(shading, attr)):
                    try:
                        # Convert list to tuple for color properties
                        if attr in ["single_color", "background_color"]:
                            setattr(shading, attr, tuple(value))
                        else:
                            setattr(shading, attr, value)
                    except AttributeError as e:
                        print(f"Could not set shading attribute {attr}: {e}")
                    except TypeError as e:
                        print(f"Invalid type for shading attribute {attr}: {e}")


def apply_settings(obj, settings):
    for attr, value in settings.items():
        if hasattr(obj, attr):
            prop = getattr(type(obj), attr, None)
            if prop is None or not isinstance(prop, bpy.props._PropertyDeferred):
                continue  # Skip if the attribute is not a property or is read-only

            try:
                setattr(obj, attr, value)
            except AttributeError as e:
                print(f"Could not set attribute {attr}: {e}")


def delete_viewportpreset(preset_name):
    file_path = os.path.join(get_appdata_folder(), "overlay_presets.json")
    try:
        with open(file_path, "r") as file:
            presets = json.load(file)
    except FileNotFoundError:
        return

    if preset_name in presets:
        del presets[preset_name]

    with open(file_path, "w") as file:
        json.dump(presets, file, indent=4)


def load_presets():
    file_path = os.path.join(get_appdata_folder(), "overlay_presets.json")
    try:
        with open(file_path, "r") as file:
            return json.load(file)
    except FileNotFoundError:
        return {}


class DeletePresetOperator(bpy.types.Operator):
    bl_idname = "view3d.delete_viewportpreset"
    bl_label = "Delete Overlay Preset"
    preset_name: bpy.props.StringProperty()

    def execute(self, context):
        delete_viewportpreset(self.preset_name)
        return {"FINISHED"}


class ApplyPresetOperator(bpy.types.Operator):
    bl_idname = "view3d.apply_preset"
    bl_label = "Apply or Delete Overlay Preset"
    preset_name: bpy.props.StringProperty()
    is_delete: bpy.props.BoolProperty(
        default=False, options={"HIDDEN"}
    )  # Add a hidden property to handle deletion

    def execute(self, context):
        if self.is_delete:
            delete_viewportpreset(self.preset_name)
            # Refresh the menu
            bpy.utils.unregister_class(VIEW3D_MT_OverlayPresetsMenu)
            bpy.utils.register_class(VIEW3D_MT_OverlayPresetsMenu)
            self.report({"INFO"}, f"Preset '{self.preset_name}' deleted")
        else:
            presets = load_presets()
            if self.preset_name in presets:
                settings = presets[self.preset_name]
                load_viewport_settings(
                    context, settings
                )  # Call the function to apply all settings
                self.report({"INFO"}, f"Preset '{self.preset_name}' applied")
            else:
                self.report({"WARNING"}, f"Preset '{self.preset_name}' not found")
        return {"FINISHED"}

    def invoke(self, context, event):
        if event.alt:
            # Alt+Click: Set the flag to delete and call execute
            self.is_delete = True
            return self.execute(context)
        else:
            # Normal Click: Set the flag to not delete and call execute
            self.is_delete = False
            return self.execute(context)


class SavePresetOperator(bpy.types.Operator):
    bl_idname = "view3d.save_preset"
    bl_label = "Save Overlay Preset"
    preset_name: bpy.props.StringProperty(name="Preset Name", default="Default Name")
    save_space: bpy.props.BoolProperty(name="Save Space Settings", default=True)
    save_shading: bpy.props.BoolProperty(name="Save Shading Settings", default=True)
    save_overlay: bpy.props.BoolProperty(name="Save Overlay Settings", default=True)
    has_confirmed_overwrite: bpy.props.BoolProperty(
        default=False, options={"HIDDEN"}
    )  # Track confirmation

    def execute(self, context):
        presets = load_presets()

        if self.preset_name in presets and not context.scene.confirm_overwrite:
            return bpy.ops.view3d.confirm_overwrite("INVOKE_DEFAULT")

        # If overwrite is confirmed or the preset is new, save it
        if context.scene.confirm_overwrite:
            context.scene.confirm_overwrite = False

        save_preset(
            self.preset_name,
            context,
            self.save_space,
            self.save_shading,
            self.save_overlay,
        )
        self.report({"INFO"}, f"Preset '{self.preset_name}' saved")
        return {"FINISHED"}

    def invoke(self, context, event):
        wm = context.window_manager
        invoke_response = wm.invoke_props_dialog(self, width=300)
        return invoke_response

    def draw(self, context):
        self.layout.prop(self, "preset_name", text="Preset Name")
        row = self.layout.row()
        row.prop(self, "save_space", text="Space")
        row.prop(self, "save_shading", text="Shading")
        row.prop(self, "save_overlay", text="Overlay")


# This is a new operator to handle the confirmation
class ConfirmOverwriteOperator(bpy.types.Operator):
    bl_idname = "view3d.confirm_overwrite"
    bl_label = "Confirm Overwrite"

    def execute(self, context):
        # Set the property on the scene to indicate confirmation
        context.scene.confirm_overwrite = True

        # Find the save preset operator and re-invoke it
        for op in reversed(bpy.context.window_manager.operators):
            if op.bl_idname == "view3d.save_preset":
                bpy.ops.view3d.save_preset("INVOKE_DEFAULT")
                break

        return {"FINISHED"}

    def invoke(self, context, event):
        return context.window_manager.invoke_confirm(self, event)


class VIEW3D_MT_OverlayPresetsMenu(bpy.types.Menu):
    bl_label = "Overlay Presets"
    bl_idname = "VIEW3D_MT_overlay_presets_menu"

    def draw(self, context):
        layout = self.layout
        presets = load_presets()

        layout.operator("view3d.save_preset", text="Save New Preset")
        layout.separator()

        for preset_name in presets.keys():
            apply_op = layout.operator("view3d.apply_preset", text=preset_name)
            apply_op.preset_name = preset_name


def draw_header(self, context):
    layout = self.layout
    row = layout.row(align=True)
    row.menu("VIEW3D_MT_overlay_presets_menu", text="", icon="DESKTOP")


def register():
    bpy.utils.register_class(ApplyPresetOperator)
    bpy.utils.register_class(SavePresetOperator)
    bpy.utils.register_class(DeletePresetOperator)
    bpy.utils.register_class(ConfirmOverwriteOperator)
    bpy.types.Scene.confirm_overwrite = bpy.props.BoolProperty(default=False)

    bpy.utils.register_class(VIEW3D_MT_OverlayPresetsMenu)
    bpy.types.VIEW3D_HT_header.append(draw_header)


def unregister():
    bpy.utils.unregister_class(ApplyPresetOperator)
    bpy.utils.unregister_class(SavePresetOperator)
    bpy.utils.unregister_class(DeletePresetOperator)
    bpy.utils.unregister_class(ConfirmOverwriteOperator)
    del bpy.types.Scene.confirm_overwrite

    bpy.utils.unregister_class(VIEW3D_MT_OverlayPresetsMenu)
    bpy.types.VIEW3D_HT_header.remove(draw_header)


register()
