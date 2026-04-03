# Tooltip: Store and load shape key drivers as JSON files with UI panel

import bpy
import json
import os
from bpy.props import StringProperty
from bpy.types import Panel, Operator
from bpy_extras.io_utils import ExportHelper, ImportHelper

class SHAPEKEY_OT_save_drivers(Operator, ExportHelper):
    """Save shape key drivers to JSON file"""
    bl_idname = "shapekey.save_drivers"
    bl_label = "Save Shape Key Drivers"
    bl_description = "Save shape key drivers from selected object to JSON file"
    
    filename_ext = ".json"
    filter_glob: StringProperty(default="*.json", options={'HIDDEN'})
    
    def execute(self, context):
        selected_objects = [obj for obj in context.selected_objects if obj.type == 'MESH' and obj.data.shape_keys]

        if not selected_objects:
            self.report({'ERROR'}, "Please select at least one mesh object with shape keys")
            return {'CANCELLED'}

        try:
            drivers_data = {
                'objects': {},
                'export_info': {
                    'total_objects': len(selected_objects),
                    'object_names': [obj.name for obj in selected_objects]
                }
            }

            total_drivers = 0
            for obj in selected_objects:
                obj_data = self.extract_drivers_data(obj)
                drivers_data['objects'][obj.name] = obj_data
                total_drivers += len(obj_data['shape_keys'])

            with open(self.filepath, 'w') as f:
                json.dump(drivers_data, f, indent=2)

            self.report({'INFO'}, f"Saved {total_drivers} shape key drivers from {len(selected_objects)} objects to {os.path.basename(self.filepath)}")
            return {'FINISHED'}

        except Exception as e:
            self.report({'ERROR'}, f"Error saving drivers: {str(e)}")
            return {'CANCELLED'}
    
    def extract_drivers_data(self, obj):
        """Extract all driver data from shape keys"""
        data = {
            'object_name': obj.name,
            'shape_keys': {}
        }
        
        shape_keys = obj.data.shape_keys.key_blocks
        animation_data = obj.data.shape_keys.animation_data
        
        if not animation_data or not animation_data.drivers:
            return data
        
        for shape_key in shape_keys:
            if shape_key.name == "Basis":
                continue
                
            data_path = f'key_blocks["{shape_key.name}"].value'
            
            # Find F-curve for this shape key
            fcurve = None
            for fc in animation_data.drivers:
                if fc.data_path == data_path:
                    fcurve = fc
                    break
            
            if fcurve:
                shape_key_data = self.extract_fcurve_data(fcurve)
                data['shape_keys'][shape_key.name] = shape_key_data
        
        return data
    
    def extract_fcurve_data(self, fcurve):
        """Extract all data from an F-curve"""
        data = {
            'keyframes': [],
            'fcurve_properties': {},
            'driver': {},
            'modifiers': []
        }
        
        # Extract keyframes
        for kf in fcurve.keyframe_points:
            keyframe_data = {
                'co': list(kf.co),
                'interpolation': kf.interpolation,
                'handle_left_type': kf.handle_left_type,
                'handle_right_type': kf.handle_right_type,
                'handle_left': list(kf.handle_left),
                'handle_right': list(kf.handle_right)
            }
            data['keyframes'].append(keyframe_data)
        
        # Extract F-curve properties
        data['fcurve_properties'] = {
            'extrapolation': fcurve.extrapolation,
            'color_mode': fcurve.color_mode,
            'color': list(fcurve.color),
            'auto_smoothing': fcurve.auto_smoothing
        }
        
        # Extract driver data
        driver = fcurve.driver
        data['driver'] = {
            'type': driver.type,
            'expression': driver.expression,
            'use_self': getattr(driver, 'use_self', False),
            'show_debug_info': getattr(driver, 'show_debug_info', False),
            'variables': []
        }
        
        # Extract driver variables
        for var in driver.variables:
            var_data = {
                'name': var.name,
                'type': var.type,
                'targets': []
            }
            
            for target in var.targets:
                target_data = {
                    'id_name': target.id.name if target.id else None,
                    'id_type': target.id.__class__.__name__ if target.id else None,
                    'data_path': target.data_path,
                    'bone_target': getattr(target, 'bone_target', ''),
                    'transform_type': getattr(target, 'transform_type', 'LOC_X'),
                    'transform_space': getattr(target, 'transform_space', 'WORLD_SPACE')
                }
                var_data['targets'].append(target_data)
            
            data['driver']['variables'].append(var_data)
        
        # Extract modifiers
        for mod in fcurve.modifiers:
            mod_data = {
                'type': mod.type,
                'active': mod.active,
                'mute': mod.mute,
                'show_expanded': mod.show_expanded,
                'frame_start': mod.frame_start,
                'frame_end': mod.frame_end,
                'blend_in': mod.blend_in,
                'blend_out': mod.blend_out,
                'influence': mod.influence
            }
            
            # Type-specific properties
            if mod.type == 'GENERATOR':
                mod_data.update({
                    'mode': mod.mode,
                    'poly_order': mod.poly_order,
                    'use_additive': mod.use_additive,
                    'use_restricted_range': mod.use_restricted_range,
                    'coefficients': list(mod.coefficients)
                })
            elif mod.type == 'FNGENERATOR':
                mod_data.update({
                    'function_type': mod.function_type,
                    'use_additive': mod.use_additive,
                    'amplitude': mod.amplitude,
                    'phase_multiplier': mod.phase_multiplier,
                    'phase_offset': mod.phase_offset,
                    'value_offset': mod.value_offset
                })
            
            data['modifiers'].append(mod_data)
        
        return data

