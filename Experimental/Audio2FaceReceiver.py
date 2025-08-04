# Tooltip:  Stream Audio2Face data to Blender
import socket

import json

import threading

import bpy



def process_complete_message(data_buffer):

    """

    Process a complete JSON message and update matching shape keys on 'Face' object,

    ignoring missing shape keys.

    """

    if not data_buffer.strip():  # Check if the buffer is empty or contains only whitespace

        print("Warning: Attempted to process an empty or whitespace-only buffer.")

        return



    try:

        parsed_data = json.loads(data_buffer.decode('utf-8'))

        print("Parsed JSON successfully.")



        obj = bpy.data.objects.get('Face')

        if obj is None:

            print("Object 'Face' not found.")

            return

        

        # Ensure the active object has the expected shape keys

        if obj.data.shape_keys is None:

            print(f"Object '{obj.name}' has no shape keys.")

            return



        key_blocks = obj.data.shape_keys.key_blocks

        if key_blocks:

            facial_data = parsed_data.get("Audio2Face", {}).get("Facial", {})

            names = facial_data.get("Names", [])

            weights = facial_data.get("Weights", [])



            for name, weight in zip(names, weights):

                # Normalize the shape key name to match Blender's naming

                adjusted_name = name[0].lower() + name[1:]

                if adjusted_name in key_blocks:

                    key_blocks[adjusted_name].value = weight

                    print(f"Updated '{adjusted_name}' to {weight}.")

                else:

                    print(f"Shape key '{adjusted_name}' not found in 'Face'.")

        else:

            print("No shape keys found in 'Face'.")

            

    except json.JSONDecodeError as e:

        print("Failed to decode JSON:", e)



def listen_for_data(port):

    """

    Open a socket and listen for incoming data in a separate thread.

    """

    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:

        s.bind(('localhost', port))

        s.listen()

        print(f"Listening on port {port}...")

        

        conn, addr = s.accept()

        with conn:

            print(f"Connected by {addr}")

            data_buffer = b''  # Initialize an empty buffer for incoming data

            expected_length = None  # Initialize expected length with None



            while True:

                data = conn.recv(1024)

                if not data:

                    break  # Connection closed

                

                data_buffer += data



                while data_buffer:

                    # If expected_length is None, try to read the length prefix

                    if expected_length is None:

                        if len(data_buffer) >= 4:  # Assuming the length prefix is 4 bytes

                            expected_length = int.from_bytes(data_buffer[:4], byteorder='big')

                            data_buffer = data_buffer[4:]  # Remove the length prefix from the buffer

                        else:

                            # Not enough data to read length prefix

                            break

                    

                    # If there's enough data in the buffer for the expected length, process the message

                    if len(data_buffer) >= expected_length:

                        complete_message = data_buffer[:expected_length]

                        process_complete_message(complete_message)  # Process the complete message

                        data_buffer = data_buffer[expected_length:]  # Remove the processed message from the buffer

                        expected_length = None  # Reset expected_length for the next message

                    else:

                        # Not enough data for a complete message, wait for more data

                        break



def start_listener():

    """

    Start the listener in a new thread.

    """

    port = 12345  # Example port number

    threading.Thread(target=listen_for_data, args=(port,), daemon=True).start()

start_listener()