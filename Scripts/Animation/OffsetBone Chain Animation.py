# Tooltip:  offset the animation on a bone chain
import bpy


def iter_fcurves(action):
    """Yield all fcurves from an action, supporting both legacy and layered actions."""
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


def is_bone_selected(pose_bone):
    """Check if a pose bone is selected (Blender 4.x and 5.x compatible)."""
    if hasattr(pose_bone, 'select'):
        return pose_bone.select
    if hasattr(pose_bone, 'bone') and hasattr(pose_bone.bone, 'select'):
        return pose_bone.bone.select
    return False


def get_hierarchy_depth(pose_bone):
    """Get the depth of a bone in the full armature hierarchy."""
    depth = 0
    current = pose_bone
    while current.parent:
        depth += 1
        current = current.parent
    return depth


def find_chain_root(pose_bone, selected_set):
    """Walk up parents to find the topmost selected ancestor."""
    root = pose_bone
    current = pose_bone.parent
    while current:
        if current in selected_set:
            root = current
        current = current.parent
    return root


def group_into_chains(selected_bones):
    """Group selected bones into independent hierarchy chains, sorted by depth."""
    selected_set = set(selected_bones)
    chains = {}
    for bone in selected_bones:
        root = find_chain_root(bone, selected_set)
        if root not in chains:
            chains[root] = []
        chains[root].append(bone)
    # Sort each chain by hierarchy depth
    for root in chains:
        chains[root].sort(key=lambda b: get_hierarchy_depth(b))
    return chains


class OBJECT_OT_OffsetKeyframesOperator(bpy.types.Operator):
    bl_label = "Offset Bone Chain Animation"
    bl_idname = "object.offset_keyframes_operator"

    offset_amount: bpy.props.FloatProperty(name="Offset Amount", default=1.0)
    offset_direction: bpy.props.EnumProperty(
        name="Direction",
        items=[
            ('FORWARD', "Forward", "Offset keys from parent to child"),
            ('REVERSE', "Reverse", "Offset keys from child to parent"),
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
            if obj.type != 'ARMATURE':
                continue
            if not obj.animation_data or not obj.animation_data.action:
                continue

            action = obj.animation_data.action
            selected_bones = [pb for pb in obj.pose.bones if is_bone_selected(pb)]

            if not selected_bones:
                self.report({'WARNING'}, f"No selected bones on '{obj.name}'")
                continue

            # Determine sign and direction
            sign = -1.0 if direction in ('REMOVE_FORWARD', 'REMOVE_REVERSE') else 1.0
            reverse = direction in ('REVERSE', 'REMOVE_REVERSE')

            self.offset_bone_keyframes(action, selected_bones, offset_amount * sign, reverse)

        return {'FINISHED'}

    def offset_bone_keyframes(self, action, selected_bones, offset_amount, reverse):
        """Apply offset per bone based on chain position."""
        chains = group_into_chains(selected_bones)

        for root, chain_bones in chains.items():
            if reverse:
                chain_bones = chain_bones[::-1]

            for chain_index, bone in enumerate(chain_bones):
                if chain_index == 0:
                    # Root of each chain gets no offset
                    continue

                offset = offset_amount * chain_index

                for fcurve in iter_fcurves(action):
                    # Precise match: only fcurves belonging to this exact bone
                    if f'pose.bones["{bone.name}"]' not in fcurve.data_path:
                        continue
                    for keyframe in fcurve.keyframe_points:
                        if keyframe.select_control_point:
                            keyframe.co.x += offset
                            keyframe.handle_left.x += offset
                            keyframe.handle_right.x += offset


def register():
    bpy.utils.register_class(OBJECT_OT_OffsetKeyframesOperator)

def unregister():
    bpy.utils.unregister_class(OBJECT_OT_OffsetKeyframesOperator)


register()


bpy.ops.object.offset_keyframes_operator('INVOKE_DEFAULT')
