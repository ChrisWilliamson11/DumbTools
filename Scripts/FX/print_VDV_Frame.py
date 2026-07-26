import bpy
import os

# You must fetch the evaluated object from the dependency graph
# to see the accurate, post-time-stretch file assignment.
depsgraph = bpy.context.evaluated_depsgraph_get()
active_obj = bpy.context.active_object

if active_obj and active_obj.type == 'VOLUME':
    # Get the evaluated version of the volume
    eval_obj = active_obj.evaluated_get(depsgraph)
    vol_data = eval_obj.data
    
    # 1. Direct path to the current frame's file
    current_vdb_path = vol_data.grids.frame_filepath  # Direct API property
    
    if current_vdb_path:
        # Extract just the file name (e.g., "smoke_0045.vdb")
        filename = os.path.basename(current_vdb_path)
        
        print(f"Evaluated File Path: {current_vdb_path}")
        print(f"Active File: {filename}")
    else:
        print("No VDB file is currently loaded on this frame (or outside sequence range).")
else:
    print("Please select a Volume object.")
