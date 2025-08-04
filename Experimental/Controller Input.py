# Tooltip:  Use a game controller to interact with Blender.
import bpy
import mido
import threading
import atexit
import re
import XInput

# Define button identifiers based on the XInput library's constants or your own mapping
BUTTONS = {
    'DPAD_UP': 0x0001,
    'DPAD_DOWN': 0x0002,
    'DPAD_LEFT': 0x0004,
    'DPAD_RIGHT': 0x0008,
    'START': 0x0010,
    'BACK': 0x0020,
    'LEFT_THUMB': 0x0040,
    'RIGHT_THUMB': 0x0080,
    'LEFT_SHOULDER': 0x0100,
    'RIGHT_SHOULDER': 0x0200,
    'A': 0x1000,
    'B': 0x2000,
    'X': 0x4000,
    'Y': 0x8000,
}

# Define axes identifiers, possibly with positive/negative differentiation for analog inputs
AXES = {
    'LEFT_TRIGGER': 'bLeftTrigger',
    'RIGHT_TRIGGER': 'bRightTrigger',
    'LEFT_THUMB_X': 'sThumbLX',
    'LEFT_THUMB_-X': 'sThumbLX',
    'LEFT_THUMB_Y': 'sThumbLY',
    'LEFT_THUMB_-Y': 'sThumbLY',
    'RIGHT_THUMB_X': 'sThumbRX',
    'RIGHT_THUMB_-X': 'sThumbRX',
    'RIGHT_THUMB_Y': 'sThumbRY',
    'RIGHT_THUMB_-Y': 'sThumbRY',
}


# Combine mappings for EnumProperty
INPUTS = {**BUTTONS, **AXES}  # Combine your dictionaries

# Global reference to manage the MIDI input connection
global_inport = None

def get_controller_input_items():
    items = []
    for name, identifier in INPUTS.items():
        # For binary button inputs, use the identifier directly
        if name in BUTTONS:
            items.append((name, name.replace('_', ' '), 'Button input'))
        # For axes, you might want to handle positive and negative directions
        elif name in AXES:
            items.append((name + "_POS", name.replace('_', ' ') + " Positive", 'Axis input positive'))
            items.append((name + "_NEG", name.replace('_', ' ') + " Negative", 'Axis input negative'))
    return items

class ControllerControlAssignment(bpy.types.PropertyGroup):
    controller_input: bpy.props.EnumProperty(
        items=get_controller_input_items(),
        name="Controller Input",
        description="Select the controller input type",
    )
    property_path: bpy.props.StringProperty(name="Property Path")
    min_value: bpy.props.FloatProperty(name="Min Value", default=0.0)
    max_value: bpy.props.FloatProperty(name="Max Value", default=1.0)


# Property group for MIDI controls
class MIDIControlAssignment(bpy.types.PropertyGroup):
    control_id: bpy.props.IntProperty(name="Control ID")
    property_path: bpy.props.StringProperty(name="Property Path")
    min_value: bpy.props.FloatProperty(name="Min Value", default=0.0)
    max_value: bpy.props.FloatProperty(name="Max Value", default=1.0)

# UI List to display MIDI controls
class MIDIControlsUIList(bpy.types.UIList):
    def draw_item(self, context, layout, data, item, icon, active_data, active_propname, index):
        row = layout.row()
        split = row.split(factor=0.25)
        split.prop(item, "control_id", text="ID", emboss=False)
        split.prop(item, "property_path", text="Path", emboss=False)
        split.prop(item, "min_value", text="Min")
        split.prop(item, "max_value", text="Max")
        
# UI List to display Controller controls
class ControllerControlsUIList(bpy.types.UIList):
    def draw_item(self, context, layout, data, item, icon, active_data, active_propname, index):
        # Assuming 'item' is an instance of ControllerControlAssignment
        if self.layout_type in {'DEFAULT', 'COMPACT'}:
            row = layout.row(align=True)
            row.label(text="", icon='GAME')  # Just as an example, you can use any icon
            row.prop(item, "controller_input", text="", emboss=False)  # Dropdown for input type
            row.prop(item, "property_path", text="", emboss=False)  # Text field for property path
            row.prop(item, "min_value", text="Min", emboss=False)  # Min value
            row.prop(item, "max_value", text="Max", emboss=False)  # Max value

        elif self.layout_type in {'GRID'}:
            layout.alignment = 'CENTER'
            layout.label(text="", icon='GAME')  # Placeholder for potential GRID layout usage


class AddControllerControl(bpy.types.Operator):
    """Add a new controller control"""
    bl_idname = "wm.add_controller_control"
    bl_label = "Add Controller Control"

    def execute(self, context):
        item = context.scene.controller_controls.add()
        # Set default values for the new item
        item.controller_input = 'A'  # Assuming 'A' is a valid identifier in your enum
        item.property_path = "bpy.data.objects['Cube'].location[0]"  # Example path
        context.scene.active_controller_control_index = len(context.scene.controller_controls) - 1
        return {'FINISHED'}