class SHAPEKEY_OT_load_drivers(Operator, ImportHelper):
    """Load shape key drivers from JSON file"""
    bl_idname = "shapekey.load_drivers"
    bl_label = "Load Shape Key Drivers"
    bl_description = "Load shape key drivers from JSON file to selected objects (matches by name)"
    
    filename_ext = ".json"
    filter_glob: StringProperty(default="*.json", options={'HIDDEN'})
    
    def execute(self, context):
        try:
            with open(self.filepath, 'r') as f:
                drivers_data = json.load(f)

            # Check if this is the new multi-object format
            if 'objects' in drivers_data:
                # Check if we have selected objects for multi-object loading
                selected_mesh_objects = [obj for obj in context.selected_objects
                                       if obj.type == 'MESH' and obj.data.shape_keys]
                if not selected_mesh_objects:
                    self.report({'ERROR'},
                              "Please select at least one mesh object with shape keys for loading")
                    return {'CANCELLED'}

                loaded_objects, total_drivers = self.apply_multi_object_data(context, drivers_data)
                if loaded_objects == 0:
                    warning_msg = ("No matching objects found. Make sure selected objects "
                                 "have names that match the JSON data.")
                    self.report({'WARNING'}, warning_msg)
                    return {'CANCELLED'}

                filename = os.path.basename(self.filepath)
                info_msg = f"Loaded {total_drivers} shape key drivers to {loaded_objects} objects from {filename}"
                self.report({'INFO'}, info_msg)
            else:
                # Legacy single object format
                obj = context.active_object
                if not obj or obj.type != 'MESH':
                    self.report({'ERROR'}, "Please select a mesh object for legacy format")
                    return {'CANCELLED'}

                if not obj.data.shape_keys:
                    self.report({'ERROR'}, "Selected object has no shape keys")
                    return {'CANCELLED'}

                loaded_count = self.apply_drivers_data(obj, drivers_data)
                filename = os.path.basename(self.filepath)
                self.report({'INFO'}, f"Loaded {loaded_count} shape key drivers from {filename}")

            return {'FINISHED'}

        except Exception as e:
            self.report({'ERROR'}, f"Error loading drivers: {str(e)}")
            return {'CANCELLED'}

    def apply_multi_object_data(self, context, drivers_data):
        """Apply driver data to selected objects by name matching"""
        loaded_objects = 0
        total_drivers = 0

        # Get only selected mesh objects with shape keys
        selected_objects = {obj.name: obj for obj in context.selected_objects
                           if obj.type == 'MESH' and obj.data.shape_keys}

        if not selected_objects:
            print("No selected mesh objects with shape keys found")
            return loaded_objects, total_drivers

        for obj_name, obj_data in drivers_data['objects'].items():
            if obj_name in selected_objects:
                obj = selected_objects[obj_name]
                try:
                    loaded_count = self.apply_drivers_data(obj, obj_data)
                    if loaded_count > 0:
                        loaded_objects += 1
                        total_drivers += loaded_count
                        print(f"Loaded {loaded_count} drivers to {obj_name}")
                except Exception as e:
                    print(f"Error loading drivers to {obj_name}: {e}")
            else:
                print(f"Selected object '{obj_name}' not found or doesn't match JSON data")

        return loaded_objects, total_drivers

    def apply_drivers_data(self, obj, drivers_data):
        """Apply driver data to object"""
        loaded_count = 0
        shape_keys = obj.data.shape_keys.key_blocks
        target_keys_dict = {key.name: key for key in shape_keys}

        # Ensure animation data exists
        if not obj.data.shape_keys.animation_data:
            obj.data.shape_keys.animation_data_create()

        for shape_key_name, shape_key_data in drivers_data['shape_keys'].items():
            if shape_key_name in target_keys_dict:
                try:
                    self.apply_fcurve_data(obj, shape_key_name, shape_key_data)
                    loaded_count += 1
                except Exception as e:
                    print(f"Error applying driver to {shape_key_name}: {e}")

        # Update dependency graph
        try:
            bpy.context.view_layer.update()
            bpy.context.evaluated_depsgraph_get().update()
        except:
            pass

        return loaded_count
    def apply_fcurve_data(self, obj, shape_key_name, shape_key_data):
        """Apply F-curve data to a shape key"""
        data_path = f'key_blocks["{shape_key_name}"].value'
        
        # Remove existing driver
        try:
            obj.data.shape_keys.driver_remove(data_path)
        except:
            pass
        
        # Add new driver
        fcurve = obj.data.shape_keys.driver_add(data_path)
        
        # Apply keyframes
        fcurve.keyframe_points.clear()
        for kf_data in shape_key_data['keyframes']:
            kf = fcurve.keyframe_points.insert(kf_data['co'][0], kf_data['co'][1])
            kf.interpolation = kf_data['interpolation']
            kf.handle_left_type = kf_data['handle_left_type']
            kf.handle_right_type = kf_data['handle_right_type']
            kf.handle_left = kf_data['handle_left']
            kf.handle_right = kf_data['handle_right']
        
        # Apply F-curve properties
        fcurve_props = shape_key_data['fcurve_properties']
        fcurve.extrapolation = fcurve_props['extrapolation']
        fcurve.color_mode = fcurve_props['color_mode']
        fcurve.color = fcurve_props['color']
        fcurve.auto_smoothing = fcurve_props['auto_smoothing']
        
        # Apply driver properties
        driver_data = shape_key_data['driver']
        driver = fcurve.driver
        driver.type = driver_data['type']
        driver.expression = driver_data['expression']
        if hasattr(driver, 'use_self'):
            driver.use_self = driver_data['use_self']
        if hasattr(driver, 'show_debug_info'):
            driver.show_debug_info = driver_data['show_debug_info']
        
        # Clear and apply variables
        while len(driver.variables) > 0:
            driver.variables.remove(driver.variables[0])
        
        for var_data in driver_data['variables']:
            var = driver.variables.new()
            var.name = var_data['name']
            var.type = var_data['type']
            
            for i, target_data in enumerate(var_data['targets']):
                if i < len(var.targets):
                    target = var.targets[i]
                    
                    # Find object by name and type
                    if target_data['id_name'] and target_data['id_type']:
                        if target_data['id_type'] == 'Object':
                            target.id = bpy.data.objects.get(target_data['id_name'])
                        elif target_data['id_type'] == 'Armature':
                            target.id = bpy.data.armatures.get(target_data['id_name'])
                    
                    target.data_path = target_data['data_path']
                    if hasattr(target, 'bone_target'):
                        target.bone_target = target_data['bone_target']
                    if hasattr(target, 'transform_type'):
                        target.transform_type = target_data['transform_type']
                    if hasattr(target, 'transform_space'):
                        target.transform_space = target_data['transform_space']
        
        # Apply modifiers
        while len(fcurve.modifiers) > 0:
            fcurve.modifiers.remove(fcurve.modifiers[0])
        
        for mod_data in shape_key_data['modifiers']:
            mod = fcurve.modifiers.new(mod_data['type'])
            
            # Common properties
            mod.active = mod_data['active']
            mod.mute = mod_data['mute']
            mod.show_expanded = mod_data['show_expanded']
            mod.frame_start = mod_data['frame_start']
            mod.frame_end = mod_data['frame_end']
            mod.blend_in = mod_data['blend_in']
            mod.blend_out = mod_data['blend_out']
            mod.influence = mod_data['influence']
            
            # Type-specific properties
            if mod_data['type'] == 'GENERATOR':
                mod.mode = mod_data['mode']
                mod.poly_order = mod_data['poly_order']
                mod.use_additive = mod_data['use_additive']
                mod.use_restricted_range = mod_data['use_restricted_range']
                for i, coeff in enumerate(mod_data['coefficients']):
                    if i < len(mod.coefficients):
                        mod.coefficients[i] = coeff
            elif mod_data['type'] == 'FNGENERATOR':
                mod.function_type = mod_data['function_type']
                mod.use_additive = mod_data['use_additive']
                mod.amplitude = mod_data['amplitude']
                mod.phase_multiplier = mod_data['phase_multiplier']
                mod.phase_offset = mod_data['phase_offset']
                mod.value_offset = mod_data['value_offset']

