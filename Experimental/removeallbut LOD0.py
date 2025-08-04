# Tooltip: Remove all FBX files except LOD0 and VFX files from a specified folder and subfolders
import os
import glob

def find_and_delete_fbx_files(source_folder):
    # Find all .fbx files recursively
    fbx_files = []
    for root, dirs, files in os.walk(source_folder):
        for file in files:
            if file.endswith('.fbx') and 'LOD0' not in file and 'VFX' not in file:
                full_path = os.path.join(root, file)
                fbx_files.append(full_path)
    
    # If no files found, exit
    if not fbx_files:
        print("No matching .fbx files found.")
        return
    
    # Print all files that will be deleted
    print("\nFound the following files:")
    for file in fbx_files:
        print(f"- {file}")
    
    # Ask for confirmation
    print(f"\nTotal files to delete: {len(fbx_files)}")
    confirmation = input("\nDo you want to delete these files? (yes/no): ").lower()
    
    # Delete files if confirmed
    if confirmation == 'yes':
        for file in fbx_files:
            try:
                os.remove(file)
                print(f"Deleted: {file}")
            except Exception as e:
                print(f"Error deleting {file}: {e}")
        print("\nDeletion complete!")
    else:
        print("\nOperation cancelled. No files were deleted.")

if __name__ == "__main__":
    # Get source folder from user
    source_folder = input("Enter the source folder path: ")
    
    # Check if folder exists
    if not os.path.exists(source_folder):
        print("Error: Folder does not exist!")
    else:
        find_and_delete_fbx_files(source_folder)
