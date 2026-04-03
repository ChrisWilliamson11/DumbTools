import bpy
import re

# Regex to capture the bone name from data paths like: pose.bones["BoneName"].something
BONE_PATH_RE = re.compile(r'^pose\.bones\["((?:[^"\\]|\\.)*)"\]')


def _unescape_blender_string(s: str) -> str:
    # Blender stores quotes as \" inside data paths; this decodes common escapes.
    try:
        return bytes(s, "utf-8").decode("unicode_escape")
    except Exception:
        return s.replace('\\"', '"').replace("\\\\", "\\")


def actions_from_nla(obj):
    acts = set()
    ad = obj.animation_data
    if not ad:
        return acts
    for track in ad.nla_tracks:
        for strip in track.strips:
            act = getattr(strip, "action", None)
            if act:
                acts.add(act)
    return acts


def cleanup_action_groups_for_bones(action):
    reassigned = 0
    created = 0
    removed = 0

    # Cache groups by name for quick lookup
    group_cache = {g.name: g for g in action.groups}

    # Ensure every bone-related F-Curve is in an Action Group named after that bone
    for fc in action.fcurves:
        dp = fc.data_path or ""
        m = BONE_PATH_RE.match(dp)
        if not m:
            continue  # Not a pose bone channel, ignore
        raw_name = m.group(1)
        bone_name = _unescape_blender_string(raw_name)

        grp = group_cache.get(bone_name)
        if not grp:
            grp = action.groups.new(bone_name)
            group_cache[bone_name] = grp
            created += 1

        if fc.group != grp:
            fc.group = grp
            reassigned += 1

    # Remove groups that ended up empty after reassignments
    # (ActionGroup collection supports remove(group) )
    for g in list(action.groups):
        if not any(fc.group == g for fc in action.fcurves):
            action.groups.remove(g)
            removed += 1

    print(
        f'[Cleanup] Action "{action.name}": reassigned={reassigned}, created_groups={created}, removed_empty_groups={removed}'
    )
    return reassigned, created, removed


def main():
    obj = bpy.context.active_object
    if not obj or obj.type != "ARMATURE":
        raise RuntimeError("Select an Armature object that has NLA strips.")

    actions = actions_from_nla(obj)
    if not actions:
        print("[Cleanup] No Actions found in NLA tracks on the selected Armature.")
        return

    total_stats = [0, 0, 0]
    for act in sorted(actions, key=lambda a: a.name.lower()):
        stats = cleanup_action_groups_for_bones(act)
        total_stats = [a + b for a, b in zip(total_stats, stats)]

    print(
        f"[Cleanup] Done. Reassigned {total_stats[0]} F-Curves, "
        f"created {total_stats[1]} groups, removed {total_stats[2]} empty groups "
        f"across {len(actions)} action(s)."
    )


main()
