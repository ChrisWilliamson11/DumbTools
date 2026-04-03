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
        # Include objects that have any animation data (Action and/or NLA)
        objs = [o for o in context.selected_objects if getattr(o, "animation_data", None)]
        # print(f"Number of animated objects: {len(objs)}")  # silenced

        if not objs:
            self.report({'INFO'}, "No animated objects found to offset.")
            return {'CANCELLED'}

        def get_anim_range(obj, selected_only=False):
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
                if selected_only:
                    for fcu in getattr(act, "fcurves", []) or []:
                        for kp in getattr(fcu, "keyframe_points", []) or []:
                            if _key_selected(kp):
                                found = True
                                f = float(kp.co[0])
                                start = min(start, f)
                                end = max(end, f)
                else:
                    try:
                        s = float(act.frame_range[0])
                        e = float(act.frame_range[1])
                        start = min(start, s)
                        end = max(end, e)
                        found = True
                    except Exception:
                        pass

            def _update_from_nla(ad):
                nonlocal start, end, found
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

        def shift_action_keys(act, delta, selected_only=False):
            if not act or not act.fcurves:
                return
            for fcu in act.fcurves:
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

        def shift_nla_influence_keys(obj, delta, selected_only=False):
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

        for i, o in enumerate(objs):
            ad = getattr(o, "animation_data", None)
            act = getattr(ad, "action", None) if ad else None
            rng = get_anim_range(o, self.selected_only)
            if rng is None:
                # If selected_only, skip objects with no selected keys
                # If not selected_only but no range found, skip as well
                continue
            start, end = rng

            # Apply noise for each object
            current_noise = random.uniform(-self.noise, self.noise)

            # If 'Remove Offset' is checked, align keys to frame 0 (uses selected range if enabled)
            if self.reset:
                delta = -start
            elif self.use_overlap:
                if i == 0:
                    # First object is only affected by noise
                    delta = current_noise
                else:
                    # Start current object's anim 'overlap' frames before previous end
                    delta = prev_end - start - self.offset + current_noise
                # Update the end frame for the next iteration (remove noise so it doesn't accumulate)
                prev_end = end + delta - current_noise
            else:
                # Original offset logic with noise added for each object
                delta = self.offset * i + current_noise

            # Shift Action keys (if any)
            shift_action_keys(act, delta, self.selected_only)
            # Also shift NLA Influence keys (if any)
            shift_nla_influence_keys(o, delta, self.selected_only)

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
