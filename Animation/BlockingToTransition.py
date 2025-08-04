import bpy

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

    def execute(self, context):
        # Check if an object is selected
        obj = context.object
        if not obj or not obj.animation_data or not obj.animation_data.action:
            self.report({'WARNING'}, "No object with animation selected")
            return {'CANCELLED'}
        
        # Get the fcurves (animation curves) of the selected object
        action = obj.animation_data.action
        fcurves = action.fcurves
        
        # Process each fcurve for the selected object
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

        return {'FINISHED'}

    def duplicate_keyframe(self, fcurve, keyframe, new_x):
        """Duplicate a keyframe and place it at a new location"""
        new_kf = fcurve.keyframe_points.insert(new_x, keyframe.co.y)
        new_kf.interpolation = 'BEZIER'

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
