import os
import re
import shutil
import sys

# ==========================================
# CONFIGURATION
# ==========================================
# Set the target folder path here if you want to run it directly from an editor.
# You can also drag and drop a folder onto this script file.
TARGET_DIR = r"INSERT_FOLDER_PATH_HERE"

# Speed multiplier. 
# 3 = 300% speed (Keep 1 frame, skip 2).
SPEED_FACTOR = 3

# Amount of zero-padding for numbers (e.g. 4 => _0001.vdb)
# Set to 0 to disable padding (e.g. _1.vdb)
PADDING = 0

# If True, copies the FIRST frame of the original sequence to fill the remaining duration.
# If False, you might want to modify the code to copy the LAST frame.
PAD_WITH_FIRST_FRAME = True
# ==========================================

def pad_number(num, width):
    """Returns a zero-padded string of the number."""
    # If width is 0, standard integer string conversion
    return f"{num:0{width}d}"

def process_sequence(folder_path):
    print(f"Processing folder: {folder_path}")
    
    if not os.path.exists(folder_path) or not os.path.isdir(folder_path):
        print("Error: Invalid folder path.")
        return

    # 1. Gather valid VDB files
    files = []
    # Regex to capture (Prefix)_(FrameNumber).vdb
    # We use greedy matching for the prefix (.*) so it grabs everything up to the last underscore.
    pattern = re.compile(r"^(.*)_(\d+)\.vdb$", re.IGNORECASE)
    
    all_files = os.listdir(folder_path)
    ignored_count = 0
    
    # Filter and parse
    for fname in all_files:
        match = pattern.match(fname)
        if match:
            prefix, frame_str = match.groups()
            files.append({
                "name": fname,
                "path": os.path.join(folder_path, fname),
                "prefix": prefix,
                "frame": int(frame_str)
            })
        else:
            ignored_count += 1
            
    if not files:
        print("No .vdb files matching the pattern 'name_number.vdb' found.")
        return
        
    # Group by prefix in case there are multiple sequences
    prefixes = sorted(list(set(f["prefix"] for f in files)))
    
    print(f"Found {len(files)} VDB files across {len(prefixes)} sequences.")
    if ignored_count > 0:
        print(f"Ignoring {ignored_count} files (e.g. .abc, .txt, or non-matching names).")
    
    for prefix in prefixes:
        print(f"\n--- Sequence: {prefix} ---")
        
        # Sort by actual integer frame number
        seq_files = sorted([f for f in files if f["prefix"] == prefix], key=lambda x: x["frame"])
        total_frames = len(seq_files)
        print(f"  Total frames found: {total_frames}")
        
        # Determine the starting frame number (to preserve original numbering range)
        start_frame_num = seq_files[0]["frame"] if seq_files else 0
        print(f"  Sequence starts at frame: {start_frame_num}")

        # 2. Determine frames to keep and remove
        # Logic: Keep every Nth frame (where N is SPEED_FACTOR), starting from index 0.
        kept_files = []
        removed_files = []
        
        for i, f in enumerate(seq_files):
            if i % SPEED_FACTOR == 0:
                kept_files.append(f)
            else:
                removed_files.append(f)
                
        print(f"  > Keeping: {len(kept_files)} frames")
        print(f"  > Removing: {len(removed_files)} frames")
        
        # 3. Delete the skipped frames
        if removed_files:
            print("  Deleting skipped frames...")
            for f in removed_files:
                try:
                    os.remove(f["path"])
                except OSError as e:
                    print(f"    Error removing {f['name']}: {e}")
                
        # 4. Rename and renumber kept frames
        print("  Renumbering sequence...")
        
        # Check first frame source for padding later
        # The first frame of the NEW sequence is the first file in kept_files.
        # We need its path later for padding. 
        # Note: We are about to rename it, so we must track the new path.
        first_frame_new_path = None
        
        for i, f in enumerate(kept_files):
            new_frame_num = start_frame_num + i
            new_suffix = pad_number(new_frame_num, PADDING)
            new_name = f"{prefix}_{new_suffix}.vdb"
            new_path = os.path.join(folder_path, new_name)
            
            old_path = f["path"]
            
            # Store the path of the new frame 0 (or start frame) for padding use
            if i == 0:
                first_frame_new_path = new_path
            
            # Rename if name changed
            if old_path != new_path:
                try:
                    # Check for collision (rare in this logic unless files weren't deleted)
                    if os.path.exists(new_path):
                         # If target exists, it might be an issue. 
                         # But since we deleted intermediates, strictly usually safe.
                         pass
                    
                    os.rename(old_path, new_path)
                    
                    # Update local struct just in case
                    f["path"] = new_path
                    f["name"] = new_name
                    
                except OSError as e:
                    print(f"    Error renaming {f['name']} to {new_name}: {e}")
            else:
                # Need to update first_frame_new_path if we didn't rename (already named correctly)
                if i == 0:
                     first_frame_new_path = old_path

        # 5. Pad with copies of the first frame
        # We need to reach 'total_frames' duration.
        current_len = len(kept_files)
        needed_padding = total_frames - current_len
        
        if needed_padding > 0:
            print(f"  Padding end with {needed_padding} copies of the first frame...")
            
            if not first_frame_new_path or not os.path.exists(first_frame_new_path):
                print(f"    Critical Error: Source frame for padding not found: {first_frame_new_path}")
            else:
                for i in range(needed_padding):
                    # Target index starts after the last kept frame
                    # And must respect the start_frame offset
                    target_idx = start_frame_num + current_len + i
                    target_name = f"{prefix}_{pad_number(target_idx, PADDING)}.vdb"
                    target_path = os.path.join(folder_path, target_name)
                    
                    try:
                        shutil.copy2(first_frame_new_path, target_path)
                    except OSError as e:
                         print(f"    Error creating padding frame {target_name}: {e}")

    print("\nProcessing complete!")

if __name__ == "__main__":
    # Handle arguments
    folder_arg = TARGET_DIR
    
    # If script is run with an argument (e.g. drag and drop)
    if len(sys.argv) > 1:
        folder_arg = sys.argv[1]
    
    # Check if configured
    if folder_arg == "INSERT_FOLDER_PATH_HERE" or not folder_arg:
        print("\n=== VDB Sequence Retimer ===")
        print("Usage:")
        print("  1. Drag and drop a folder containing .vdb files onto this script.")
        print("  2. Or edit the 'TARGET_DIR' variable in this script.")
        print("  3. Or run via command line: python RetimeVDBSequence.py \"C:\\Path\\To\\Folder\"")
        input("\nPress Enter to exit...")
    else:
        # Require confirmation since this is destructive
        print("WARNING: This script will DELETE and RENAME files in:")
        print(f"  {folder_arg}")
        print("Expected Action: Retime 300% (Keep 1 every 3), Renumber, and Pad.")
        print("Note: Supports multiple sequences and ignores .abc files.")
        confirm = input("Type 'yes' to proceed: ")
        if confirm.lower() == "yes":
            process_sequence(folder_arg)
            input("\nDone. Press Enter to exit...")
        else:
            print("Aborted.")
