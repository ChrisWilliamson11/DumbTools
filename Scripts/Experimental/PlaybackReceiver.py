# Tooltip: Listens on a UDP port for a signal to start playback - enables synced playback across multiple Blender instances
import bpy
import socket
import struct
import threading

# Configuration
DEFAULT_PORT = 50000
MULTICAST_GROUP = "239.255.50.50"  # Multicast address for playback sync
BUFFER_SIZE = 1024
PLAY_COMMAND = b"PLAY"
STOP_COMMAND = b"STOP"
TOGGLE_COMMAND = b"TOGGLE"

receiver_thread = None
server_socket = None
running = False


def handle_command(command):
    """Handle incoming command - must be called from main thread"""
    command = command.strip().upper()

    if command == PLAY_COMMAND:
        if not bpy.context.screen.is_animation_playing:
            bpy.ops.screen.animation_play()
            print("Playback started")
    elif command == STOP_COMMAND:
        if bpy.context.screen.is_animation_playing:
            bpy.ops.screen.animation_cancel(restore_frame=False)
            print("Playback stopped")
    elif command == TOGGLE_COMMAND:
        bpy.ops.screen.animation_play()
        print("Playback toggled")


def listen_for_commands(port):
    """Background thread that listens for multicast UDP commands"""
    global server_socket, running

    server_socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM, socket.IPPROTO_UDP)
    server_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    server_socket.settimeout(1.0)  # Allow checking running flag

    try:
        # Bind to all interfaces on the port
        server_socket.bind(('', port))

        # Join the multicast group
        mreq = struct.pack("4sl", socket.inet_aton(MULTICAST_GROUP), socket.INADDR_ANY)
        server_socket.setsockopt(socket.IPPROTO_IP, socket.IP_ADD_MEMBERSHIP, mreq)

        print(f"Playback Receiver listening on multicast {MULTICAST_GROUP}:{port}")
        
        while running:
            try:
                data, addr = server_socket.recvfrom(BUFFER_SIZE)
                print(f"Received: {data} from {addr}")
                # Queue command to be executed in main thread
                bpy.app.timers.register(lambda: handle_command(data) or None, first_interval=0.0)
            except socket.timeout:
                continue
            except Exception as e:
                if running:
                    print(f"Error receiving: {e}")
    finally:
        server_socket.close()
        print("Playback Receiver stopped")


class PlaybackReceiverStart(bpy.types.Operator):
    """Start listening for playback commands"""
    bl_idname = "wm.playback_receiver_start"
    bl_label = "Start Playback Receiver"

    def execute(self, context):
        global receiver_thread, running
        
        if receiver_thread is not None and receiver_thread.is_alive():
            self.report({'WARNING'}, 'Receiver is already running')
            return {'CANCELLED'}
        
        running = True
        port = context.window_manager.playback_receiver_port
        receiver_thread = threading.Thread(target=listen_for_commands, args=(port,), daemon=True)
        receiver_thread.start()
        
        self.report({'INFO'}, f'Listening on port {port}')
        return {'FINISHED'}


class PlaybackReceiverStop(bpy.types.Operator):
    """Stop listening for playback commands"""
    bl_idname = "wm.playback_receiver_stop"
    bl_label = "Stop Playback Receiver"

    def execute(self, context):
        global running, receiver_thread
        
        running = False
        if receiver_thread is not None:
            receiver_thread.join(timeout=2.0)
            receiver_thread = None
            self.report({'INFO'}, 'Receiver stopped')
        else:
            self.report({'WARNING'}, 'Receiver was not running')
        
        return {'FINISHED'}


class PlaybackReceiverPanel(bpy.types.Panel):
    bl_label = "Playback Receiver"
    bl_idname = "VIEW3D_PT_playback_receiver"
    bl_space_type = 'VIEW_3D'
    bl_region_type = 'UI'
    bl_category = "Tool"

    def draw(self, context):
        layout = self.layout
        wm = context.window_manager
        
        layout.prop(wm, "playback_receiver_port")
        
        row = layout.row(align=True)
        row.operator(PlaybackReceiverStart.bl_idname, text="Start", icon='PLAY')
        row.operator(PlaybackReceiverStop.bl_idname, text="Stop", icon='PAUSE')
        
        # Status indicator
        if receiver_thread is not None and receiver_thread.is_alive():
            layout.label(text="Status: Listening", icon='CHECKMARK')
        else:
            layout.label(text="Status: Stopped", icon='X')


def register():
    bpy.utils.register_class(PlaybackReceiverStart)
    bpy.utils.register_class(PlaybackReceiverStop)
    bpy.utils.register_class(PlaybackReceiverPanel)
    bpy.types.WindowManager.playback_receiver_port = bpy.props.IntProperty(
        name="Port", 
        default=DEFAULT_PORT,
        min=1024,
        max=65535
    )


def unregister():
    global running
    running = False
    bpy.utils.unregister_class(PlaybackReceiverStart)
    bpy.utils.unregister_class(PlaybackReceiverStop)
    bpy.utils.unregister_class(PlaybackReceiverPanel)
    del bpy.types.WindowManager.playback_receiver_port


register()

