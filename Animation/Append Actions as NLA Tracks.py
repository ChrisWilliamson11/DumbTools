# Tooltip: Append multiple actions from another blend file and add them as NLA tracks on the selected object
import bpy
from bpy.types import Operator, PropertyGroup
import os
from bpy.props import StringProperty, BoolProperty, CollectionProperty
from bpy_extras.io_utils import ImportHelper
from bpy.utils import register_class, unregister_class


class ActionItem(PropertyGroup):
    """Property group to store action name and selection state"""

    name: StringProperty(name="Action Name", default="")
    selected: BoolProperty(
        name="Select", default=False, description="Include this action"
    )


class OT_SelectActionsToAppend(Operator):
    """Select which actions to append from the blend file"""

    bl_idname = "nla.select_actions_to_append"
    bl_label = "Select Actions to Append"
    bl_options = {"REGISTER", "UNDO"}

    filepath: StringProperty()
    actions: CollectionProperty(type=ActionItem)

    def execute(self, context):
        """Append selected actions and create NLA tracks"""
        obj = context.active_object

        if not obj:
            self.report({"ERROR"}, "No active object selected")
            return {"CANCELLED"}

        # Get selected action names
        selected_action_names = [item.name for item in self.actions if item.selected]

        if not selected_action_names:
            self.report({"WARNING"}, "No actions selected")
            return {"CANCELLED"}

        # Push down any existing action first
        if obj.animation_data and obj.animation_data.action:
            existing_action = obj.animation_data.action

            # Create animation data if somehow it doesn't exist
            if not obj.animation_data:
                obj.animation_data_create()

            # Create a new track and push down the existing action
            track = obj.animation_data.nla_tracks.new()
            track.name = existing_action.name

            action_start = int(existing_action.frame_range[0])
            action_end = int(existing_action.frame_range[1])

            strip = track.strips.new(
                name=existing_action.name, start=action_start, action=existing_action
            )

            # Clear the active action
            obj.animation_data.action = None

            print(f"Pushed down existing action: {existing_action.name}")

        # Append only the selected actions
        appended_actions = []

        with bpy.data.libraries.load(self.filepath, link=False) as (data_from, data_to):
            data_to.actions = [
                name for name in data_from.actions if name in selected_action_names
            ]

        appended_actions = data_to.actions

        # Create animation data for the object if it doesn't exist
        if not obj.animation_data:
            obj.animation_data_create()

        # Create a new NLA track for each appended action
        for action in appended_actions:
            if action:
                # Create a new NLA track
                track = obj.animation_data.nla_tracks.new()
                track.name = action.name

                # Get action frame range
                action_start = int(action.frame_range[0])
                action_end = int(action.frame_range[1])

                # Add a strip with this action
                strip = track.strips.new(
                    name=action.name, start=action_start, action=action
                )

                # Set strip properties
                strip.action_frame_start = action_start
                strip.action_frame_end = action_end

                print(f"Added action '{action.name}' to NLA track")

        self.report(
            {"INFO"}, f"Appended {len(appended_actions)} action(s) as NLA tracks"
        )

        return {"FINISHED"}

    def invoke(self, context, event):
        # Load actions from the file
        self.actions.clear()

        try:
            with bpy.data.libraries.load(self.filepath) as (data_from, data_to):
                for action_name in data_from.actions:
                    item = self.actions.add()
                    item.name = action_name
                    item.selected = False  # Unchecked by default
        except Exception as e:
            self.report({"ERROR"}, f"Failed to read file: {e}")
            return {"CANCELLED"}

        if not self.actions:
            self.report({"WARNING"}, "No actions found in the selected file")
            return {"CANCELLED"}

        return context.window_manager.invoke_props_dialog(self, width=450)

    def draw(self, context):
        layout = self.layout
        layout.label(text="Select Actions to Append:")
        layout.label(text=f"Found {len(self.actions)} action(s)")

        layout.separator()

        # Create a scrollable box - Blender will handle scrolling automatically
        box = layout.box()
        col = box.column(align=True)

        for item in self.actions:
            row = col.row()
            row.prop(item, "selected", text="")
            row.label(text=item.name)


class OT_AppendActionsAsNLATracks(Operator, ImportHelper):
    """Open file browser to select a blend file containing actions"""

    bl_idname = "nla.append_actions_as_tracks"
    bl_label = "Append Actions as NLA Tracks"
    bl_options = {"REGISTER", "UNDO"}

    filter_glob: StringProperty(default="*.blend", options={"HIDDEN"})

    def execute(self, context):
        """Open the action selection dialog"""
        # Validate the file path
        if not self.filepath:
            self.report({"ERROR"}, "No file selected")
            return {"CANCELLED"}

        # Check if there's an active object before proceeding
        if not context.active_object:
            self.report(
                {"ERROR"}, "No active object selected. Please select an object first."
            )
            return {"CANCELLED"}

        # Call the action selection operator with the selected file
        bpy.ops.nla.select_actions_to_append("INVOKE_DEFAULT", filepath=self.filepath)
        return {"FINISHED"}

    def invoke(self, context, event):
        # Open the file browser first, we'll check for active object later
        context.window_manager.fileselect_add(self)
        return {"RUNNING_MODAL"}


def register():
    bpy.utils.register_class(ActionItem)
    bpy.utils.register_class(OT_SelectActionsToAppend)
    bpy.utils.register_class(OT_AppendActionsAsNLATracks)


def unregister():
    bpy.utils.unregister_class(OT_AppendActionsAsNLATracks)
    bpy.utils.unregister_class(OT_SelectActionsToAppend)
    bpy.utils.unregister_class(ActionItem)


register()
bpy.ops.nla.append_actions_as_tracks("INVOKE_DEFAULT")
