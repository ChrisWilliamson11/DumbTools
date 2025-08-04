# Tooltip: Copy the active document from Photoshop and save it as a PNG file to the clipboard
import os
import tempfile
import comtypes.client
from PIL import Image
import win32clipboard
import io
import logging
import numpy as np
import win32con
import win32gui
import struct
import win32ui

# Set up logging
logging.basicConfig(level=logging.DEBUG, format='%(asctime)s - %(levelname)s - %(message)s')

def save_png_from_photoshop():
    logging.info("Starting save_png_from_photoshop function")
    try:
        # Connect to Photoshop
        ps_app = comtypes.client.CreateObject("Photoshop.Application")
        logging.info("Connected to Photoshop")
        ps_app.Visible = True
        
        if ps_app.Documents.Count == 0:
            raise Exception("No open documents in Photoshop.")
        
        # Get the active document
        doc = ps_app.ActiveDocument
        logging.info(f"Active document: {doc.Name}")
        
        # Create temp file for PNG
        temp_dir = tempfile.gettempdir()
        temp_png = os.path.join(temp_dir, "temp_image.png")
        
        # Convert backslashes to forward slashes for JavaScript
        js_temp_png = temp_png.replace('\\', '/')
        
        # JavaScript to save as PNG
        js_code = '''
        var pngSaveOptions = new PNGSaveOptions();
        pngSaveOptions.interlaced = false;
        app.activeDocument.saveAs(new File("''' + js_temp_png + '''"), pngSaveOptions, true, Extension.LOWERCASE);
        '''
        
        ps_app.DoJavaScript(js_code)
        logging.info(f"PNG file saved to: {temp_png}")
        
        return temp_png
    except Exception as e:
        logging.error(f"An error occurred in save_png_from_photoshop: {e}", exc_info=True)
        raise

def convert_png_to_tga(png_path):
    logging.info(f"Converting PNG to TGA: {png_path}")
    try:
        # Open the PNG image
        with Image.open(png_path) as img:
            # Ensure the image has an alpha channel
            if img.mode != 'RGBA':
                img = img.convert('RGBA')
            
            # Create temp file for TGA
            temp_dir = tempfile.gettempdir()
            temp_tga = os.path.join(temp_dir, "clipboard_image.tga")
            
            # Save as TGA
            img.save(temp_tga, format='TGA')
            
            logging.info(f"TGA file saved to: {temp_tga}")
            return temp_tga
    except Exception as e:
        logging.error(f"An error occurred in convert_png_to_tga: {e}", exc_info=True)
        raise

def copy_image_to_clipboard(image_path):
    logging.info(f"Copying image from {image_path} to clipboard")
    
    try:
        image = Image.open(image_path)
        if image.mode != 'RGBA':
            image = image.convert('RGBA')

        width, height = image.size

        # Create a device context
        hdc = win32gui.GetDC(0)
        hdc_mem = win32gui.CreateCompatibleDC(hdc)

        # Create a bitmap with alpha channel
        bmi = struct.pack('LHHHH', struct.calcsize('LHHHH'), width, height, 1, 32)
        hBitmap = win32gui.CreateDIBSection(hdc, bmi, win32con.DIB_RGB_COLORS)
        win32gui.SelectObject(hdc_mem, hBitmap)

        # Convert image to BGRA and copy to bitmap
        image_bgra = image.convert("RGBA")
        pixels = image_bgra.tobytes('raw', 'BGRA')
        win32gui.SetDIBits(hdc, hBitmap, 0, height, pixels, bmi, win32con.DIB_RGB_COLORS)

        # Copy bitmap to clipboard
        win32clipboard.OpenClipboard()
        win32clipboard.EmptyClipboard()
        win32clipboard.SetClipboardData(win32con.CF_BITMAP, hBitmap)
        win32clipboard.CloseClipboard()

        # Clean up
        win32gui.DeleteObject(hBitmap)
        win32gui.DeleteDC(hdc_mem)
        win32gui.ReleaseDC(0, hdc)

        logging.info("Image copied to clipboard with alpha channel")
    except Exception as e:
        logging.error(f"Error copying image to clipboard: {e}")

# Run the process: save PNG, convert to TGA, and copy to clipboard
try:
    png_path = save_png_from_photoshop()
    tga_path = convert_png_to_tga(png_path)
    copy_image_to_clipboard(tga_path)
    logging.info("Process completed successfully.")
except Exception as e:
    logging.error(f"An error occurred: {e}", exc_info=True)
