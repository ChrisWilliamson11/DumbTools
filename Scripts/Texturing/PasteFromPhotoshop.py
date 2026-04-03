# Tooltip: This script will paste an image from Photoshop into the active scene
import os
import tempfile
import comtypes.client
from PIL import Image
import win32clipboard
from io import BytesIO

# Function to copy PNG to clipboard
def copy_image_to_clipboard(image_path):
    image = Image.open(image_path)
    output = BytesIO()
    image.convert("RGBA").save(output, "PNG")
    data = output.getvalue()[8:]  # remove PNG header (8 bytes)
    
    # Copy image data to clipboard
    win32clipboard.OpenClipboard()
    win32clipboard.EmptyClipboard()
    win32clipboard.SetClipboardData(win32clipboard.CF_DIB, data)
    win32clipboard.CloseClipboard()

# Function to control Photoshop
def save_png_with_transparency():
    try:
        # Connect to Photoshop
        ps_app = comtypes.client.CreateObject("Photoshop.Application")
        ps_app.Visible = True  # Make Photoshop visible
    except Exception as e:
        print(f"Failed to create Photoshop COM object: {e}")
        raise

    if ps_app.Documents.Count == 0:
        raise Exception("No open documents in Photoshop.")
    
    # Get the active document
    doc = ps_app.ActiveDocument
    
    # Ensure the document has a transparent background
    if doc.BackgroundLayer:
        doc.BackgroundLayer.IsBackgroundLayer = False
    
    # Create a temp file to save the PNG
    temp_file = os.path.join(tempfile.gettempdir(), "clipboard_image.png")
    
    # Export options for PNG
    options = comtypes.client.CreateObject("Photoshop.ExportOptionsSaveForWeb")
    options.Format = 13  # PNG format
    options.PNG8 = False  # 24-bit PNG
    options.Transparency = True
    
    # Export the file
    doc.Export(ExportIn=temp_file, ExportAs=2, Options=options)  # 2 is SaveForWeb
    
    return temp_file

# Run the process: save PNG and copy to clipboard
try:
    png_path = save_png_with_transparency()
    print(f"Image saved to: {png_path}")
    copy_image_to_clipboard(png_path)
    print("Image copied to clipboard with transparency.")
except Exception as e:
    print(f"An error occurred: {e}")
