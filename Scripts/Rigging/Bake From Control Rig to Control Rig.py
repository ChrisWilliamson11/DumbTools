# Tooltip: Bake animation from source control rig to target control rig while preserving shape key values

import bpy
import json
import mathutils
from bpy.props import StringProperty, PointerProperty
from bpy.types import Panel, Operator, PropertyGroup
from bpy_extras.io_utils import ImportHelper

class BakeControlRigProperties(PropertyGroup):
    source_rig: PointerProperty(
        name="Source Control Rig",
        type=bpy.types.Object,
        description="Source armature to bake animation from",
        poll=lambda self, obj: obj.type == 'ARMATURE'
    )
    
    target_rig: PointerProperty(
        name="Target Control Rig", 
        type=bpy.types.Object,
        description="Target armature to bake animation to",
        poll=lambda self, obj: obj.type == 'ARMATURE'
    )
    
    json_filepath: StringProperty(
        name="Target Rig JSON File",
        description="JSON file containing target rig driver data",
        default="",
        subtype='FILE_PATH'
    )

class BAKE_OT_select_json_file(Operator, ImportHelper):
    """Select JSON file for target control rig"""
    bl_idname = "bake.select_json_file"
    bl_label = "Select JSON File"
    bl_description = "Select JSON file containing target rig driver data"
    
    filename_ext = ".json"
    filter_glob: StringProperty(default="*.json", options={'HIDDEN'})
    
    def execute(self, context):
        context.scene.bake_control_rig_props.json_filepath = self.filepath
        return {'FINISHED'}

