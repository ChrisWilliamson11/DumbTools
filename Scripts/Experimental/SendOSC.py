# Tooltip: Send OSC (Open Sound Control) messages from Blender for real-time communication with external applications
from pythonosc import udp_client
import math
import time

# OSC server configuration (same as your Blender script)
IP = "127.0.0.1"  # localhost
PORT = 9000

# Create OSC client
client = udp_client.SimpleUDPClient(IP, PORT)

# Animation parameters
FREQUENCY_X = 0.5  # Hz - slower wave
FREQUENCY_Y = 1.0  # Hz - faster wave
AMPLITUDE = 180    # degrees - full rotation range
SAMPLE_RATE = 60   # Hz - how many times per second to send data

try:
    print("Sending OSC data... Press Ctrl+C to stop")
    t = 0
    while True:
        # Calculate sine waves
        value_x = AMPLITUDE * math.sin(2 * math.pi * FREQUENCY_X * t)
        value_y = AMPLITUDE * math.sin(2 * math.pi * FREQUENCY_Y * t)
        
        # Send OSC messages
        client.send_message("/default/LeftArmUpper/rotation/X", value_x)
        client.send_message("/default/LeftArmUpper/rotation/Y", value_y)
        
        # Print current values
        print(f"X: {value_x:.2f}°  Y: {value_y:.2f}°")
        
        # Increment time and sleep
        t += 1/SAMPLE_RATE
        time.sleep(1/SAMPLE_RATE)

except KeyboardInterrupt:
    print("\nStopped sending OSC data")