# Tooltip: Organize HDRI files by moving folders containing HDR/EXR files to a dedicated HDRI directory
import os
import shutil
from pathlib import Path

def move_hdri_folders(root_path):
    # Create HDRI destination folder if it doesn't exist
    hdri_dest = os.path.join(root_path, 'HDRI')
    os.makedirs(hdri_dest, exist_ok=True)
    
    # Walk through all subdirectories
    for dirpath, dirnames, filenames in os.walk(root_path):
        # Skip the HDRI destination folder itself
        if dirpath == hdri_dest:
            continue
            
        # Check if any .hdr files exist in current directory
        has_hdr = any(filename.lower().endswith('.hdr') for filename in filenames)
        
        if has_hdr:
            # Get the folder name
            folder_name = os.path.basename(dirpath)
            # Create new destination path
            new_path = os.path.join(hdri_dest, folder_name)
            
            try:
                # Move the entire folder to HDRI directory
                shutil.move(dirpath, new_path)
                print(f"Moved {folder_name} to HDRI folder")
            except Exception as e:
                print(f"Error moving {folder_name}: {str(e)}")

if __name__ == "__main__":
    # Get the root path from user input
    root_path = input("Enter the root folder path: ")
    
    # Verify the path exists
    if os.path.exists(root_path):
        move_hdri_folders(root_path)
        print("Process completed!")
    else:
        print("Invalid path. Please provide a valid folder path.")