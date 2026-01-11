# Tooltip:  Copy NLA animation from active armature to all other selected armatures
import bpy


def _safe_set(obj, attr, value):
    if hasattr(obj, attr):
        try:
            setattr(obj, attr, value)
        except Exception:
            pass


def _copy_attrs(dst, src, attrs):
    for a in attrs:
        if hasattr(src, a) and hasattr(dst, a):
            try:
                setattr(dst, a, getattr(src, a))
            except Exception:
                pass



def _copy_influence_keyframes(dst_strip, src_strip):
    """Copy animated influence keyframes from src_strip to dst_strip.

    Prefer src_strip.fcurves (strip-local FCurves); fall back to owner's action.
    Insert on destination via keyframe_insert so Blender creates the FCurve
    at the correct data_path.
    """
    if dst_strip is None or src_strip is None:
        return

    # Owning IDs (Objects/Armatures)
    src_id = getattr(src_strip, "id_data", None)
    dst_id = getattr(dst_strip, "id_data", None)
    if src_id is None or dst_id is None:
        return

    # Resolve RNA paths (best-effort; useful for matching and cleanup)
    src_path = None
    dst_path = None
    try:
        src_path = src_strip.path_from_id("influence")
    except Exception:
        pass
    try:
        dst_path = dst_strip.path_from_id("influence")
    except Exception:
        pass

    # Locate source FCurve from strip.fcurves first
    src_fc = None
    try:
        strip_fcurves = getattr(src_strip, "fcurves", None)
        if strip_fcurves:
            if src_path:
                for fc in strip_fcurves:
                    dp = getattr(fc, "data_path", "")
                    ai = getattr(fc, "array_index", 0)
                    if dp == src_path and ai == 0:
                        src_fc = fc
                        break
            if src_fc is None:
                for fc in strip_fcurves:
                    dp = getattr(fc, "data_path", "")
                    ai = getattr(fc, "array_index", 0)
                    if dp.endswith("influence") and ai == 0:
                        src_fc = fc
                        break
    except Exception:
        pass

    # Fallback: search in the owner's action
    if src_fc is None:
        src_anim = getattr(src_id, "animation_data", None)
        src_action = getattr(src_anim, "action", None) if src_anim else None
        if src_action:
            try:
                if src_path:
                    src_fc = src_action.fcurves.find(src_path, index=0)
            except Exception:
                src_fc = None
            if src_fc is None:
                try:
                    for fc in src_action.fcurves:
                        if getattr(fc, "array_index", 0) != 0:
                            continue
                        dp = getattr(fc, "data_path", "")
                        if dp.endswith("influence"):
                            if src_path and dp != src_path:
                                continue
                            src_fc = fc
                            break
                except Exception:
                    pass

    # Nothing to copy if no source keys
    if not src_fc or len(getattr(src_fc, "keyframe_points", [])) == 0:
        return

    # Ensure destination has anim data; enable animated influence
    try:
        if not getattr(dst_id, "animation_data", None):
            dst_id.animation_data_create()
    except Exception:
        pass
    _safe_set(dst_strip, "use_animated_influence", True)

    # Clear existing destination influence keys if present (prefer strip.fcurves)
    try:
        dst_fc_existing = None
        dst_strip_fcurves = getattr(dst_strip, "fcurves", None)
        if dst_strip_fcurves:
            # Match by exact path first
            if dst_path:
                for fc in dst_strip_fcurves:
                    dp = getattr(fc, "data_path", "")
                    ai = getattr(fc, "array_index", 0)
                    if dp == dst_path and ai == 0:
                        dst_fc_existing = fc
                        break
            # Fallback by suffix match
            if dst_fc_existing is None:
                for fc in dst_strip_fcurves:
                    dp = getattr(fc, "data_path", "")
                    ai = getattr(fc, "array_index", 0)
                    if dp.endswith("influence") and ai == 0:
                        dst_fc_existing = fc
                        break
        if dst_fc_existing:
            try:
                for i in range(len(dst_fc_existing.keyframe_points) - 1, -1, -1):
                    dst_fc_existing.keyframe_points.remove(
                        dst_fc_existing.keyframe_points[i]
                    )
                dst_fc_existing.update()
            except Exception:
                pass
    except Exception:
        pass

    # Insert destination keys at the same frames/values
    for kp in list(src_fc.keyframe_points):
        frame = float(kp.co[0])
        value = float(kp.co[1])
        try:
            dst_strip.influence = value
        except Exception:
            pass
        try:
            dst_strip.keyframe_insert(data_path="influence", frame=frame)
        except Exception:
            pass

    # Mirror interpolation, easing, and handles on the created dest fcurve
    dst_fc = None
    try:
        dst_strip_fcurves = getattr(dst_strip, "fcurves", None)
        if dst_strip_fcurves:
            if dst_path:
                for fc in dst_strip_fcurves:
                    if getattr(fc, "data_path", "") == dst_path and getattr(fc, "array_index", 0) == 0:
                        dst_fc = fc
                        break
            if dst_fc is None:
                for fc in dst_strip_fcurves:
                    if getattr(fc, "data_path", "").endswith("influence") and getattr(fc, "array_index", 0) == 0:
                        dst_fc = fc
                        break
    except Exception:
        dst_fc = None

    if dst_fc and len(dst_fc.keyframe_points) == len(src_fc.keyframe_points):
        for i, kp in enumerate(src_fc.keyframe_points):
            dkp = dst_fc.keyframe_points[i]
            _safe_set(
                dkp,
                "interpolation",
                getattr(kp, "interpolation", getattr(dkp, "interpolation", None)),
            )
            if hasattr(kp, "easing"):
                _safe_set(dkp, "easing", getattr(kp, "easing", getattr(dkp, "easing", None)))
            for attr in ("handle_left_type", "handle_right_type"):
                if hasattr(kp, attr):
                    _safe_set(dkp, attr, getattr(kp, attr))
            try:
                dkp.handle_left = kp.handle_left
                dkp.handle_right = kp.handle_right
            except Exception:
                try:
                    dkp.handle_left[0] = kp.handle_left[0]
                    dkp.handle_left[1] = kp.handle_left[1]
                    dkp.handle_right[0] = kp.handle_right[0]
                    dkp.handle_right[1] = kp.handle_right[1]
                except Exception:
                    pass
        try:
            dst_fc.update()
        except Exception:
            pass


