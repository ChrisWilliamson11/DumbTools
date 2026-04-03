import bpy
import math
class ScaleKeyframesToLimitNLA(bpy.types.Operator):
    """Scale keyframes to within the rotation limits of selected bones"""
    bl_idname = "pose.scale_keyframes_to_limit_nla"
    bl_label = "Scale Keyframes to Limit NLA"
    bl_options = {'REGISTER', 'UNDO'}

    proportional_size: bpy.props.FloatProperty(name="Proportional Size", default=119.139)
    proportional_falloff: bpy.props.EnumProperty(
        name="Proportional Falloff",
        items=[
            ('SMOOTH', "Smooth", ""),
            ('SPHERE', "Sphere", ""),
            ('ROOT', "Root", ""),
            ('INVERSE_SQUARE', "Inverse Square", ""),
            ('SHARP', "Sharp", ""),
            ('LINEAR', "Linear", ""),
            ('CONSTANT', "Constant", "")
        ],
        default='SMOOTH'
    )

    @classmethod
    def poll(cls, context):
        return (
            context.active_object is not None and 
            context.active_object.type == 'ARMATURE' and 
            context.mode == 'POSE' and 
            context.active_object.animation_data is not None and
            context.active_object.animation_data.action is not None
        )

    def execute(self, context):
        # Check if the current area is the Graph Editor
        if context.area.type != 'GRAPH_EDITOR':
            self.report({'WARNING'}, "Script must be run from within the Graph Editor.")
            return {'CANCELLED'}

        # Process all selected bones
        for bone in context.selected_pose_bones:
            constraint = next((c for c in bone.constraints if c.type == 'LIMIT_ROTATION'), None)
            if not constraint:
                self.report({'INFO'}, "Bone {} has no limit rotation constraint.".format(bone.name))
                continue  # Skip this bone if no constraint

            # Process all NLA strips for each selected bone
            nla_tracks = context.active_object.animation_data.nla_tracks
            for track in nla_tracks:
                for strip in track.strips:
                    if strip.select:
                        action = strip.action
                        if action:
                            # Process all fcurves in the action related to the bone
                            for fcurve in action.fcurves:
                                if fcurve.data_path.startswith('pose.bones["{}"].'.format(bone.name)):
                                    for index, axis in enumerate("xyz"):
                                        if "rotation_euler" in fcurve.data_path and fcurve.array_index == index:
                                            self.process_axis(context, bone, constraint, axis, index, fcurve)
        return {'FINISHED'}


    def process_axis(self, context, bone, constraint, axis, index, fcurve):
        # Get the fcurve for the specific axis rotation
        fcurve = context.active_object.animation_data.action.fcurves.find(
            'pose.bones["{}"].rotation_euler'.format(bone.name), index=index)
            
        if not fcurve:
            self.report({'INFO'}, "No animation found for the {} rotation of the active pose bone.".format(axis.upper()))
            return  # Skip this axis if no keyframes

        # Get limit values and whether limits are used
        max_limit = getattr(constraint, "max_{}".format(axis), None)
        min_limit = getattr(constraint, "min_{}".format(axis), None)
        use_limit = getattr(constraint, "use_limit_{}".format(axis), False)

        # Process limit if enabled for the axis
        if use_limit:
            # Check and process keyframes above the max limit
            if max_limit is not None:
                self.select_and_scale_keyframes(context, fcurve, max_limit, 'GREATER')
            
            # Check and process keyframes below the min limit
            if min_limit is not None:
                self.select_and_scale_keyframes(context, fcurve, min_limit, 'LESS')

    def select_and_scale_keyframes(self, fcurve, limit_value, mode):
        # Deselect all keyframes first
        for keyframe in fcurve.keyframe_points:
            keyframe.select_control_point = False
        # Select keyframes based on mode and limit value
        for keyframe in fcurve.keyframe_points:
            if (mode == 'GREATER' and keyframe.co.y > limit_value) or \
               (mode == 'LESS' and keyframe.co.y < limit_value):
                keyframe.select_control_point = True
            else:
                keyframe.select_control_point = False
        limit_value = math.degrees(limit_value)        
        print(limit_value)
        print('the limit value')
        # Set the 2D cursor position in the Graph Editor
        if mode == 'GREATER':
            bpy.context.space_data.cursor_position_y = limit_value
        elif mode == 'LESS':
            bpy.context.space_data.cursor_position_y = limit_value

        # Scale the selected keyframes
        bpy.ops.transform.resize(
            value=(1, 0, 1),
            orient_type='GLOBAL',
            constraint_axis=(False, True, False),
            mirror=False,
            use_proportional_edit=True,
            proportional_edit_falloff=self.proportional_falloff,
            proportional_size=self.proportional_size,
            use_proportional_connected=False
        )

        # Deselect all keyframes to clear the selection for the next pass
        for keyframe in fcurve.keyframe_points:
            keyframe.select_control_point = False

def register():
    bpy.utils.register_class(ScaleKeyframesToLimitNLA)

def unregister():
    bpy.utils.unregister_class(ScaleKeyframesToLimitNLA)

register()
