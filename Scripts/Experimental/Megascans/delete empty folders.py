import os
import sys

def is_folder_empty(folder_path):
    # Check if a folder is empty (no files or only empty subfolders)
    for root, dirs, files in os.walk(folder_path):
        if files:
            return False
        for dir in dirs:
            if not is_folder_empty(os.path.join(root, dir)):
                return False
    return True

def find_empty_folders(start_path='.'):
    empty_folders = []
    
    # Walk through directory tree
    for root, dirs, files in os.walk(start_path):
        for dir_name in dirs:
            full_path = os.path.join(root, dir_name)
            if is_folder_empty(full_path):
                empty_folders.append(full_path)
    
    return empty_folders

def main():
    # Find empty folders
    empty_folders = find_empty_folders()
    
    if not empty_folders:
        print("No empty folders found.")
        return
    
    # Display empty folders
    print("\nFound the following empty folders:")
    for folder in empty_folders:
        print(f"- {folder}")
    
    # Ask for confirmation
    response = input("\nWould you like to remove these folders? (yes/no): ").lower()
    
    if response == 'yes':
        # Remove empty folders
        for folder in empty_folders:
            try:
                os.rmdir(folder)
                print(f"Removed: {folder}")
            except OSError as e:
                print(f"Error removing {folder}: {e}")
        print("\nDone removing empty folders.")
    else:
        print("\nOperation cancelled.")

if __name__ == "__main__":
    main()
