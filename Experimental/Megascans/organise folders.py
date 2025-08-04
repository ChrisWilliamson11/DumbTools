import os
from pathlib import Path
import shutil

def load_asset_ids(file_path):
    """Load asset IDs from file into a set."""
    with open(file_path, 'r') as f:
        return {line.strip() for line in f if line.strip()}

def find_asset_id(folder_name, asset_ids):
    """Find the asset ID in the folder name."""
    parts = folder_name.split('_')
    for part in parts:
        if part.lower() in {aid.lower() for aid in asset_ids}:
            return part
    return None

def analyze_folder_structure(root_path, asset_ids):
    """Analyze the folder structure and return planned moves."""
    planned_moves = []
    
    # Walk through all subdirectories
    for dirpath, dirnames, filenames in os.walk(root_path):
        for dirname in dirnames:
            current_path = Path(dirpath) / dirname
            asset_id = find_asset_id(dirname, asset_ids)
            
            if asset_id:
                # Split the folder name into parts
                parts = dirname.split('_')
                asset_index = next(i for i, part in enumerate(parts) if part.lower() == asset_id.lower())
                
                # Get the categorization parts (everything before the asset ID)
                categories = [
                    p.lower() for p in parts[:asset_index] 
                    if p.lower() not in [part.lower() for part in Path(root_path).parts]
                ]
                
                if categories:
                    # Start from root path if current parent isn't in folder name (case-insensitive)
                    folder_parts_lower = [p.lower() for p in parts]
                    if current_path.parent.name.lower() not in folder_parts_lower:
                        new_parent = Path(root_path)
                    else:
                        new_parent = current_path.parent
                        
                    for category in categories:
                        if category.lower() != new_parent.name.lower():  # Only add if not already matching parent
                            new_parent = new_parent / category
                    new_path = new_parent / dirname
                    
                    if new_path != current_path:
                        planned_moves.append((current_path, new_path))
    
    return planned_moves

def preview_changes(moves):
    """Preview the planned folder moves."""
    if not moves:
        print("No changes needed - folders are already organized.")
        return
    
    print("\nPlanned folder moves:")
    print("-" * 50)
    for old_path, new_path in moves:
        print(f"Move: {old_path}")
        print(f"  To: {new_path}")
        print()

def execute_moves(moves):
    """Execute the planned folder moves."""
    for old_path, new_path in moves:
        # Create parent directories if they don't exist
        new_path.parent.mkdir(parents=True, exist_ok=True)
        # Move the folder
        shutil.move(str(old_path), str(new_path))

def main():
    # Configure paths
    root_path = Path(r"F:\Megascans\3D\Antique")  # Adjust this path as needed
    asset_ids_file = Path("megascans_asset_ids.txt")
    
    # Load asset IDs
    asset_ids = load_asset_ids(asset_ids_file)
    
    # Analyze and get planned moves
    planned_moves = analyze_folder_structure(root_path, asset_ids)
    
    # Preview changes
    preview_changes(planned_moves)
    
    # Ask for confirmation before executing
    if planned_moves:
        response = input("\nDo you want to proceed with these moves? (yes/no): ").lower()
        if response == 'yes':
            execute_moves(planned_moves)
            print("\nFolder reorganization completed successfully!")
        else:
            print("\nOperation cancelled.")

if __name__ == "__main__":
    main()
