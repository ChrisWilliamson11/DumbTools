# Tooltip:  Copy NLA animation from one armature to another
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


def copy_nla_animation(source_armature, target_armature):
    # Ensure the source armature has NLA tracks
    if (
        not source_armature.animation_data
        or not source_armature.animation_data.nla_tracks
    ):
        print("Source armature has no NLA tracks to copy.")
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
            # Note: some attributes (like 'time') don't exist or are read-only; we skip those safely.


def main():
    selected_objects = bpy.context.selected_objects
    if len(selected_objects) != 2:
        print("Please select exactly 2 armatures.")
        return

    source_armature = bpy.context.active_object
    if not source_armature or source_armature.type != "ARMATURE":
        print("The active object is not an armature.")
        return

    target_armature = [obj for obj in selected_objects if obj != source_armature][0]
    if target_armature.type != "ARMATURE":
        print("The selected object is not an armature.")
        return

    copy_nla_animation(source_armature, target_armature)
    print(f"NLA animation copied from {source_armature.name} to {target_armature.name}")


main()
