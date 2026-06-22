# Tooltip: Unsubdivides selected meshes with a Multiresolution modifier until base vertex count stops changing.

import bpy

def unsubdivide_multires():
    original_active = bpy.context.view_layer.objects.active
    selected_meshes = [obj for obj in bpy.context.selected_objects if obj.type == 'MESH']
    
    if not selected_meshes:
        print("No mesh objects selected.")
        return

    total_meshes = len(selected_meshes)
    print(f"\n--- Starting Unsubdivide on {total_meshes} meshes ---")

    for idx, obj in enumerate(selected_meshes):
        print(f"\n[{idx+1}/{total_meshes}] Processing '{obj.name}'...")
        # Check if it already has a MULTIRES modifier
        has_multires = any(m.type == 'MULTIRES' for m in obj.modifiers)
        if has_multires:
            print("  -> Skipped: Already has a MULTIRES modifier (resuming).")
            continue

        bpy.context.view_layer.objects.active = obj
        
        # Add the modifier
        mod = obj.modifiers.new(name="Multires", type='MULTIRES')
        created_mod = True
            
        unsubdivided_times = 0
        
        while True:
            # Need to update view layer to get accurate vertex count after ops
            bpy.context.view_layer.update()
            
            prev_verts = len(obj.data.vertices)
            
            try:
                # Run the unsubdivide operator for the specific modifier
                bpy.ops.object.multires_unsubdivide(modifier=mod.name)
            except Exception as e:
                # If it fails (e.g. topology doesn't allow further unsubdivision)
                print(f"  -> Stopped: {e}")
                break
                
            # Update again to check new vertex count
            bpy.context.view_layer.update()
            current_verts = len(obj.data.vertices)
            
            if current_verts == prev_verts:
                # Vertex count didn't change, meaning we've reached the base limit
                print(f"  -> Reached base limit ({current_verts} verts).")
                break
                
            unsubdivided_times += 1
            print(f"  -> Pass {unsubdivided_times}: Reduced to {current_verts} verts.")
            
        if created_mod and unsubdivided_times == 0:
            # If we created a modifier but didn't manage to unsubdivide at all, remove it to clean up
            obj.modifiers.remove(mod)
            print(f"  -> Skipped (could not be unsubdivided).")
        else:
            print(f"  -> Finished: Unsubdivided {unsubdivided_times} times.")
            
        # Save after processing each object
        if bpy.data.filepath:
            try:
                bpy.ops.wm.save_mainfile()
                print("  -> Saved .blend file.")
            except Exception as e:
                print(f"  -> Failed to save file: {e}")
            
    # Restore the originally active object
    if original_active:
        bpy.context.view_layer.objects.active = original_active

unsubdivide_multires()
