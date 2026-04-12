import bpy

def get_vdb_start_frame(vdb):
    """Attempt to get the start frame from the VDB sequence data."""
    if vdb.data and hasattr(vdb.data, "frame_start"):
        return vdb.data.frame_start
    return None

def main():
    print("--- Starting Parent Muzzleflashes Script ---")
    target_obj = bpy.context.active_object
    
    if not target_obj:
        print("No active object selected for parenting.")
        return
        
    gen_col = bpy.data.collections.get("Muzzleflashes_Generated")
    if not gen_col:
        print("Collection 'Muzzleflashes_Generated' not found.")
        return

    original_frame = bpy.context.scene.frame_current
    parented_count = 0

    for empty in gen_col.objects:
        if empty.type == 'EMPTY':
            # Skip if it is already parented to the correct target
            if empty.parent == target_obj:
                continue

            # Check for a VDB (Volume) child
            vdb_child = None
            for child in empty.children:
                if child.type == 'VOLUME':
                    vdb_child = child
                    break
            
            if vdb_child:
                start_frame = get_vdb_start_frame(vdb_child)
                
                if start_frame is None:
                    print(f"Could not determine start frame from {vdb_child.name}")
                    continue
                
                # 1. Set the scene to the exact frame the VDB starts
                bpy.context.scene.frame_set(int(start_frame))
                
                # Force view layer update so matrix_world reflects the new frame for both target and empty
                bpy.context.view_layer.update()
                
                # 2. Parent with "Keep Transform"
                # Store the world transform to ensure nothing shifts
                world_mat = empty.matrix_world.copy()
                
                empty.parent = target_obj
                empty.matrix_parent_inverse = target_obj.matrix_world.inverted()
                empty.matrix_world = world_mat
                
                parented_count += 1
                print(f"Parented '{empty.name}' to '{target_obj.name}' at frame {start_frame}")

    # Restore the timeline to where it was
    bpy.context.scene.frame_set(original_frame)
    bpy.context.view_layer.update()
    
    print(f"--- Parent Muzzleflashes Completed. Parented {parented_count} objects to '{target_obj.name}' ---")

main()