class RemoveControllerControl(bpy.types.Operator):
    """Remove an existing controller control"""
    bl_idname = "wm.remove_controller_control"
    bl_label = "Remove Controller Control"

    def execute(self, context):
        index = context.scene.active_controller_control_index
        if context.scene.controller_controls and index < len(context.scene.controller_controls):
            context.scene.controller_controls.remove(index)
            context.scene.active_controller_control_index = min(max(0, index - 1), len(context.scene.controller_controls) - 1)
        return {'FINISHED'}

# Operator to add a MIDI control assignment
class AddMIDIControl(bpy.types.Operator):
    bl_idname = "wm.add_midi_control"
    bl_label = "Add MIDI Control"
    def execute(self, context):
        item = context.scene.midi_controls.add()
        item.control_id = 0  # Example default value
        item.property_path = "bpy.data.objects['Cube'].location[0]"  # Example path
        context.scene.active_midi_control_index = len(context.scene.midi_controls) - 1
        return {'FINISHED'}

# Operator to remove a MIDI control assignment
class RemoveMIDIControl(bpy.types.Operator):
    bl_idname = "wm.remove_midi_control"
    bl_label = "Remove MIDI Control"
    def execute(self, context):
        index = context.scene.active_midi_control_index
        context.scene.midi_controls.remove(index)
        context.scene.active_midi_control_index = min(max(0, index - 1), len(context.scene.midi_controls) - 1)
        return {'FINISHED'}

class MIDIConnect(bpy.types.Operator):
    """Connect to MIDI"""
    bl_idname = "wm.midi_connect"
    bl_label = "Connect MIDI"

    def execute(self, context):
        # Start the MIDI listening thread
        threading.Thread(target=midi_listen_thread, daemon=True).start()
        self.report({'INFO'}, "MIDI Connected")
        return {'FINISHED'}

class MIDIDisconnect(bpy.types.Operator):
    """Disconnect MIDI"""
    bl_idname = "wm.midi_disconnect"
    bl_label = "Disconnect MIDI"

    def execute(self, context):
        # Close MIDI port and stop listening thread safely
        cleanup_midi_port()
        print("MIDI Disconnected")
        return {'FINISHED'}

class ControllerControlPanel(bpy.types.Panel):
    bl_label = "Controller Controls"
    bl_idname = "OBJECT_PT_controller_controls"
    bl_space_type = 'VIEW_3D'
    bl_region_type = 'UI'
    bl_category = 'Controllers'

    def draw(self, context):
        layout = self.layout
        scene = context.scene

        # Display the UIList for controller controls
        layout.template_list("ControllerControlsUIList", "", scene, "controller_controls", scene, "active_controller_control_index")

        # Buttons for adding and removing controller controls
        row = layout.row()
        row.operator("wm.add_controller_control", text="Add Control")
        row.operator("wm.remove_controller_control", text="Remove Control")

        # Display the controller_input EnumProperty for the active control
        if scene.controller_controls:
            active_index = scene.active_controller_control_index
            if 0 <= active_index < len(scene.controller_controls):
                control = scene.controller_controls[active_index]

                row = layout.row()
                row.prop(control, "controller_input", text="Input Type")

# Panel in the 3D Viewport to display the MIDI controls UI
class MIDIControlPanel(bpy.types.Panel):
    bl_label = "MIDI Controls"
    bl_idname = "OBJECT_PT_midi_controls"
    bl_space_type = 'VIEW_3D'
    bl_region_type = 'UI'
    bl_category = 'Controllers'

    def draw(self, context):
        layout = self.layout
        scene = context.scene

        # MIDI Connect/Disconnect Buttons
        row = layout.row()
        row.operator("wm.midi_connect", text="Connect MIDI")
        row.operator("wm.midi_disconnect", text="Disconnect MIDI")

        # Dynamic list of MIDI controls
        layout.template_list("MIDIControlsUIList", "", scene, "midi_controls", scene, "active_midi_control_index")

        # Buttons for adding and removing MIDI controls
        row = layout.row()
        row.operator("wm.add_midi_control", text="Add Control")
        row.operator("wm.remove_midi_control", text="Remove Control")

def apply_controller_input(control, input_value):
    # Determine if the input is binary or analog
    if control.controller_input in BUTTONS:
        # Binary input: check if pressed
        mapped_value = control.max_value if input_value else control.min_value
    else:
        # Analog input: map from input range to min-max range
        # Example assumes analog input_value is in range [0, 255]
        mapped_value = map_value(input_value, 0, 255, control.min_value, control.max_value)
    
    apply_mapped_value_to_property(control.property_path, mapped_value)

def get_controller_input_items():
    items = []
    # Add buttons to the enum
    for name, _ in BUTTONS.items():
        items.append((name, name.replace('_', ' '), 'Button input'))
    # Add axes to the enum
    for name, _ in AXES.items():
        items.append((name, name.replace('_', ' '), 'Axis input'))
    return items

