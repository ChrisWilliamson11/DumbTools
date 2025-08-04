import os
import zipfile
from shutil import copy2

# Define the folder path
source_folder = 'DumbTools'
zip_name = 'DumbTools.zip'
destination_path = os.path.join('..', '..', '..')

# Full path of the zip to be created
zip_file_path = os.path.join(zip_name)

# Full destination path including the zip file name
destination_file_path = os.path.join(destination_path, zip_name)

# Ensure the source folder exists
if not os.path.exists(source_folder):
    raise FileNotFoundError(f"The folder {source_folder} does not exist.")

# Create a ZIP archive of the DumbTools folder
with zipfile.ZipFile(zip_file_path, 'w', zipfile.ZIP_DEFLATED) as zipf:
    for root, dirs, files in os.walk(source_folder):
        for file in files:
            file_path = os.path.join(root, file)
            zipf.write(file_path, os.path.relpath(file_path, os.path.join(source_folder, '..')))

# Copy the ZIP file to the destination directory
copy2(zip_file_path, destination_file_path)
print(f"File {zip_file_path} copied to {destination_file_path}")

# Delete the ZIP file after copying
os.remove(zip_file_path)
print(f"File {zip_file_path} has been deleted after copying.")