class SHAPEKEY_PT_drivers_panel(Panel):
    """Shape Key Drivers JSON Panel"""
    bl_label = "Shape Key Drivers JSON"
    bl_idname = "SHAPEKEY_PT_drivers_panel"
    bl_space_type = 'VIEW_3D'
    bl_region_type = 'UI'
    bl_category = 'Tool'
    
    def draw(self, context):
        layout = self.layout

        # Get mesh objects with shape keys
        mesh_objects = [obj for obj in context.selected_objects if obj.type == 'MESH' and obj.data.shape_keys]

        if mesh_objects:
            if len(mesh_objects) == 1:
                obj = mesh_objects[0]
                layout.label(text=f"Object: {obj.name}")
                layout.label(text=f"Shape Keys: {len(obj.data.shape_keys.key_blocks)}")

                # Count drivers
                driver_count = 0
                if obj.data.shape_keys.animation_data and obj.data.shape_keys.animation_data.drivers:
                    driver_count = len(obj.data.shape_keys.animation_data.drivers)
                layout.label(text=f"Drivers: {driver_count}")
            else:
                layout.label(text=f"Selected Objects: {len(mesh_objects)}")

                # Count total shape keys and drivers
                total_shape_keys = 0
                total_drivers = 0
                for obj in mesh_objects:
                    total_shape_keys += len(obj.data.shape_keys.key_blocks)
                    if obj.data.shape_keys.animation_data and obj.data.shape_keys.animation_data.drivers:
                        total_drivers += len(obj.data.shape_keys.animation_data.drivers)

                layout.label(text=f"Total Shape Keys: {total_shape_keys}")
                layout.label(text=f"Total Drivers: {total_drivers}")

            layout.separator()

            # Save and Load buttons
            layout.operator("shapekey.save_drivers", text="Save Drivers to JSON", icon='EXPORT')
            layout.operator("shapekey.load_drivers", text="Load Drivers from JSON", icon='IMPORT')
        else:
            layout.label(text="Select mesh(es) with shape keys", icon='INFO')

def register():
    bpy.utils.register_class(SHAPEKEY_OT_save_drivers)
    bpy.utils.register_class(SHAPEKEY_OT_load_drivers)
    bpy.utils.register_class(SHAPEKEY_PT_drivers_panel)

def unregister():
    bpy.utils.unregister_class(SHAPEKEY_PT_drivers_panel)
    bpy.utils.unregister_class(SHAPEKEY_OT_load_drivers)
    bpy.utils.unregister_class(SHAPEKEY_OT_save_drivers)

register()
