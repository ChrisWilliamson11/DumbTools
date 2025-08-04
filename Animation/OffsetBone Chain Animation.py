# Tooltip:  offset the animation on a bone chain
import bpy

class OBJECT_OT_OffsetKeyframesOperator(bpy.types.Operator):
    bl_label = "Offset Keyframes"
    bl_idname = "object.offset_keyframes_operator"

    offset_amount: bpy.props.FloatProperty(name="Offset Amount", default=1.0)
    offset_direction: bpy.props.EnumProperty(
        name="Direction",
        items=[
            ('FORWARD', "Forward", "Offset keys from first to last bone"),
            ('REVERSE', "Reverse", "Offset keys from last to first bone"),
            ('REMOVE_FORWARD', "Remove Forward", "Remove the forward offset"),
            ('REMOVE_REVERSE', "Remove Reverse", "Remove the reverse offset")
        ],
        default='FORWARD'
    )

    def invoke(self, context, event):
        return context.window_manager.invoke_props_dialog(self)

    def execute(self, context):
        offset_amount = self.offset_amount
        direction = self.offset_direction

        for obj in context.selected_objects:
            if obj.type == 'ARMATURE':
                selected_bones = obj.pose.bones
                selected_keyframes = self.get_selected_keyframes(obj)

                if direction == 'FORWARD':
                    self.offset_bone_keyframes(selected_bones, selected_keyframes, offset_amount, reverse=False)
                elif direction == 'REVERSE':
                    self.offset_bone_keyframes(selected_bones, selected_keyframes, offset_amount, reverse=True)
                elif direction == 'REMOVE_FORWARD':
                    self.remove_offset(selected_bones, selected_keyframes, offset_amount, reverse=False)
                elif direction == 'REMOVE_REVERSE':
                    self.remove_offset(selected_bones, selected_keyframes, offset_amount, reverse=True)

        return {'FINISHED'}

    def get_selected_keyframes(self, obj):
        selected_keyframes = []
        action = obj.animation_data.action
        
        if action:
            for fcurve in action.fcurves:
                for keyframe in fcurve.keyframe_points:
                    if keyframe.select_control_point:
                        selected_keyframes.append(keyframe)
        return selected_keyframes

    def offset_bone_keyframes(self, selected_bones, selected_keyframes, offset_amount, reverse):
        if reverse:
            selected_bones = list(selected_bones)[::-1]

        for index, bone in enumerate(selected_bones):
            for fcurve in bpy.context.object.animation_data.action.fcurves:
                if bone.name in fcurve.data_path:
                    for keyframe in fcurve.keyframe_points:
                        if keyframe in selected_keyframes:
                            keyframe.co.x += offset_amount * index

    def remove_offset(self, selected_bones, selected_keyframes, offset_amount, reverse):
        if reverse:
            selected_bones = list(selected_bones)[::-1]

        for index, bone in enumerate(selected_bones):
            for fcurve in bpy.context.object.animation_data.action.fcurves:
                if bone.name in fcurve.data_path:
                    for keyframe in fcurve.keyframe_points:
                        if keyframe in selected_keyframes:
                            keyframe.co.x -= offset_amount * index

def register():
    bpy.utils.register_class(OBJECT_OT_OffsetKeyframesOperator)

def unregister():
    bpy.utils.unregister_class(OBJECT_OT_OffsetKeyframesOperator)


register()


bpy.ops.object.offset_keyframes_operator('INVOKE_DEFAULT')
