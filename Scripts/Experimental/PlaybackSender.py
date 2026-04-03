# Tooltip: Sends a UDP signal to trigger playback in Blender instances running PlaybackReceiver
# This script can be run standalone (outside Blender) or as a Blender addon
import socket
import struct
import sys

# Configuration
MULTICAST_GROUP = "239.255.50.50"  # Must match PlaybackReceiver
DEFAULT_PORT = 50000

# Commands
PLAY_COMMAND = b"PLAY"
STOP_COMMAND = b"STOP"
TOGGLE_COMMAND = b"TOGGLE"


def send_command(command, ip=MULTICAST_GROUP, port=DEFAULT_PORT):
    """Send a UDP multicast command to all receivers"""
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM, socket.IPPROTO_UDP)
    try:
        # Set TTL for multicast (1 = local network only)
        sock.setsockopt(socket.IPPROTO_IP, socket.IP_MULTICAST_TTL, 1)
        sock.sendto(command, (ip, port))
        print(f"Sent '{command.decode()}' to multicast {ip}:{port}")
        return True
    except Exception as e:
        print(f"Error sending command: {e}")
        return False
    finally:
        sock.close()


def send_play(ip=MULTICAST_GROUP, port=DEFAULT_PORT):
    """Send play command"""
    return send_command(PLAY_COMMAND, ip, port)


def send_stop(ip=MULTICAST_GROUP, port=DEFAULT_PORT):
    """Send stop command"""
    return send_command(STOP_COMMAND, ip, port)


def send_toggle(ip=MULTICAST_GROUP, port=DEFAULT_PORT):
    """Send toggle command"""
    return send_command(TOGGLE_COMMAND, ip, port)


def send_to_multiple(command, targets):
    """Send command to multiple IP:port targets
    
    Args:
        command: The command bytes to send
        targets: List of (ip, port) tuples
    """
    for ip, port in targets:
        send_command(command, ip, port)


# Blender integration (only if running in Blender)
try:
    import bpy
    
    class PlaybackSendPlay(bpy.types.Operator):
        """Send play command to receivers"""
        bl_idname = "wm.playback_send_play"
        bl_label = "Send Play"

        def execute(self, context):
            wm = context.window_manager
            send_play(wm.playback_sender_ip, wm.playback_sender_port)
            return {'FINISHED'}

    class PlaybackSendStop(bpy.types.Operator):
        """Send stop command to receivers"""
        bl_idname = "wm.playback_send_stop"
        bl_label = "Send Stop"

        def execute(self, context):
            wm = context.window_manager
            send_stop(wm.playback_sender_ip, wm.playback_sender_port)
            return {'FINISHED'}

    class PlaybackSendToggle(bpy.types.Operator):
        """Send toggle command to receivers"""
        bl_idname = "wm.playback_send_toggle"
        bl_label = "Send Toggle"

        def execute(self, context):
            wm = context.window_manager
            send_toggle(wm.playback_sender_ip, wm.playback_sender_port)
            return {'FINISHED'}

    class PlaybackSenderPanel(bpy.types.Panel):
        bl_label = "Playback Sender"
        bl_idname = "VIEW3D_PT_playback_sender"
        bl_space_type = 'VIEW_3D'
        bl_region_type = 'UI'
        bl_category = "Tool"

        def draw(self, context):
            layout = self.layout
            wm = context.window_manager
            
            layout.prop(wm, "playback_sender_ip")
            layout.prop(wm, "playback_sender_port")
            
            col = layout.column(align=True)
            col.operator(PlaybackSendPlay.bl_idname, text="Play", icon='PLAY')
            col.operator(PlaybackSendStop.bl_idname, text="Stop", icon='PAUSE')
            col.operator(PlaybackSendToggle.bl_idname, text="Toggle", icon='UV_SYNC_SELECT')

    def register():
        bpy.utils.register_class(PlaybackSendPlay)
        bpy.utils.register_class(PlaybackSendStop)
        bpy.utils.register_class(PlaybackSendToggle)
        bpy.utils.register_class(PlaybackSenderPanel)
        bpy.types.WindowManager.playback_sender_ip = bpy.props.StringProperty(
            name="Multicast IP",
            default=MULTICAST_GROUP
        )
        bpy.types.WindowManager.playback_sender_port = bpy.props.IntProperty(
            name="Port", 
            default=DEFAULT_PORT,
            min=1024,
            max=65535
        )

    def unregister():
        bpy.utils.unregister_class(PlaybackSendPlay)
        bpy.utils.unregister_class(PlaybackSendStop)
        bpy.utils.unregister_class(PlaybackSendToggle)
        bpy.utils.unregister_class(PlaybackSenderPanel)
        del bpy.types.WindowManager.playback_sender_ip
        del bpy.types.WindowManager.playback_sender_port

    register()

except ImportError:
    # Running outside Blender - use as command line tool
    if __name__ == "__main__":
        import argparse
        
        parser = argparse.ArgumentParser(description="Send playback commands to Blender instances")
        parser.add_argument("command", choices=["play", "stop", "toggle"], help="Command to send")
        parser.add_argument("--ip", default=MULTICAST_GROUP, help=f"Multicast IP (default: {MULTICAST_GROUP})")
        parser.add_argument("--port", type=int, default=DEFAULT_PORT, help=f"Target port (default: {DEFAULT_PORT})")
        
        args = parser.parse_args()
        
        if args.command == "play":
            send_play(args.ip, args.port)
        elif args.command == "stop":
            send_stop(args.ip, args.port)
        elif args.command == "toggle":
            send_toggle(args.ip, args.port)

