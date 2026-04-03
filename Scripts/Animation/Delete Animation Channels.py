# Tooltip:  Tooltip: Removes animation channels off selected objects/bones
import bpy

import bpy

def iter_fcurves(action):
    if not action:
        return
    if hasattr(action, "fcurves") and action.fcurves:
        for fc in action.fcurves:
            yield fc
    if hasattr(action, "layers"):
        for layer in action.layers:
            if hasattr(layer, "strips"):
                for strip in layer.strips:
                    if hasattr(strip, "channelbags"):
                         for bag in strip.channelbags:
                             if hasattr(bag, "fcurves"):
                                 for fc in bag.fcurves:
                                     yield fc
                    if hasattr(strip, "fcurves"):
                        for fc in strip.fcurves:
                            yield fc
                    elif hasattr(strip, "channels"):
                         for fc in strip.channels:
                             yield fc

def remove_fcurve(action, fcurve):
    if hasattr(action, "fcurves") and action.fcurves:
        try:
            action.fcurves.remove(fcurve)
            return
        except TypeError: pass
        except RuntimeError: pass
        except ValueError: pass
    if hasattr(action, "layers"):
        for layer in action.layers:
            if hasattr(layer, "strips"):
                for strip in layer.strips:
                    if hasattr(strip, "channelbags"):
                        for bag in strip.channelbags:
                            if hasattr(bag, "fcurves"):
                                try:
                                    bag.fcurves.remove(fcurve)
                                    return
                                except TypeError: pass
                                except RuntimeError: pass
                                except ValueError: pass
                    if hasattr(strip, "fcurves"):
                        try:
                            strip.fcurves.remove(fcurve)
                            return
                        except TypeError: pass
                        except RuntimeError: pass
                        except ValueError: pass
                    elif hasattr(strip, "channels"):
                        try:
                            strip.channels.remove(fcurve)
                            return
                        except TypeError: pass
                        except RuntimeError: pass
                        except ValueError: pass

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
                    act = obj.animation_data.action
                    for fcurve in list(iter_fcurves(act)):
                        if self.delete_location and fcurve.data_path.endswith("location"):
                            remove_fcurve(act, fcurve)
                        elif self.delete_rotation and fcurve.data_path.endswith(("rotation_euler", "rotation_quaternion")):
                            remove_fcurve(act, fcurve)
                        elif self.delete_scale and fcurve.data_path.endswith("scale"):
                            remove_fcurve(act, fcurve)

        # Handle selected bones within an armature, using the refined approach
        if context.active_object and context.active_object.type == 'ARMATURE' and context.active_object.mode == 'POSE':
            armature = context.active_object
            action = armature.animation_data.action if armature.animation_data else None

            if action:
                selected_bone_paths = [f'pose.bones["{bone.name}"].' for bone in context.selected_pose_bones]

                fcurves_to_remove = [
                    fcurve for fcurve in iter_fcurves(action) if any(
                        bone_path in fcurve.data_path for bone_path in selected_bone_paths
                    ) and (
                        (self.delete_location and ".location" in fcurve.data_path) or
                        (self.delete_rotation and ".rotation_" in fcurve.data_path) or
                        (self.delete_scale and ".scale" in fcurve.data_path)
                    )
                ]

                for fcurve in fcurves_to_remove:
                    remove_fcurve(action, fcurve)

        return {'FINISHED'}

    def invoke(self, context, event):
        return context.window_manager.invoke_props_dialog(self)

def register():
    bpy.utils.register_class(RemoveAnimChannels)

def unregister():
    bpy.utils.unregister_class(RemoveAnimChannels)


register()
bpy.ops.object.remove_anim_channels('INVOKE_DEFAULT')