def apply_mapped_value_to_property(property_path, value):
    try:
        # Assume the first part always 'bpy.data'
        base_path, _, prop_path = property_path.partition('].')
        base_path += ']'  # Add back the closing bracket removed by partition
        
        # Resolve the base object/data using eval in a limited and controlled context
        base_obj = eval(base_path, {"bpy": bpy})
        
        # Check if the property path includes an index and split it
        if '[' in prop_path:
            prop_name, index_part = prop_path.split('[')
            index = int(index_part[:-1])  # Remove ']' and convert to int
            current_value = getattr(base_obj, prop_name)
            current_value[index] = value
        else:
            # Directly set the property if there's no index
            setattr(base_obj, prop_path, value)
        
        print(f"Successfully applied {value} to {property_path}")
    except Exception as e:
        print(f"Error applying value: {e}")

def controller_listen_thread():
    joystick = xinput.XInputJoystick.enumerate_devices()[0]  # Example for first controller
    
    while True:
        state = joystick.get_state()
        # Example: Check for button press and apply bound property changes
        for control in bpy.context.scene.controller_controls:
            # Example logic for button press
            if state.buttons[control.button_id]:
                mapped_value = map_value(state.buttons[control.button_id], 0, 1, control.min_value, control.max_value)
                apply_mapped_value_to_property(control.property_path, mapped_value)
        time.sleep(0.1)  # Polling interval

# Function to handle incoming MIDI messages
def handle_midi_message(msg):
    scene = bpy.context.scene
    for control in scene.midi_controls:
        print(f"Checking control ID {control.control_id} against MIDI control {msg.control}")  # Debug print
        if msg.type == 'control_change' and msg.control == control.control_id:
            mapped_value = map_value(msg.value, 0, 127, control.min_value, control.max_value)
            print(f"Mapped value for control ID {msg.control}: {mapped_value}")  # Debug print
            bpy.app.timers.register(lambda m=mapped_value, p=control.property_path: apply_mapped_value_to_property(p, m))

def map_value(value, in_min, in_max, out_min, out_max):
    return (value - in_min) * (out_max - out_min) / (in_max - in_min) + out_min

# MIDI listening thread
def midi_listen_thread():
    global global_inport
    try:
        # Attempt to open the first available MIDI input
        global_inport = mido.open_input(mido.get_input_names()[0])
        print("Listening to MIDI port:", mido.get_input_names()[0])
        for msg in global_inport:
            print(msg)  # Print every MIDI message received
            handle_midi_message(msg)  # Call the function to handle the MIDI message
    except Exception as e:
        print("Failed to connect to MIDI port:", e)

# Cleanup function to close MIDI port
def cleanup_midi_port():
    if global_inport is not None:
        global_inport.close()
        print("MIDI port closed.")

atexit.register(cleanup_midi_port)

def register():
    # Register all property groups, UI lists, and operators
    bpy.utils.register_class(ControllerControlAssignment)
    bpy.utils.register_class(ControllerControlsUIList)
    bpy.utils.register_class(MIDIControlAssignment)
    bpy.utils.register_class(MIDIControlsUIList)
    bpy.utils.register_class(AddMIDIControl)
    bpy.utils.register_class(RemoveMIDIControl)
    bpy.utils.register_class(MIDIConnect)
    bpy.utils.register_class(MIDIDisconnect)
    bpy.utils.register_class(MIDIControlPanel)
    bpy.utils.register_class(ControllerControlPanel)  # Make sure this is registered
    bpy.utils.register_class(AddControllerControl)
    bpy.utils.register_class(RemoveControllerControl)

    # Add the collections to the scene
    bpy.types.Scene.midi_controls = bpy.props.CollectionProperty(type=MIDIControlAssignment)
    bpy.types.Scene.controller_controls = bpy.props.CollectionProperty(type=ControllerControlAssignment)
    bpy.types.Scene.active_midi_control_index = bpy.props.IntProperty()
    bpy.types.Scene.active_controller_control_index = bpy.props.IntProperty()

    # If you have an active index for controller controls, register it here as well

def unregister():
    # Unregister all classes in reverse order
    bpy.utils.unregister_class(ControllerControlPanel)  # And unregister it here
    bpy.utils.unregister_class(MIDIControlPanel)
    bpy.utils.unregister_class(MIDIDisconnect)
    bpy.utils.unregister_class(MIDIConnect)
    bpy.utils.unregister_class(RemoveMIDIControl)
    bpy.utils.unregister_class(AddMIDIControl)
    bpy.utils.unregister_class(MIDIControlsUIList)
    bpy.utils.unregister_class(MIDIControlAssignment)
    bpy.utils.unregister_class(ControllerControlsUIList)
    bpy.utils.unregister_class(ControllerControlAssignment)
    bpy.utils.unregister_class(RemoveControllerControl)
    bpy.utils.unregister_class(AddControllerControl)

    # Remove the collections from the scene
    del bpy.types.Scene.active_midi_control_index
    del bpy.types.Scene.active_controller_control_index
    del bpy.types.Scene.midi_controls
    del bpy.types.Scene.controller_controls

register()


