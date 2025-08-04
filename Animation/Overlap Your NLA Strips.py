# Tooltip: Offset the NLA strips of all selected objects by the specified amount of frames. Overlap mode instead lets you specify an overlap from one object to the next. If you enable the Noise option, it will add some random variation to the offset amount. If you enable the Remove Offset option, it will align all strips to frame 0.
import bpy
import random


class OffsetNLAStripsOperator(bpy.types.Operator):
    bl_idname = "object.offset_nla_strips"
    bl_label = "Offset NLA Strips"
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
        description="Enable to align strips to frame 0",
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
        objs = [o for o in context.selected_objects if o.animation_data and o.animation_data.nla_tracks]
        print(f"Number of objects with NLA strips: {len(objs)}")

        if not objs:
            self.report({'INFO'}, "No objects with NLA strips found to offset.")
            return {'CANCELLED'}

        prev_strip_end_frame = 0

        for i, obj in enumerate(objs):
            for track in obj.animation_data.nla_tracks:
                for strip in track.strips:
                    current_noise = random.uniform(-self.noise, self.noise)

                    if self.reset:
                        delta = -strip.frame_start
                    elif self.use_overlap:
                        if i == 0:
                            delta = current_noise
                        else:
                            delta = prev_strip_end_frame - strip.frame_start - self.offset + current_noise
                        prev_strip_end_frame = strip.frame_end + delta - current_noise
                    else:
                        delta = self.offset * i + current_noise

                    strip.frame_start += delta
                    strip.frame_end += delta

        return {'FINISHED'}

    def invoke(self, context, event):
        return context.window_manager.invoke_props_dialog(self)

def register():
    # Check if the class is already registered
    if "OffsetNLAStripsOperator" not in bpy.types.Operator.__subclasses__():
        bpy.utils.register_class(OffsetNLAStripsOperator)
    else:
        print("OffsetNLAStripsOperator is already registered")


def unregister():
    if "OffsetNLAStripsOperator" in bpy.types.Operator.__subclasses__():
        bpy.utils.unregister_class(OffsetNLAStripsOperator)


register()

bpy.ops.object.offset_nla_strips('INVOKE_DEFAULT')