class BAKE_OT_bake_control_rigs(Operator):
    """Bake animation from source to target control rig"""
    bl_idname = "bake.bake_control_rigs"
    bl_label = "Bake Control Rig Animation"
    bl_description = "Bake animation from source to target control rig while preserving shape key values"
    
    def execute(self, context):
        props = context.scene.bake_control_rig_props
        
        # Validation
        if not props.source_rig:
            self.report({'ERROR'}, "Please select a source control rig")
            return {'CANCELLED'}
        
        if not props.target_rig:
            self.report({'ERROR'}, "Please select a target control rig")
            return {'CANCELLED'}
        
        if not props.json_filepath:
            self.report({'ERROR'}, "Please select a JSON file for target rig")
            return {'CANCELLED'}
        
        selected_meshes = [obj for obj in context.selected_objects if obj.type == 'MESH' and obj.data.shape_keys]
        
        if not selected_meshes:
            self.report({'ERROR'}, "Please select at least one mesh with shape keys")
            return {'CANCELLED'}
        
        try:
            # Load target rig JSON data
            with open(props.json_filepath, 'r') as f:
                target_rig_data = json.load(f)
            
            total_baked = self.bake_animation(context, props, selected_meshes, target_rig_data)
            
            self.report({'INFO'}, f"Successfully baked {total_baked} shape key animations")
            return {'FINISHED'}
            
        except Exception as e:
            self.report({'ERROR'}, f"Error baking animation: {str(e)}")
            return {'CANCELLED'}
    
    def bake_animation(self, context, props, selected_meshes, target_rig_data):
        """Main baking logic"""
        total_baked = 0
        
        # Get frame range from scene
        frame_start = context.scene.frame_start
        frame_end = context.scene.frame_end
        
        for mesh in selected_meshes:
            if not mesh.data.shape_keys or not mesh.data.shape_keys.animation_data:
                continue
            
            # Find matching target rig data
            target_mesh_data = None
            if 'objects' in target_rig_data:
                # Multi-object format
                target_mesh_data = target_rig_data['objects'].get(mesh.name)
            else:
                # Legacy single object format
                if target_rig_data.get('object_name') == mesh.name:
                    target_mesh_data = target_rig_data
            
            if not target_mesh_data:
                print(f"No target data found for mesh: {mesh.name}")
                continue
            
            baked_count = self.bake_mesh_shape_keys(
                context, props, mesh, target_mesh_data, frame_start, frame_end
            )
            total_baked += baked_count
        
        return total_baked
    
    def bake_mesh_shape_keys(self, context, props, mesh, target_mesh_data, frame_start, frame_end):
        """Bake shape keys for a single mesh"""
        baked_count = 0
        
        for shape_key_name, shape_key_data in target_mesh_data['shape_keys'].items():
            if shape_key_name == "Basis":
                continue
            
            # Check if shape key exists on mesh
            if shape_key_name not in mesh.data.shape_keys.key_blocks:
                continue
            
            # Get source driver info
            source_driver_info = self.get_source_driver_info(mesh, shape_key_name)
            if not source_driver_info:
                continue
            
            # Get target driver info from JSON
            target_driver_info = self.parse_target_driver_info(shape_key_data)
            if not target_driver_info:
                continue

            print(f"Target driver info for {shape_key_name}: {target_driver_info}")
            
            # Bake keyframes
            success = self.bake_shape_key_keyframes(
                context, props, mesh, shape_key_name, 
                source_driver_info, target_driver_info, frame_start, frame_end
            )
            
            if success:
                baked_count += 1
                print(f"Baked shape key: {shape_key_name}")
        
        return baked_count
    
    def get_source_driver_info(self, mesh, shape_key_name):
        """Extract driver information from source mesh"""
        if not mesh.data.shape_keys.animation_data:
            return None

        data_path = f'key_blocks["{shape_key_name}"].value'

        for fcurve in mesh.data.shape_keys.animation_data.drivers:
            if fcurve.data_path == data_path:
                driver = fcurve.driver
                if driver.variables:
                    # Find the 'var' variable (ignore 'amp' variables)
                    for var in driver.variables:
                        if var.name == 'var' or (var.name != 'amp' and len(driver.variables) == 1):
                            if var.targets[0].id and var.targets[0].bone_target:
                                return {
                                    'bone_name': var.targets[0].bone_target,
                                    'data_path': var.targets[0].data_path,
                                    'transform_type': getattr(var.targets[0], 'transform_type', 'LOC_X'),
                                    'armature': var.targets[0].id
                                }
        return None
    
    def parse_target_driver_info(self, shape_key_data):
        """Parse target driver info from JSON data"""
        driver_data = shape_key_data.get('driver', {})
        if not driver_data.get('variables'):
            return None

        # Find the 'var' variable (ignore 'amp' variables)
        var_data = None
        for variable in driver_data['variables']:
            if variable['name'] == 'var' or (variable['name'] != 'amp' and len(driver_data['variables']) == 1):
                var_data = variable
                break

        if not var_data or not var_data.get('targets'):
            return None

        target_data = var_data['targets'][0]

        # Get polynomial modifier info
        polynomial_info = None
        for mod_data in shape_key_data.get('modifiers', []):
            if mod_data['type'] == 'GENERATOR' and mod_data.get('mode') == 'POLYNOMIAL':
                polynomial_info = {
                    'coefficients': mod_data.get('coefficients', []),
                    'poly_order': mod_data.get('poly_order', 1)
                }
                break

        return {
            'bone_name': target_data.get('bone_target', ''),
            'data_path': target_data.get('data_path', ''),
            'transform_type': target_data.get('transform_type', 'LOC_X'),
            'polynomial': polynomial_info,
            'expression': driver_data.get('expression', 'var')
        }
    
    def bake_shape_key_keyframes(self, context, props, mesh, shape_key_name,
                                source_info, target_info, frame_start, frame_end):
        """Bake keyframes for a single shape key"""
        try:
            # Get source bone from the armature that the mesh's drivers are currently pointing to
            source_armature = source_info['armature']
            source_bone = source_armature.pose.bones.get(source_info['bone_name'])

            # Get target bone from the target rig
            target_bone = props.target_rig.pose.bones.get(target_info['bone_name'])

            if not source_bone:
                print(f"Source bone not found: {source_info['bone_name']} in {source_armature.name}")
                return False

            if not target_bone:
                print(f"Target bone not found: {target_info['bone_name']} in {props.target_rig.name}")
                return False

            shape_key = mesh.data.shape_keys.key_blocks[shape_key_name]

            # Get keyframe frames from source bone
            source_keyframe_frames = self.get_bone_keyframe_frames(source_armature, source_info)

            if not source_keyframe_frames:
                print(f"No keyframes found on source bone: {source_info['bone_name']}")
                return False

            # Clear existing keyframes on target bone
            self.clear_bone_keyframes(target_bone, target_info)

            # Iterate through only the frames where source bone has keyframes
            for frame in source_keyframe_frames:
                if frame < frame_start or frame > frame_end:
                    continue

                context.scene.frame_set(frame)

                # Get current shape key value
                shape_key_value = shape_key.value

                # Reverse engineer target bone value needed
                target_bone_value = self.reverse_engineer_bone_value(shape_key_value, target_info)

                # Set target bone value and keyframe
                self.set_bone_value_and_keyframe(target_bone, target_info, target_bone_value, frame)

            print(f"Baked {len(source_keyframe_frames)} keyframes for {shape_key_name}")
            return True

        except Exception as e:
            print(f"Error baking {shape_key_name}: {e}")
            return False
    
    def reverse_engineer_bone_value(self, shape_key_value, target_info):
        """Reverse engineer the bone value needed to produce the given shape key value"""
        if not target_info.get('polynomial'):
            # Simple linear case
            return shape_key_value
        
        # Handle polynomial modifier
        coeffs = target_info['polynomial']['coefficients']
        
        if len(coeffs) == 2:  # Linear: y = a + bx, solve for x: x = (y - a) / b
            a, b = coeffs[0], coeffs[1]
            if abs(b) > 1e-6:  # Avoid division by zero
                return (shape_key_value - a) / b
        elif len(coeffs) == 3:  # Quadratic: y = a + bx + cx^2
            a, b, c = coeffs[0], coeffs[1], coeffs[2]
            # Solve quadratic equation: cx^2 + bx + (a - y) = 0
            discriminant = b*b - 4*c*(a - shape_key_value)
            if discriminant >= 0 and abs(c) > 1e-6:
                # Take positive root (assuming typical use case)
                return (-b + (discriminant ** 0.5)) / (2 * c)
        
        # Fallback: return shape key value as-is
        return shape_key_value

    def get_bone_keyframe_frames(self, armature, source_info):
        """Get list of frames where the source bone has keyframes"""
        keyframe_frames = []

        if not armature.animation_data or not armature.animation_data.action:
            print(f"No animation data or action on armature: {armature.name}")
            return keyframe_frames

        action = armature.animation_data.action
        bone_name = source_info["bone_name"]
        data_path = source_info["data_path"]
        transform_type = source_info['transform_type']

        print(f"Looking for keyframes on bone: {bone_name}")
        print(f"Data path: {data_path}")
        print(f"Transform type: {transform_type}")

        # Try different data path formats
        possible_data_paths = [
            f'pose.bones["{bone_name}"].{data_path}',
            data_path,  # In case it's already a full path
            f'pose.bones["{bone_name}"].location',
            f'pose.bones["{bone_name}"].rotation_euler',
            f'pose.bones["{bone_name}"].scale'
        ]

        # Get transform type index
        array_index = self.get_transform_array_index(transform_type)
        print(f"Looking for array index: {array_index}")

        # Find F-curves for this bone's property
        found_fcurves = []
        for fcurve in action.fcurves:
            for test_path in possible_data_paths:
                if fcurve.data_path == test_path and fcurve.array_index == array_index:
                    found_fcurves.append(fcurve)
                    print(f"Found matching F-curve: {fcurve.data_path}[{fcurve.array_index}]")
                    # Extract keyframe frames
                    for keyframe in fcurve.keyframe_points:
                        frame = int(keyframe.co[0])
                        if frame not in keyframe_frames:
                            keyframe_frames.append(frame)
                    break

        if not found_fcurves:
            print(f"No F-curves found for bone {bone_name}. Available F-curves:")
            for fcurve in action.fcurves:
                if bone_name in fcurve.data_path:
                    print(f"  - {fcurve.data_path}[{fcurve.array_index}]")

        print(f"Found keyframes on frames: {sorted(keyframe_frames)}")
        return sorted(keyframe_frames)

    def get_transform_array_index(self, transform_type):
        """Get array index for transform type"""
        transform_indices = {
            'LOC_X': 0, 'LOC_Y': 1, 'LOC_Z': 2,
            'ROT_X': 0, 'ROT_Y': 1, 'ROT_Z': 2,
            'SCALE_X': 0, 'SCALE_Y': 1, 'SCALE_Z': 2
        }
        return transform_indices.get(transform_type, 0)

    def clear_bone_keyframes(self, bone, target_info):
        """Clear existing keyframes on target bone"""
        if bone.id_data.animation_data and bone.id_data.animation_data.action:
            action = bone.id_data.animation_data.action
            data_path = f'pose.bones["{bone.name}"].{target_info["data_path"]}'
            
            # Find and remove existing F-curves
            fcurves_to_remove = []
            for fcurve in action.fcurves:
                if fcurve.data_path == data_path:
                    fcurves_to_remove.append(fcurve)
            
            for fcurve in fcurves_to_remove:
                action.fcurves.remove(fcurve)
    
    def set_bone_value_and_keyframe(self, bone, target_info, value, frame):
        """Set bone value and insert keyframe"""
        transform_type = target_info['transform_type']

        # Determine data path from transform type if not provided or empty
        data_path = target_info.get('data_path', '')
        if not data_path:
            if transform_type.startswith('LOC_'):
                data_path = 'location'
            elif transform_type.startswith('ROT_'):
                data_path = 'rotation_euler'
            elif transform_type.startswith('SCALE_'):
                data_path = 'scale'
            else:
                print(f"Unknown transform type: {transform_type}")
                return

        # Set the bone property value
        if data_path == 'location' or transform_type.startswith('LOC_'):
            if transform_type == 'LOC_X':
                bone.location.x = value
            elif transform_type == 'LOC_Y':
                bone.location.y = value
            elif transform_type == 'LOC_Z':
                bone.location.z = value
        elif data_path == 'rotation_euler' or transform_type.startswith('ROT_'):
            if transform_type == 'ROT_X':
                bone.rotation_euler.x = value
            elif transform_type == 'ROT_Y':
                bone.rotation_euler.y = value
            elif transform_type == 'ROT_Z':
                bone.rotation_euler.z = value
        elif data_path == 'scale' or transform_type.startswith('SCALE_'):
            if transform_type == 'SCALE_X':
                bone.scale.x = value
            elif transform_type == 'SCALE_Y':
                bone.scale.y = value
            elif transform_type == 'SCALE_Z':
                bone.scale.z = value

        # Use the correct data path for keyframe insertion
        if data_path == 'location':
            final_data_path = 'location'
        elif data_path == 'rotation_euler':
            final_data_path = 'rotation_euler'
        elif data_path == 'scale':
            final_data_path = 'scale'
        else:
            final_data_path = data_path

        print(f"Inserting keyframe: bone={bone.name}, data_path={final_data_path}, value={value}, frame={frame}")

        # Insert keyframe
        try:
            bone.keyframe_insert(data_path=final_data_path, frame=frame)
        except Exception as e:
            print(f"Error inserting keyframe: {e}")
            print(f"Attempted: bone.keyframe_insert(data_path='{final_data_path}', frame={frame})")

