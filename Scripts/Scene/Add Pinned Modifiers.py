# Tooltip: Add pinned Smooth by Angle and Weighted Normal modifiers
import bpy

def main():
    selected = bpy.context.selected_objects
    if not selected:
        print("No objects selected.")
        return

    original_active = bpy.context.view_layer.objects.active
    
    # Find existing node group to avoid repeatedly loading from asset library
    smooth_node_group = bpy.data.node_groups.get("Smooth by Angle")
    
    for obj in selected:
        if obj.type != 'MESH':
            continue
            
        bpy.context.view_layer.objects.active = obj
        
        # 1. Add Smooth by Angle
        try:
            mod_smooth = None
            if not smooth_node_group:
                # Load from Essentials library (Blender 4.1+)
                bpy.ops.object.modifier_add_node_group(
                    asset_library_type='ESSENTIALS',
                    asset_library_identifier="",
                    relative_asset_identifier="geometry_nodes\\smooth_by_angle.blend\\NodeTree\\Smooth by Angle"
                )
                if obj.modifiers:
                    mod_smooth = obj.modifiers[-1]
                    if mod_smooth.type == 'NODES':
                        smooth_node_group = mod_smooth.node_group
            else:
                # Reuse existing node group
                mod_smooth = obj.modifiers.new(name="Smooth by Angle", type='NODES')
                mod_smooth.node_group = smooth_node_group
                
            # Pin it (Blender 4.2+)
            if mod_smooth and hasattr(mod_smooth, "use_pin_to_last"):
                mod_smooth.use_pin_to_last = True
        except Exception as e:
            print(f"Failed to add Smooth by Angle to {obj.name}: {e}")
            
        # 2. Add Weighted Normal
        try:
            mod_wn = obj.modifiers.new(name="Weighted Normal", type='WEIGHTED_NORMAL')
            mod_wn.keep_sharp = True
            
            # Pin it (Blender 4.2+)
            if hasattr(mod_wn, "use_pin_to_last"):
                mod_wn.use_pin_to_last = True
        except Exception as e:
            print(f"Failed to add Weighted Normal to {obj.name}: {e}")

    # Restore active object
    if original_active and original_active.name in bpy.context.view_layer.objects:
        try:
            bpy.context.view_layer.objects.active = original_active
        except:
            pass

main()
