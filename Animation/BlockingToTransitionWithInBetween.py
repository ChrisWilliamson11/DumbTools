import bpy
import math
import random

class ConvertSteppedToBezierOperator(bpy.types.Operator):
    """Convert Stepped Animation to Bezier with Transition Length"""
    bl_idname = "object.convert_stepped_to_bezier"
    bl_label = "Convert Stepped to Bezier"
    bl_options = {'REGISTER', 'UNDO'}

    # Slider for transition length
    transition_length: bpy.props.IntProperty(
        name="Transition Length",
        description="Number of frames for transition",
        default=5,
        min=1,
        max=100
    )

    # New properties for z-offset and rotation
    z_offset: bpy.props.FloatProperty(
        name="Z Offset",
        description="Base units to move up on Z axis at midpoint",
        default=3.0,
        min=0.0
    )
    rotation_degrees: bpy.props.FloatProperty(
        name="Rotation Degrees",
        description="Base degrees to rotate during transition",
        default=720.0
    )
    rotation_axis: bpy.props.EnumProperty(
        name="Rotation Axis",
        items=[('X', 'X', 'X Axis'), ('Z', 'Z', 'Z Axis')],
        default='Z'
    )
    randomness: bpy.props.FloatProperty(
        name="Randomness",
        description="Amount of randomness (0-1)",
        default=0.2,
        min=0.0,
        max=1.0
    )

    def execute(self, context):
        # Iterate through all selected objects
        for obj in context.selected_objects:
            if obj.animation_data and obj.animation_data.action:
                self.process_object(obj)
        
        return {'FINISHED'}

    def process_object(self, obj):
        action = obj.animation_data.action
        fcurves = action.fcurves
        
        # Process each fcurve for the object
        for fcurve in fcurves:
            selected_keyframes = [kp for kp in fcurve.keyframe_points if kp.select_control_point]
            
            # Convert all keyframes to Bezier first
            for kp in selected_keyframes:
                kp.interpolation = 'BEZIER'

            # Duplicating keyframes for smoothing transition
            if len(selected_keyframes) > 1:
                for i in range(1, len(selected_keyframes)):
                    prev_keyframe = selected_keyframes[i - 1]
                    current_keyframe = selected_keyframes[i]
                    
                    # Duplicate the first keyframe and move it before the second
                    self.duplicate_keyframe(fcurve, prev_keyframe, current_keyframe.co.x - self.transition_length)

                    # If not the last keyframe, duplicate the current keyframe and move it behind the next
                    if i < len(selected_keyframes) - 1:
                        next_keyframe = selected_keyframes[i + 1]
                        self.duplicate_keyframe(fcurve, current_keyframe, next_keyframe.co.x - self.transition_length)

        # Add Z offset and rotation
        self.add_z_offset(obj)
        self.add_rotation(obj)

    def add_z_offset(self, obj):
        z_fcurve = self.get_or_create_fcurve(obj, 'location', 2)
        keyframes = [kp for kp in z_fcurve.keyframe_points if kp.select_control_point]
        
        for i in range(1, len(keyframes), 2):  # Step by 2 to get pairs of keyframes
            if i + 1 < len(keyframes):
                start_frame = keyframes[i].co.x  # Start from the newly generated keyframe
                end_frame = keyframes[i + 1].co.x
                mid_frame = (start_frame + end_frame) / 2
                
                # Add randomness to z_offset
                random_offset = self.z_offset * (1 + random.uniform(-self.randomness, self.randomness))
                
                # Add keyframe at midpoint with random z_offset
                z_value = z_fcurve.evaluate(mid_frame) + random_offset
                new_kf = z_fcurve.keyframe_points.insert(mid_frame, z_value)
                new_kf.interpolation = 'BEZIER'

    def add_rotation(self, obj):
        axis_index = 0 if self.rotation_axis == 'X' else 2  # 0 for X, 2 for Z
        rot_fcurve = self.get_or_create_fcurve(obj, 'rotation_euler', axis_index)
        keyframes = [kp for kp in rot_fcurve.keyframe_points if kp.select_control_point]
        
        if not keyframes:
            return  # Exit if there are no keyframes

        current_rotation = rot_fcurve.evaluate(keyframes[0].co.x)  # Start with the initial rotation
        
        for i in range(0, len(keyframes) - 1, 2):  # Step by 2 to get pairs of keyframes
            start_frame = keyframes[i].co.x
            end_frame = keyframes[i + 1].co.x
            
            # Calculate the available gap
            gap = end_frame - start_frame
            
            # Determine the actual transition start and end frames
            transition_start = start_frame + self.transition_length
            transition_end = end_frame
            
            if gap <= self.transition_length:
                transition_start = start_frame + 1
            
            # Add rotation keyframe at start of transition (maintain previous rotation)
            start_kf = rot_fcurve.keyframe_points.insert(transition_start, current_rotation)
            start_kf.interpolation = 'BEZIER'
            
            # Calculate new rotation
            new_rotation = current_rotation + math.radians(self.rotation_degrees)
            
            # Add rotation keyframe at end of transition
            end_kf = rot_fcurve.keyframe_points.insert(transition_end, new_rotation)
            end_kf.interpolation = 'BEZIER'
            
            # Update current rotation for the next iteration
            current_rotation = new_rotation

    def get_or_create_fcurve(self, obj, data_path, array_index):
        if not obj.animation_data:
            obj.animation_data_create()
        action = obj.animation_data.action
        if not action:
            action = bpy.data.actions.new(name="MyAction")
            obj.animation_data.action = action
        
        for fc in action.fcurves:
            if fc.data_path == data_path and fc.array_index == array_index:
                return fc
        
        return action.fcurves.new(data_path=data_path, index=array_index)

    def duplicate_keyframe(self, fcurve, keyframe, new_x):
        """Duplicate a keyframe and place it at a new location"""
        new_kf = fcurve.keyframe_points.insert(new_x, keyframe.co.y)
        new_kf.interpolation = 'BEZIER'
        
        # Add randomness to transition length
        random_offset = int(self.transition_length * random.uniform(-self.randomness, self.randomness))
        new_x += random_offset
        new_kf.co.x = new_x

    def invoke(self, context, event):
        # Open the pop-up dialog when the operator is called
        return context.window_manager.invoke_props_dialog(self)


def register():
    bpy.utils.register_class(ConvertSteppedToBezierOperator)

def unregister():
    bpy.utils.unregister_class(ConvertSteppedToBezierOperator)


register()
# Test call to the operator to show the dialog
bpy.ops.object.convert_stepped_to_bezier('INVOKE_DEFAULT')
