# Tooltip: Delete bones from selected armatures that don't exist in the active armature

import bpy

def delete_bones_not_in_active():
    # Get the active object
    active_obj = bpy.context.active_object
    
    # Ensure the active object is an armature
    if not active_obj or active_obj.type != 'ARMATURE':
        print("Error: Active object must be an armature.")
        return
    
    # Get all bone names from the active armature
    active_bone_names = {bone.name for bone in active_obj.data.bones}
    print(f"Active armature '{active_obj.name}' has {len(active_bone_names)} bones.")
    
    # Get selected objects (excluding the active one)
    selected_armatures = [obj for obj in bpy.context.selected_objects 
                         if obj.type == 'ARMATURE' and obj != active_obj]
    
    if not selected_armatures:
        print("Error: No other armatures selected. Please select one or more armatures in addition to the active one.")
        return
    
    print(f"Found {len(selected_armatures)} selected armature(s) to process.")
    
    # Store current mode and active object
    original_mode = bpy.context.mode
    original_active = bpy.context.active_object
    
    total_bones_deleted = 0
    
    try:
        # Process each selected armature
        for armature in selected_armatures:
            print(f"\nProcessing armature: '{armature.name}'")
            
            # Set this armature as active and enter edit mode
            bpy.context.view_layer.objects.active = armature
            bpy.ops.object.mode_set(mode='EDIT')
            
            # Get bones that exist in this armature but not in the active armature
            bones_to_delete = []
            for bone in armature.data.edit_bones:
                if bone.name not in active_bone_names:
                    bones_to_delete.append(bone.name)
            
            # Delete the bones
            bones_deleted_count = 0
            for bone_name in bones_to_delete:
                bone = armature.data.edit_bones.get(bone_name)
                if bone:
                    armature.data.edit_bones.remove(bone)
                    bones_deleted_count += 1
                    print(f"  Deleted bone: '{bone_name}'")
            
            total_bones_deleted += bones_deleted_count
            print(f"  Deleted {bones_deleted_count} bones from '{armature.name}'")
            
            # Return to object mode
            bpy.ops.object.mode_set(mode='OBJECT')
    
    except Exception as e:
        print(f"Error occurred: {e}")
    
    finally:
        # Restore original active object and mode
        try:
            bpy.context.view_layer.objects.active = original_active
            if original_mode == 'EDIT_ARMATURE':
                bpy.ops.object.mode_set(mode='EDIT')
            elif original_mode == 'POSE':
                bpy.ops.object.mode_set(mode='POSE')
            else:
                bpy.ops.object.mode_set(mode='OBJECT')
        except:
            # If we can't restore the mode, at least go to object mode
            bpy.ops.object.mode_set(mode='OBJECT')
    
    print(f"\nCompleted! Total bones deleted: {total_bones_deleted}")

# Call the function
delete_bones_not_in_active()
