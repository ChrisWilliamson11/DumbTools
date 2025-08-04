# Tooltip: Removes animation channels off all selected NLA clips

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
        # Handle selected objects
        selected_objects = context.selected_objects
        for obj in selected_objects:
            # Handle armature objects. This is where you check for selected bones.
            if context.active_object and context.active_object.type == 'ARMATURE' and context.active_object.mode == 'POSE':
                armature = context.active_object
                if armature.animation_data:
                    for nla_track in armature.animation_data.nla_tracks:
                        for strip in nla_track.strips:
                            if strip.select:  # Check if the strip is selected
                                action = strip.action
                                if action:
                                    self.delete_action_channels(action, context)  # Pass context here

        return {'FINISHED'}

    def delete_action_channels(self, action, context):
        selected_bone_names = [bone.name for bone in context.selected_pose_bones]
        
        # Delete selected channel types from the given action
        fcurves_to_remove = []
        for fcurve in action.fcurves:
            bone_name = fcurve.data_path.split('"')[1] if '"' in fcurve.data_path else None
            if bone_name in selected_bone_names:  # Check if the bone is selected
                if self.delete_location and fcurve.data_path.endswith("location"):
                    fcurves_to_remove.append(fcurve)
                elif self.delete_rotation and fcurve.data_path.endswith(("rotation_euler", "rotation_quaternion", "rotation_axis_angle")):
                    fcurves_to_remove.append(fcurve)
                elif self.delete_scale and fcurve.data_path.endswith("scale"):
                    fcurves_to_remove.append(fcurve)

        # Perform the actual removal outside of the loop to avoid modifying the collection while iterating
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
