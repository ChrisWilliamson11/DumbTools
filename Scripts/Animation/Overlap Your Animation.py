# Tooltip:  Offset the keyframes of all selected objects by the specified amount of frames. Overlap mode instead lets you specify an overlap from one object to the next. If you enable the Noise option, it will add some random variation to the offset amount. If you enable the Remove Offset option, it will align all actions to frame 0.
import bpy
import random

def iter_fcurves(action):
    """
    Yields fcurves from an Action, handling both Legacy Blender and Blender 5+ Layered Animation.
    """
    if not action:
        return
    # Legacy: Direct fcurves list
    if hasattr(action, "fcurves") and action.fcurves:
        for fc in action.fcurves:
            yield fc
    # Blender 5+: Layers and Strips
    if hasattr(action, "layers"):
        for layer in action.layers:
            if hasattr(layer, "strips"):
                for strip in layer.strips:
                    if hasattr(strip, "channelbags"):
                         for bag in strip.channelbags:
                             if hasattr(bag, "fcurves"):
                                 for fc in bag.fcurves:
                                     yield fc
                    # Fallback for other structures (legacy transition or direct strips)
                    if hasattr(strip, "fcurves"):
                        for fc in strip.fcurves:
                            yield fc
                    elif hasattr(strip, "channels"):
                         for fc in strip.channels:
                             yield fc

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

    selected_only: bpy.props.BoolProperty(
        name="Selected Keys Only",
        description="Affect only selected keyframes in Actions and NLA Influence curves",
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
        layout.prop(self, "selected_only")

    def execute(self, context):
        entities = []
        if context.mode == 'POSE' and context.selected_pose_bones:
            for bone in context.selected_pose_bones:
                obj = bone.id_data
                if getattr(obj, "animation_data", None):
                    entities.append({'type': 'BONE', 'bone': bone, 'object': obj})
        else:
            for o in context.selected_objects:
                if getattr(o, "animation_data", None):
                    entities.append({'type': 'OBJECT', 'object': o})

        if not entities:
            self.report({'INFO'}, "No animated objects or bones found to offset.")
            return {'CANCELLED'}

        def fcurve_belongs_to_entity(fc, entity):
            if entity['type'] == 'OBJECT':
                return True
            elif entity['type'] == 'BONE':
                dp = getattr(fc, "data_path", "")
                bone_name = entity['bone'].name
                prefix1 = f'pose.bones["{bone_name}"]'
                prefix2 = f"pose.bones['{bone_name}']"
                return dp.startswith(prefix1) or dp.startswith(prefix2)
            return False

        def get_anim_range(entity, selected_only=False):
            obj = entity['object']
            ad = getattr(obj, "animation_data", None)
            if not ad:
                return None
            start = float("inf")
            end = float("-inf")
            found = False

            def _key_selected(kp):
                return bool(
                    getattr(kp, "select_control_point", getattr(kp, "select", False))
                    or getattr(kp, "select_left_handle", False)
                    or getattr(kp, "select_right_handle", False)
                )

            def _update_from_action(act):
                nonlocal start, end, found
                if not act:
                    return
                if entity['type'] == 'OBJECT' and not selected_only:
                    try:
                        s = float(act.frame_range[0])
                        e = float(act.frame_range[1])
                        start = min(start, s)
                        end = max(end, e)
                        found = True
                    except Exception:
                        pass
                else:
                    for fcu in iter_fcurves(act):
                        if not fcurve_belongs_to_entity(fcu, entity):
                            continue
                        for kp in getattr(fcu, "keyframe_points", []) or []:
                            if selected_only and not _key_selected(kp):
                                continue
                            found = True
                            f = float(kp.co[0])
                            start = min(start, f)
                            end = max(end, f)

            def _update_from_nla(ad):
                nonlocal start, end, found
                if entity['type'] == 'BONE':
                    return
                for tr in getattr(ad, "nla_tracks", []) or []:
                    for st in getattr(tr, "strips", []) or []:
                        fc_list = getattr(st, "fcurves", None)
                        if not fc_list:
                            continue
                        for fc in fc_list:
                            dp = getattr(fc, "data_path", "")
                            if not dp.endswith("influence"):
                                continue
                            for kp in getattr(fc, "keyframe_points", []) or []:
                                if selected_only and not _key_selected(kp):
                                    continue
                                found = True
                                f = float(kp.co[0])
                                start = min(start, f)
                                end = max(end, f)

            act = getattr(ad, "action", None)
            _update_from_action(act)
            _update_from_nla(ad)

            if not found:
                return None
            return start, end

        def shift_action_keys(entity, act, delta, selected_only=False):
            if not act:
                return
            for fcu in iter_fcurves(act):
                if not fcurve_belongs_to_entity(fcu, entity):
                    continue
                for k in fcu.keyframe_points:
                    if selected_only:
                        if not (
                            getattr(k, "select_control_point", getattr(k, "select", False))
                            or getattr(k, "select_left_handle", False)
                            or getattr(k, "select_right_handle", False)
                        ):
                            continue
                    k.co[0] += delta
                    k.handle_left[0] += delta
                    k.handle_right[0] += delta

        def shift_nla_influence_keys(entity, delta, selected_only=False):
            if entity['type'] == 'BONE':
                return
            obj = entity['object']
            ad = getattr(obj, "animation_data", None)
            if not ad:
                return
            for tr in getattr(ad, "nla_tracks", []) or []:
                for st in getattr(tr, "strips", []) or []:
                    fc_list = getattr(st, "fcurves", None)
                    if not fc_list:
                        continue
                    for fc in fc_list:
                        dp = getattr(fc, "data_path", "")
                        if dp.endswith("influence") and getattr(fc, "array_index", 0) == 0:
                            for k in getattr(fc, "keyframe_points", []) or []:
                                if selected_only:
                                    if not (
                                        getattr(k, "select_control_point", getattr(k, "select", False))
                                        or getattr(k, "select_left_handle", False)
                                        or getattr(k, "select_right_handle", False)
                                    ):
                                        continue
                                k.co[0] += delta
                                k.handle_left[0] += delta
                                k.handle_right[0] += delta
                            try:
                                fc.update()
                            except Exception:
                                pass

        prev_end = 0.0

        for i, entity in enumerate(entities):
            obj = entity['object']
            ad = getattr(obj, "animation_data", None)
            act = getattr(ad, "action", None) if ad else None
            rng = get_anim_range(entity, self.selected_only)
            if rng is None:
                continue
            start, end = rng

            # Apply noise for each object/bone
            current_noise = random.uniform(-self.noise, self.noise)

            # If 'Remove Offset' is checked, align keys to frame 0
            if self.reset:
                delta = -start
            elif self.use_overlap:
                if i == 0:
                    delta = current_noise
                else:
                    delta = prev_end - start - self.offset + current_noise
                prev_end = end + delta - current_noise
            else:
                delta = self.offset * i + current_noise

            shift_action_keys(entity, act, delta, self.selected_only)
            shift_nla_influence_keys(entity, delta, self.selected_only)

        return {'FINISHED'}

    def invoke(self, context, event):
        return context.window_manager.invoke_props_dialog(self)

def register():
    # Check if the class is already registered
    if "OffsetAnimationOperator" not in bpy.types.Operator.__subclasses__():
        bpy.utils.register_class(OffsetAnimationOperator)
    else:
        # print("OffsetAnimationOperator is already registered")
        pass


def unregister():
    if "OffsetAnimationOperator" in bpy.types.Operator.__subclasses__():
        bpy.utils.unregister_class(OffsetAnimationOperator)


register()

bpy.ops.object.offset_animation('INVOKE_DEFAULT')
