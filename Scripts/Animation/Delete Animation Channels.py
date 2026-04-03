# Tooltip:  Tooltip: Removes animation channels off selected objects/bones
import bpy

class RemoveAnimChannels(bpy.types.Operator):
    """Remove Selected Animation Channels from Selected Objects or Bones"""
    bl_idname = "object.remove_anim_channels"
    bl_label = "Remove Animation Channels"
    bl_options = {'REGISTER', 'UNDO'}

    delete_location: bpy.props.BoolProperty(name="Location", default=False)
    delete_rotation: bpy.props.BoolProperty(name="Rotation", default=False)
    delete_scale: bpy.props.BoolProperty(name="Scale", default=False)

    def execute(self, context):
        # Handle selected objects (non-armature)
        selected_objects = context.selected_objects
        for obj in selected_objects:
            if context.active_object.type != 'ARMATURE':
                if obj.animation_data and obj.animation_data.action:
                    fcurves = obj.animation_data.action.fcurves
                    for fcurve in fcurves[:]:
                        if self.delete_location and fcurve.data_path.endswith("location"):
                            fcurves.remove(fcurve)
                        elif self.delete_rotation and fcurve.data_path.endswith(("rotation_euler", "rotation_quaternion")):
                            fcurves.remove(fcurve)
                        elif self.delete_scale and fcurve.data_path.endswith("scale"):
                            fcurves.remove(fcurve)

        # Handle selected bones within an armature, using the refined approach
        if context.active_object and context.active_object.type == 'ARMATURE' and context.active_object.mode == 'POSE':
            armature = context.active_object
            action = armature.animation_data.action if armature.animation_data else None

            if action:
                selected_bone_paths = [f'pose.bones["{bone.name}"].' for bone in context.selected_pose_bones]

                fcurves_to_remove = [
                    fcurve for fcurve in action.fcurves if any(
                        bone_path in fcurve.data_path for bone_path in selected_bone_paths
                    ) and (
                        (self.delete_location and ".location" in fcurve.data_path) or
                        (self.delete_rotation and ".rotation_" in fcurve.data_path) or
                        (self.delete_scale and ".scale" in fcurve.data_path)
                    )
                ]

                for fcurve in fcurves_to_remove:
                    action.fcurves.remove(fcurve)

        return {'FINISHED'}

    def invoke(self, context, event):
        return context.window_manager.invoke_props_dialog(self)

def register():
    bpy.utils.register_class(RemoveAnimChannels)

def unregister():
    bpy.utils.unregister_class(RemoveAnimChannels)


register()
bpy.ops.object.remove_anim_channels('INVOKE_DEFAULT')
