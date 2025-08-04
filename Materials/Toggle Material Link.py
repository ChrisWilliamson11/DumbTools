# Tooltip: Toggle material link mode between object and data link for all selected objects
import bpy

def toggle_material_link_mode():
    # Get all selected objects
    selected_objects = bpy.context.selected_objects
    
    if not selected_objects:
        print("No objects selected")
        return
    
    # Process each selected object
    for obj in selected_objects:
        # Skip objects that don't use materials
        if not hasattr(obj, 'material_slots') or len(obj.material_slots) == 0:
            continue
            
        # Process each material slot in the object
        for slot in obj.material_slots:
            # Skip empty slots
            if not slot.material:
                continue
                
            # Store the current material
            current_material = slot.material
            
            # Toggle the link mode
            if slot.link == 'OBJECT':
                # Currently linked to Object, switch to Data
                slot.link = 'DATA'
                print(f"Changed {obj.name}'s material from Object to Data link")
            elif slot.link == 'DATA':
                # Currently linked to Data, switch to Object
                slot.link = 'OBJECT'
                print(f"Changed {obj.name}'s material from Data to Object link")
            
            # Ensure the material is preserved
            slot.material = current_material
    
    print("Material link modes toggled for all selected objects")

# Run the function
toggle_material_link_mode() 