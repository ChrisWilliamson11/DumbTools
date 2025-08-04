# Tooltip: Experental OSC plugin
import threading
from pythonosc.dispatcher import Dispatcher
from pythonosc.osc_server import BlockingOSCUDPServer
import bpy

osc_thread = None  # Global reference to the OSC server thread

# Function to handle incoming OSC messages
def default_handler(address, *args):
    print(f"Received OSC message: {address} with arguments: {args}")

# Function to start the OSC server
def start_osc_server(ip, port):
    global osc_thread
    dispatcher = Dispatcher()
    dispatcher.set_default_handler(default_handler)
    server = BlockingOSCUDPServer((ip, port), dispatcher)
    print(f"Starting OSC Server on {ip}:{port}")
    server.serve_forever()

# Blender Operator to start the OSC server
class OSCStart(bpy.types.Operator):
    """Start OSC Server"""
    bl_idname = "wm.start_osc_server"
    bl_label = "Start OSC Server"

    def execute(self, context):
        global osc_thread
        wm = context.window_manager
        if osc_thread is None or not osc_thread.is_alive():
            osc_thread = threading.Thread(target=start_osc_server, args=(wm.osc_ip, wm.osc_port))
            osc_thread.daemon = True 
            osc_thread.start()
        else:
            self.report({'INFO'}, 'OSC Server is already running')
        return {'FINISHED'}

# Blender Operator to stop the OSC server
class OSCStop(bpy.types.Operator):
    """Stop OSC Server"""
    bl_idname = "wm.stop_osc_server"
    bl_label = "Stop OSC Server"

    def execute(self, context):
        global osc_thread
        if osc_thread is not None:
            # Stopping the thread gracefully requires implementation based on your server setup.
            self.report({'INFO'}, 'Havent Done this yet...')
        return {'FINISHED'}

# Panel for OSC controls in the 3D View sidebar
class OSCPanel(bpy.types.Panel):
    bl_label = "OSC Controls"
    bl_idname = "VIEW3D_PT_osc"
    bl_space_type = 'VIEW_3D'
    bl_region_type = 'UI'
    bl_category = "Tool"

    def draw(self, context):
        layout = self.layout
        wm = context.window_manager

        layout.prop(wm, "osc_ip")
        layout.prop(wm, "osc_port")
        layout.operator(OSCStart.bl_idname)
        layout.operator(OSCStop.bl_idname)

def register():
    bpy.utils.register_class(OSCStart)
    bpy.utils.register_class(OSCStop)
    bpy.utils.register_class(OSCPanel)
    bpy.types.WindowManager.osc_ip = bpy.props.StringProperty(name="IP Address", default="127.0.0.1")
    bpy.types.WindowManager.osc_port = bpy.props.IntProperty(name="Port", default=9001)

def unregister():
    bpy.utils.unregister_class(OSCStart)
    bpy.utils.unregister_class(OSCStop)
    bpy.utils.unregister_class(OSCPanel)
    del bpy.types.WindowManager.osc_ip
    del bpy.types.WindowManager.osc_port

if __name__ == "__main__":
    register()
