# Tooltip: Organize material files by moving folders containing material textures to a dedicated Materials directory
import os
import shutil
from pathlib import Path

def move_polyhaven_props(root_path):
    # Create Polyhaven Props destination folder if it doesn't exist
    props_dest = os.path.join(root_path, 'Polyhaven Props')
    os.makedirs(props_dest, exist_ok=True)
    
    # Dictionary to store counts of each type
    type_counts = {}
    
    # Walk through all subdirectories
    for dirpath, dirnames, filenames in os.walk(root_path):
        # Skip the destination folder itself
        if dirpath == props_dest:
            continue
            
        # Check if any json files exist in current directory
        json_files = [f for f in filenames if f.lower().endswith('.json')]
        
        for json_file in json_files:
            try:
                with open(os.path.join(dirpath, json_file), 'r') as f:
                    import json
                    data = json.load(f)
                    
                    # Get the type and increment count
                    file_type = data.get('type', 'unknown')
                    type_counts[file_type] = type_counts.get(file_type, 0) + 1
                    
                    # Check if 'Type' is '2'
                    if file_type == '2':
                        # Get the folder name
                        folder_name = os.path.basename(dirpath)
                        # Create new destination path
                        new_path = os.path.join(props_dest, folder_name)
                        
                        try:
                            # Copy the entire folder to Polyhaven Props directory
                            shutil.copytree(dirpath, new_path)
                            print(f"Copied {folder_name} to Polyhaven Props folder")
                        except Exception as e:
                            print(f"Error copying {folder_name}: {str(e)}")
                        
                        # Break after finding the first matching json file
                        break
                        
            except Exception as e:
                print(f"Error reading json file {json_file}: {str(e)}")
    
    # Print type counts at the end
    print("\nType counts summary:")
    for type_key, count in type_counts.items():
        print(f"Type {type_key}: {count}")

if __name__ == "__main__":
    # Get the root path from user input
    root_path = input("Enter the root folder path: ")
    
    # Verify the path exists
    if os.path.exists(root_path):
        move_polyhaven_props(root_path)
        print("Process completed!")
    else:
        print("Invalid path. Please provide a valid folder path.")