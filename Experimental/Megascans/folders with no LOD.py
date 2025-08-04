import os

def find_folders_without_lod0(root_path):
    folders_without_lod0 = []
    folders_without_fbx = []
    has_subfolders = False
    has_fbx_files = False
    
    # Walk through all directories and subdirectories
    for dirpath, dirnames, filenames in os.walk(root_path):
        if dirpath != root_path:
            has_subfolders = True
            
        # Filter for FBX files
        fbx_files = [f for f in filenames if f.lower().endswith('.fbx')]
        
        if fbx_files:
            has_fbx_files = True
            # Check if any of the FBX files contain 'LOD0'
            has_lod0 = any('LOD0' in f for f in fbx_files)
            if not has_lod0:
                folders_without_lod0.append(dirpath)
        else:
            # If the directory has no FBX files at all, add it to the other list
            folders_without_fbx.append(dirpath)
    
    return folders_without_lod0, folders_without_fbx, has_subfolders, has_fbx_files

if __name__ == '__main__':
    # Replace with your root folder path
    root_folder = r'F:\Megascans\3DPlants'
    
    missing_lod_folders, empty_folders, has_subfolders, has_fbx_files = find_folders_without_lod0(root_folder)
    
    if not has_subfolders:
        print("No subfolders found in the root directory.")
    elif not has_fbx_files:
        print("No FBX files found in any directory.")
    else:
        if missing_lod_folders:
            print("\nFolders missing LOD0 FBX files:")
            for folder in missing_lod_folders:
                print(f"- {folder}")
        else:
            print("\nAll folders with FBX files contain LOD0 models.")
            
        if empty_folders:
            print("\nFolders with no FBX files:")
            for folder in empty_folders:
                print(f"- {folder}")
