# Tooltip: Copy drivers from selected mesh shape keys to matching shape keys on active mesh

import bpy

def main():
    # Get selected objects
    selected_objects = bpy.context.selected_objects
    active_object = bpy.context.active_object
    
    # Validation
    if len(selected_objects) < 2:
        print("Error: Please select at least 2 objects (source mesh + active target mesh)")
        return
    
    if not active_object:
        print("Error: No active object found")
        return
    
    if active_object.type != 'MESH':
        print("Error: Active object must be a mesh")
        return
    
    # Find the source mesh (selected but not active)
    source_mesh = None
    for obj in selected_objects:
        if obj != active_object and obj.type == 'MESH':
            source_mesh = obj
            break
    
    if not source_mesh:
        print("Error: Could not find a selected mesh object (other than active)")
        return
    
    # Check if both meshes have shape keys
    if not source_mesh.data.shape_keys:
        print(f"Error: Source mesh '{source_mesh.name}' has no shape keys")
        return
    
    if not active_object.data.shape_keys:
        print(f"Error: Active mesh '{active_object.name}' has no shape keys")
        return
    
    print(f"\n=== Copying Shape Key Drivers ===")
    print(f"Source mesh: {source_mesh.name}")
    print(f"Target mesh: {active_object.name}")
    
    # Get shape keys
    source_shape_keys = source_mesh.data.shape_keys.key_blocks
    target_shape_keys = active_object.data.shape_keys.key_blocks
    
    # Create a dictionary of target shape keys for quick lookup
    target_keys_dict = {key.name: key for key in target_shape_keys}
    
    drivers_copied = 0
    drivers_skipped = 0
    matches_found = 0
    
    # Process each source shape key
    for source_key in source_shape_keys:
        # Skip the Basis key
        if source_key.name == "Basis":
            continue

        print(f"Processing: {source_key.name}")

        # Check if target has matching shape key
        if source_key.name in target_keys_dict:
            matches_found += 1
            target_key = target_keys_dict[source_key.name]
            print(f"  Found match in target")

            # Check if source shape key has a driver
            source_data_path = f'key_blocks["{source_key.name}"].value'
            source_driver = source_mesh.data.shape_keys.animation_data
            
            if source_driver and source_driver.drivers:
                # Look for driver on this shape key
                source_fcurve = None
                for fcurve in source_driver.drivers:
                    if fcurve.data_path == source_data_path:
                        source_fcurve = fcurve
                        break
                
                if source_fcurve:
                    print(f"  Found driver, copying...")
                    try:
                        # Copy driver to target
                        target_data_path = f'key_blocks["{target_key.name}"].value'

                        # Ensure target has animation data
                        if not active_object.data.shape_keys.animation_data:
                            active_object.data.shape_keys.animation_data_create()

                        # Remove existing driver if present
                        try:
                            active_object.data.shape_keys.driver_remove(target_data_path)
                        except:
                            pass  # No existing driver to remove

                        # Add new driver
                        target_fcurve = active_object.data.shape_keys.driver_add(target_data_path)

                        # Copy the entire F-curve (keyframes, interpolation, etc.)
                        target_fcurve.keyframe_points.clear()
                        for source_keyframe in source_fcurve.keyframe_points:
                            target_keyframe = target_fcurve.keyframe_points.insert(
                                source_keyframe.co[0], source_keyframe.co[1]
                            )
                            target_keyframe.interpolation = source_keyframe.interpolation
                            target_keyframe.handle_left_type = source_keyframe.handle_left_type
                            target_keyframe.handle_right_type = source_keyframe.handle_right_type
                            target_keyframe.handle_left = source_keyframe.handle_left
                            target_keyframe.handle_right = source_keyframe.handle_right

                        # Copy F-curve properties
                        target_fcurve.extrapolation = source_fcurve.extrapolation
                        target_fcurve.color_mode = source_fcurve.color_mode
                        target_fcurve.color = source_fcurve.color
                        target_fcurve.auto_smoothing = source_fcurve.auto_smoothing

                        # Copy driver properties
                        target_driver = target_fcurve.driver
                        source_driver_obj = source_fcurve.driver

                        # Copy basic driver properties
                        target_driver.type = source_driver_obj.type
                        target_driver.expression = source_driver_obj.expression
                        if hasattr(source_driver_obj, 'use_self'):
                            target_driver.use_self = source_driver_obj.use_self
                        if hasattr(source_driver_obj, 'show_debug_info'):
                            target_driver.show_debug_info = source_driver_obj.show_debug_info

                        # Clear existing variables (compatible way)
                        while len(target_driver.variables) > 0:
                            target_driver.variables.remove(target_driver.variables[0])

                        # Copy variables
                        for source_var in source_driver_obj.variables:
                            target_var = target_driver.variables.new()
                            target_var.name = source_var.name
                            target_var.type = source_var.type

                            # Copy targets
                            for i, source_target in enumerate(source_var.targets):
                                if i < len(target_var.targets):
                                    target_target = target_var.targets[i]
                                    try:
                                        target_target.id = source_target.id
                                        target_target.data_path = source_target.data_path
                                        if hasattr(source_target, 'bone_target'):
                                            target_target.bone_target = source_target.bone_target
                                        if hasattr(source_target, 'transform_type'):
                                            target_target.transform_type = source_target.transform_type
                                        if hasattr(source_target, 'transform_space'):
                                            target_target.transform_space = source_target.transform_space
                                    except Exception as e:
                                        print(f"  Warning: Could not copy target properties for {source_var.name}: {e}")

                        # Copy F-curve modifiers
                        # Clear existing modifiers (compatible way)
                        while len(target_fcurve.modifiers) > 0:
                            target_fcurve.modifiers.remove(target_fcurve.modifiers[0])
                        for source_mod in source_fcurve.modifiers:
                            # Read all source modifier properties first
                            mod_type = source_mod.type
                            mod_active = source_mod.active
                            mod_mute = source_mod.mute
                            mod_show_expanded = source_mod.show_expanded
                            mod_frame_start = source_mod.frame_start
                            mod_frame_end = source_mod.frame_end
                            mod_blend_in = source_mod.blend_in
                            mod_blend_out = source_mod.blend_out
                            mod_influence = source_mod.influence

                            # Initialize type-specific variables
                            gen_mode = gen_poly_order = gen_use_additive = gen_use_restricted_range = None
                            gen_coefficients = []
                            fn_function_type = fn_use_additive = fn_amplitude = None
                            fn_phase_multiplier = fn_phase_offset = fn_value_offset = None

                            # Read type-specific properties
                            if source_mod.type == 'GENERATOR':
                                gen_mode = source_mod.mode
                                gen_poly_order = source_mod.poly_order
                                gen_use_additive = source_mod.use_additive
                                gen_use_restricted_range = source_mod.use_restricted_range
                                gen_coefficients = [coeff for coeff in source_mod.coefficients]
                                print(f"    Reading {len(gen_coefficients)} coefficients: {gen_coefficients}")
                            elif source_mod.type == 'FNGENERATOR':
                                fn_function_type = source_mod.function_type
                                fn_use_additive = source_mod.use_additive
                                fn_amplitude = source_mod.amplitude
                                fn_phase_multiplier = source_mod.phase_multiplier
                                fn_phase_offset = source_mod.phase_offset
                                fn_value_offset = source_mod.value_offset

                            # Create new modifier
                            target_mod = target_fcurve.modifiers.new(mod_type)

                            # Set common properties
                            target_mod.active = mod_active
                            target_mod.mute = mod_mute
                            target_mod.show_expanded = mod_show_expanded
                            target_mod.frame_start = mod_frame_start
                            target_mod.frame_end = mod_frame_end
                            target_mod.blend_in = mod_blend_in
                            target_mod.blend_out = mod_blend_out
                            target_mod.influence = mod_influence

                            # Set type-specific properties
                            if source_mod.type == 'GENERATOR':
                                target_mod.mode = gen_mode
                                target_mod.poly_order = gen_poly_order
                                target_mod.use_additive = gen_use_additive
                                target_mod.use_restricted_range = gen_use_restricted_range

                                # Now set coefficients after all other properties are set
                                for i, coeff in enumerate(gen_coefficients):
                                    if i < len(target_mod.coefficients):
                                        target_mod.coefficients[i] = coeff
                                print(f"    Set {len(gen_coefficients)} coefficients on target modifier")
                            elif source_mod.type == 'FNGENERATOR':
                                target_mod.function_type = fn_function_type
                                target_mod.use_additive = fn_use_additive
                                target_mod.amplitude = fn_amplitude
                                target_mod.phase_multiplier = fn_phase_multiplier
                                target_mod.phase_offset = fn_phase_offset
                                target_mod.value_offset = fn_value_offset

                        drivers_copied += 1
                        print(f"✓ Copied driver: {source_key.name} (with {len(source_fcurve.modifiers)} modifiers)")
                    except Exception as e:
                        print(f"✗ Error copying driver for {source_key.name}: {e}")
                        drivers_skipped += 1
                else:
                    drivers_skipped += 1
                    print(f"- No driver found: {source_key.name}")
            else:
                drivers_skipped += 1
                print(f"- No driver found: {source_key.name}")
        else:
            print(f"✗ No matching shape key: {source_key.name}")

    # Update dependency graph to resolve driver issues
    if drivers_copied > 0:
        try:
            bpy.context.view_layer.update()
            bpy.context.evaluated_depsgraph_get().update()
        except:
            pass  # Ignore dependency graph update errors

    # Summary
    print(f"\n=== Summary ===")
    print(f"Shape key matches found: {matches_found}")
    print(f"Drivers copied: {drivers_copied}")
    print(f"Shape keys without drivers: {drivers_skipped}")

    if drivers_copied > 0:
        print(f"\n✓ Successfully copied {drivers_copied} drivers!")
        print("Note: Dependency graph warnings are normal and can be ignored.")
    else:
        print("\n⚠ No drivers were copied.")

main()
