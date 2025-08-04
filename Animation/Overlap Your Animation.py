# Tooltip:  Offset the keyframes of all selected objects by the specified amount of frames. Overlap mode instead lets you specify an overlap from one object to the next. If you enable the Noise option, it will add some random variation to the offset amount. If you enable the Remove Offset option, it will align all actions to frame 0.
import bpy
import random


class OffsetAnimationOperator(bpy.types.Operator):
    bl_idname = "object.offset_animation"
    bl_label = "Offset Animation"
    bl_options = {'REGISTER', 'UNDO'}

    use_overlap: bpy.props.BoolProperty(
        name="Use Overlap Amount",
        description="Enable to use relative overlap offset",
        default=False
    )

    offset: bpy.props.IntProperty(
        name="Offset",
        description="Number of frames to offset (or overlap amount if 'Use Overlap Amount' is enabled)",
        default=0
    )

    noise: bpy.props.IntProperty(
        name="Noise",
        description="Add some offset variation (set to 0 to disable)",
        default=0
    )

    reset: bpy.props.BoolProperty(
        name="Remove Offset",
        description="Enable to align actions to frame 0",
        default=False
    )

    def draw(self, context):
        layout = self.layout
        layout.prop(self, "use_overlap")

        # Change the label dynamically based on the state of 'use_overlap'
        if self.use_overlap:
            layout.prop(self, "offset", text="Overlap")
        else:
            layout.prop(self, "offset", text="Offset")

        layout.prop(self, "noise")
        layout.prop(self, "reset")

    def execute(self, context):
        objs = [o for o in context.selected_objects if o.animation_data and o.animation_data.action]
        print(f"Number of animated objects: {len(objs)}")

        if not objs:
            self.report({'INFO'}, "No animated objects found to offset.")
            return {'CANCELLED'}

        prev_action_end_frame = 0

        for i, o in enumerate(objs):
            act = o.animation_data.action

            # Apply noise for each object
            current_noise = random.uniform(-self.noise, self.noise)

            # If 'Remove Offset' is checked, align all actions to frame 0
            if self.reset:
                delta = -act.frame_range[0]
            elif self.use_overlap:
                if i == 0:
                    # First object is only affected by noise
                    delta = current_noise
                else:
                    # Start the current action 'overlap' frames before the end of the previous action
                    delta = prev_action_end_frame - act.frame_range[0] - self.offset + current_noise
                # Update the end frame for the next iteration
                prev_action_end_frame = act.frame_range[1] + delta - current_noise
            else:
                # Original offset logic with noise added for each object
                delta = self.offset * i + current_noise

            for fcu in act.fcurves:
                for k in fcu.keyframe_points:
                    k.co[0] += delta
                    k.handle_left[0] += delta
                    k.handle_right[0] += delta

        return {'FINISHED'}

    def invoke(self, context, event):
        return context.window_manager.invoke_props_dialog(self)

def register():
    # Check if the class is already registered
    if "OffsetAnimationOperator" not in bpy.types.Operator.__subclasses__():
        bpy.utils.register_class(OffsetAnimationOperator)
    else:
        print("OffsetAnimationOperator is already registered")


def unregister():
    if "OffsetAnimationOperator" in bpy.types.Operator.__subclasses__():
        bpy.utils.unregister_class(OffsetAnimationOperator)


register()

bpy.ops.object.offset_animation('INVOKE_DEFAULT')
