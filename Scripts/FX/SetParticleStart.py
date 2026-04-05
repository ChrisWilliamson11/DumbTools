# Tooltip: Set particle system start frame to current, end to next frame
import bpy

def main():
    current_frame = bpy.context.scene.frame_current
    selected_objects = bpy.context.selected_objects
    
    if not selected_objects:
        print("No objects selected.")
        return
        
    updated_any = False
    
    for obj in selected_objects:
        if not obj.particle_systems:
            continue
            
        for psys in obj.particle_systems:
            if psys.settings:
                psys.settings.frame_start = current_frame
                psys.settings.frame_end = current_frame + 1
                updated_any = True
                
        print(f"Updated particle systems for {obj.name}: start={current_frame}, end={current_frame + 1}")
        
    if not updated_any:
        print("No particle systems found on selected objects.")

main()
