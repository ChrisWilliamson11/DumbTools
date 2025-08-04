# Tooltip: Test COM types client functionality for Windows application integration
import comtypes.client

try:
    ps_app = comtypes.client.CreateObject("Photoshop.Application")
    print("Photoshop COM object created successfully.")
except Exception as e:
    print(f"Failed to create Photoshop COM object: {e}")