def copy_nla_animation(source_armature, target_armature):
    # Ensure the source armature has NLA tracks
    if (
        not source_armature.animation_data
        or not source_armature.animation_data.nla_tracks
    ):
        # print("Source armature has no NLA tracks to copy.")
        return

    # Make sure the target has animation data, but DO NOT clear it (preserve drivers, actions, etc.)
    if not target_armature.animation_data:
        target_armature.animation_data_create()

    # Remove only NLA tracks from the target (keep drivers and other animation data intact)
    if target_armature.animation_data and target_armature.animation_data.nla_tracks:
        for tr in list(target_armature.animation_data.nla_tracks):
            target_armature.animation_data.nla_tracks.remove(tr)

    # Copy each NLA track from the source to the target armature
    for track in source_armature.animation_data.nla_tracks:
        new_track = target_armature.animation_data.nla_tracks.new()
        new_track.name = track.name

        # Copy common NLA track flags when available
        _copy_attrs(
            new_track,
            track,
            [
                "is_solo",  # Solo flag (newer Blender versions)
                "mute",
                "lock",
                "select",
            ],
        )
        # Older Blender versions may use 'solo' instead of 'is_solo'
        if hasattr(track, "solo") and hasattr(new_track, "solo"):
            _safe_set(new_track, "solo", getattr(track, "solo"))



        # Copy the strips within the track
        for strip in track.strips:
            # Create the new strip with basic required args
            new_strip = new_track.strips.new(
                name=strip.name,
                start=int(strip.frame_start),  # Start must be numeric; int is safest
                action=strip.action,
            )

            # Try to match placement and timing as closely as possible
            _safe_set(
                new_strip,
                "frame_start",
                float(getattr(strip, "frame_start", new_strip.frame_start)),
            )
            _safe_set(
                new_strip,
                "frame_end",
                float(getattr(strip, "frame_end", new_strip.frame_end)),
            )

            # Action sub-frame range
            _safe_set(
                new_strip,
                "action_frame_start",
                getattr(strip, "action_frame_start", new_strip.action_frame_start),
            )
            _safe_set(
                new_strip,
                "action_frame_end",
                getattr(strip, "action_frame_end", new_strip.action_frame_end),
            )

            # Strip length controls
            _safe_set(new_strip, "scale", getattr(strip, "scale", new_strip.scale))
            _safe_set(new_strip, "repeat", getattr(strip, "repeat", new_strip.repeat))

            # Blend settings
            _safe_set(
                new_strip, "blend_in", getattr(strip, "blend_in", new_strip.blend_in)
            )
            _safe_set(
                new_strip, "blend_out", getattr(strip, "blend_out", new_strip.blend_out)
            )
            _safe_set(
                new_strip,
                "blend_type",
                getattr(strip, "blend_type", getattr(new_strip, "blend_type", None)),
            )
            _safe_set(
                new_strip,
                "extrapolation",
                getattr(
                    strip, "extrapolation", getattr(new_strip, "extrapolation", None)
                ),
            )

            # Influence and time animation flags
            _safe_set(
                new_strip,
                "use_animated_influence",
                getattr(
                    strip,
                    "use_animated_influence",
                    getattr(new_strip, "use_animated_influence", False),
                ),
            )
            _safe_set(
                new_strip,
                "use_animated_time",
                getattr(
                    strip,
                    "use_animated_time",
                    getattr(new_strip, "use_animated_time", False),
                ),
            )
            _safe_set(
                new_strip,
                "influence",
                getattr(strip, "influence", getattr(new_strip, "influence", 1.0)),
            )

            # Misc

            # Copy animated influence FCurve (if the source has one)
            _copy_influence_keyframes(new_strip, strip)

            _safe_set(
                new_strip,
                "mute",
                getattr(strip, "mute", getattr(new_strip, "mute", False)),
            )
            _safe_set(
                new_strip,
                "select",
                getattr(strip, "select", getattr(new_strip, "select", False)),
            )
            # Note: some attributes (like 'time') don't exist
            # or are read-only; we skip those safely.


def main():
    """Copy NLA tracks from the active Armature to all other selected Armatures.

    Usage: Make the source Armature active, shift-select target Armatures, run script.
    """
    ctx = bpy.context
    source_armature = ctx.active_object

    if not source_armature or source_armature.type != "ARMATURE":
        print("Active object must be an Armature (source).")
        return

    selected_objects = ctx.selected_objects or []
    targets = [obj for obj in selected_objects if obj.type == "ARMATURE" and obj != source_armature]

    if not targets:
        print("Select one or more target armatures in addition to the active source.")
        return

    for target in targets:
        copy_nla_animation(source_armature, target)
        # print(f"NLA animation copied from {source_armature.name} to {target.name}")


main()
