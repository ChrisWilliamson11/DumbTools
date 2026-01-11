# Tooltip: Open dialog to copy specific shape key drivers from active mesh to selected meshes

import bpy

# Property group for the items in the list
class ShapeKeyItem(bpy.types.PropertyGroup):
    name: bpy.props.StringProperty(name="Name")
    selected: bpy.props.BoolProperty(name="Selected", default=True)

class DUMBTOOLS_OT_CopyShapeKeyDriversToSelected(bpy.types.Operator):
    bl_idname = "dumbtools.copy_shapekey_drivers_to_selected"
    bl_label = "Copy Shape Key Drivers"
    bl_options = {'REGISTER', 'UNDO'}
    
    # Collection to hold the list of shape keys
    shape_key_items: bpy.props.CollectionProperty(type=ShapeKeyItem)
    
    def invoke(self, context, event):
        active_object = context.active_object
        selected_objects = context.selected_objects
        
        # Validation
        if not active_object or active_object.type != 'MESH':
            self.report({'ERROR'}, "Active object must be a mesh")
            return {'CANCELLED'}
            
        if not active_object.data.shape_keys:
            self.report({'ERROR'}, "Active object has no shape keys")
            return {'CANCELLED'}
            
        if len(selected_objects) < 2:
             self.report({'ERROR'}, "Please select at least one target object along with the source")
             return {'CANCELLED'}

        # Populate the list
        self.shape_key_items.clear()
        for key_block in active_object.data.shape_keys.key_blocks:
            if key_block.name == "Basis":
                continue
            item = self.shape_key_items.add()
            item.name = key_block.name
            item.selected = True # Default to selected
            
        return context.window_manager.invoke_props_dialog(self)
        
    def draw(self, context):
        layout = self.layout
        layout.label(text="Select drivers to copy:")
        
        # Draw the list
        # Since we can't easily draw a scrolling list in a simple operator dialog without a custom UI list,
        # we'll just stack checkboxes. If there are too many, it might go off screen, 
        # but standard UI lists need a panel or a more complex setup. 
        # For a simple invoke dialog, a column of checkboxes is standard.
        box = layout.box()
        for item in self.shape_key_items:
            row = box.row()
            row.prop(item, "selected", text=item.name)

    def execute(self, context):
        active_object = context.active_object
        selected_objects = context.selected_objects
        
        source_mesh = active_object
        target_objects = [obj for obj in selected_objects if obj != source_mesh and obj.type == 'MESH']
        
        if not target_objects:
             self.report({'ERROR'}, "No target mesh objects found")
             return {'CANCELLED'}
        
        drivers_copied = 0
        
        # Filter selected keys
        keys_to_copy = {item.name for item in self.shape_key_items if item.selected}
        
        for target_obj in target_objects:
            print(f"Processing target: {target_obj.name}")
            
            if not target_obj.data.shape_keys:
                 print(f"Skipping {target_obj.name}: No shape keys")
                 continue
                 
            target_keys_dict = {key.name: key for key in target_obj.data.shape_keys.key_blocks}

            for source_key_name in keys_to_copy:
                if source_key_name not in target_keys_dict:
                    print(f"  Skipping {source_key_name}: Not found on target")
                    continue
                    
                print(f"  Copying driver for {source_key_name}")
                
                # Source driver logic
                source_data_path = f'key_blocks["{source_key_name}"].value'
                if not source_mesh.data.shape_keys.animation_data or not source_mesh.data.shape_keys.animation_data.drivers:
                     print(f"    No animation data on source")
                     continue
                     
                source_fcurve = None
                for fcurve in source_mesh.data.shape_keys.animation_data.drivers:
                    if fcurve.data_path == source_data_path:
                        source_fcurve = fcurve
                        break
                        
                if not source_fcurve:
                    print(f"    No driver found on source for {source_key_name}")
                    continue
                    
                # Copy logic (adapted from existing script)
                target_data_path = f'key_blocks["{source_key_name}"].value'
                
                if not target_obj.data.shape_keys.animation_data:
                    target_obj.data.shape_keys.animation_data_create()
                    
                # Remove existing
                try:
                    target_obj.data.shape_keys.driver_remove(target_data_path)
                except:
                    pass
                    
                target_fcurve = target_obj.data.shape_keys.driver_add(target_data_path)
                
                # Copy F-Curve
                target_fcurve.keyframe_points.clear()
                for kf in source_fcurve.keyframe_points:
                    nkf = target_fcurve.keyframe_points.insert(kf.co[0], kf.co[1])
                    nkf.interpolation = kf.interpolation
                    nkf.handle_left = kf.handle_left
                    nkf.handle_right = kf.handle_right
                    nkf.handle_left_type = kf.handle_left_type
                    nkf.handle_right_type = kf.handle_right_type
                
                target_fcurve.extrapolation = source_fcurve.extrapolation
                target_fcurve.color_mode = source_fcurve.color_mode
                target_fcurve.color = source_fcurve.color
                target_fcurve.auto_smoothing = source_fcurve.auto_smoothing
                
                # Driver settings
                t_drv = target_fcurve.driver
                s_drv = source_fcurve.driver
                
                t_drv.type = s_drv.type
                t_drv.expression = s_drv.expression
                if hasattr(s_drv, 'use_self'): t_drv.use_self = s_drv.use_self
                
                # Variables
                for v in t_drv.variables: t_drv.variables.remove(v)
                
                for s_var in s_drv.variables:
                    t_var = t_drv.variables.new()
                    t_var.name = s_var.name
                    t_var.type = s_var.type
                    
                    for i, s_target in enumerate(s_var.targets):
                        if i < len(t_var.targets):
                            t_target = t_var.targets[i]
                            t_target.id = s_target.id
                            t_target.data_path = s_target.data_path
                            if hasattr(s_target, 'bone_target'): t_target.bone_target = s_target.bone_target
                            if hasattr(s_target, 'transform_type'): t_target.transform_type = s_target.transform_type
                            if hasattr(s_target, 'transform_space'): t_target.transform_space = s_target.transform_space
                
                # Modifiers
                for m in target_fcurve.modifiers: target_fcurve.modifiers.remove(m)
                
                for s_mod in source_fcurve.modifiers:
                    t_mod = target_fcurve.modifiers.new(s_mod.type)
                    
                    # Common props
                    for prop in ['active', 'mute', 'show_expanded', 'frame_start', 'frame_end', 'blend_in', 'blend_out', 'influence']:
                         if hasattr(s_mod, prop): setattr(t_mod, prop, getattr(s_mod, prop))
                         
                    # Generator
                    if s_mod.type == 'GENERATOR':
                        t_mod.mode = s_mod.mode
                        t_mod.poly_order = s_mod.poly_order
                        t_mod.use_additive = s_mod.use_additive
                        t_mod.use_restricted_range = s_mod.use_restricted_range
                        for i, c in enumerate(s_mod.coefficients):
                            if i < len(t_mod.coefficients): t_mod.coefficients[i] = c
                            
                    # FNGENERATOR (Built-in Function)
                    elif s_mod.type == 'FNGENERATOR':
                         for prop in ['function_type', 'use_additive', 'amplitude', 'phase_multiplier', 'phase_offset', 'value_offset']:
                             if hasattr(s_mod, prop): setattr(t_mod, prop, getattr(s_mod, prop))
                
                drivers_copied += 1

        self.report({'INFO'}, f"Copied {drivers_copied} drivers")
        return {'FINISHED'}

def register():
    try:
        bpy.utils.register_class(ShapeKeyItem)
        bpy.utils.register_class(DUMBTOOLS_OT_CopyShapeKeyDriversToSelected)
    except ValueError:
        pass # Already registered

def unregister():
    try:
        bpy.utils.unregister_class(DUMBTOOLS_OT_CopyShapeKeyDriversToSelected)
        bpy.utils.unregister_class(ShapeKeyItem)
    except ValueError:
        pass


register()
# Invoke the operator immediately
bpy.ops.dumbtools.copy_shapekey_drivers_to_selected('INVOKE_DEFAULT')
