#Tooltip: Renames all your driver variables to that of the shape key driving them

import bpy

# Ensure an armature is selected
if bpy.context.object.type == 'ARMATURE':
    armature = bpy.context.object
    
    # Check if the armature has animation data and drivers
    if armature.animation_data and armature.animation_data.drivers:
        for fcurve in armature.animation_data.drivers:
            # For each driver, iterate through its variables
            for var in fcurve.driver.variables:
                # Check if the variable is a 'SINGLE_PROP'
                if var.type == 'SINGLE_PROP':
                    for target in var.targets:
                        # Extract shape key name from the data path
                        if 'key_blocks' in target.data_path:
                            shape_key_name = target.data_path.split('"')[1]
                            old_var_name = var.name
                            var.name = shape_key_name  # Rename variable to shape key name
                            
                            # Update the driver's expression
                            # Replace old variable name with the new shape key name in the expression
                            if old_var_name in fcurve.driver.expression:
                                new_expression = fcurve.driver.expression.replace(old_var_name, shape_key_name)
                                fcurve.driver.expression = new_expression

    print("Driver variables and expressions updated successfully.")
else:
    print("Please select an armature.")