import os

import json



def get_asset_name_from_json(json_path):
    """Extract asset name from JSON file."""
    try:
        with open(json_path, 'r') as f:
            data = json.load(f)
            return data['name']
    except Exception as e:
        print(f"Error reading JSON {json_path}: {e}")
        return None

def main():
    root_folder = "F:/Megascans/3D"
    print(f"Checking Megascans library at: {root_folder}")
    missing_objs = []
    
    for dirpath, dirnames, filenames in os.walk(root_folder):
        # Check if folder has any JSON files
        json_files = [f for f in filenames if f.endswith('.json')]
        if not json_files:
            continue
            
        # Check if folder has any OBJ files
        has_obj = any(f.lower().endswith('.obj') for f in filenames)
        
        if not has_obj:
            # Get asset name from JSON
            for json_file in json_files:
                json_path = os.path.join(dirpath, json_file)
                asset_name = get_asset_name_from_json(json_path)
                if asset_name:
                    missing_objs.append(asset_name)
    
    # Print results
    if missing_objs:
        print("\nAssets missing OBJ files:")
        for name in sorted(missing_objs):
            print(f"- {name}")
        print(f"\nTotal missing: {len(missing_objs)}")
    else:
        print("\nNo assets missing OBJ files found.")

main()