class BAKE_PT_control_rig_panel(Panel):
    """Control Rig Baking Panel"""
    bl_label = "Bake Control Rig Animation"
    bl_idname = "BAKE_PT_control_rig_panel"
    bl_space_type = 'VIEW_3D'
    bl_region_type = 'UI'
    bl_category = 'Tool'
    
    def draw(self, context):
        layout = self.layout
        props = context.scene.bake_control_rig_props
        
        # Source and Target Rigs
        layout.label(text="Control Rigs:")
        layout.label(text="Source: Rig with keyframes to bake FROM", icon='INFO')
        layout.prop(props, "source_rig")
        layout.label(text="Target: Rig to bake keyframes TO", icon='INFO')
        layout.prop(props, "target_rig")
        
        layout.separator()
        
        # JSON File Selection
        layout.label(text="Target Rig JSON File:")
        row = layout.row()
        row.prop(props, "json_filepath", text="")
        row.operator("bake.select_json_file", text="", icon='FILEBROWSER')
        
        layout.separator()
        
        # Selected Meshes Info
        selected_meshes = [obj for obj in context.selected_objects if obj.type == 'MESH' and obj.data.shape_keys]
        layout.label(text=f"Selected Meshes: {len(selected_meshes)}")
        
        layout.separator()
        
        # Bake Button
        layout.operator("bake.bake_control_rigs", text="Bake Animation", icon='RENDER_ANIMATION')

def register():
    bpy.utils.register_class(BakeControlRigProperties)
    bpy.utils.register_class(BAKE_OT_select_json_file)
    bpy.utils.register_class(BAKE_OT_bake_control_rigs)
    bpy.utils.register_class(BAKE_PT_control_rig_panel)
    
    bpy.types.Scene.bake_control_rig_props = PointerProperty(type=BakeControlRigProperties)

def unregister():
    bpy.utils.unregister_class(BAKE_PT_control_rig_panel)
    bpy.utils.unregister_class(BAKE_OT_bake_control_rigs)
    bpy.utils.unregister_class(BAKE_OT_select_json_file)
    bpy.utils.unregister_class(BakeControlRigProperties)
    
    del bpy.types.Scene.bake_control_rig_props

register()
