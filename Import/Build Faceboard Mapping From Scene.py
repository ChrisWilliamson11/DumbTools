# Build Faceboard Mapping From Scene
# Generates a JSON mapping from object-based faceboard controls (CTRL_*) to
# bones on an armature-based faceboard. Uses fuzzy matching with sensible
# defaults and writes:
#   {
#     "CTRL_L_mouth_upperLipRaise.001": {
#       "bone": "CTRL_L_mouth_upperLipRaise",
#       "transform": "AUTO"
#     },
#     ...
#   }
#
# Notes:
# - "transform": "AUTO" preserves each driver's original transform axis/type
#   when you rewire (e.g., LOC_X, LOC_Y, ROT_Z). Use "AUTO" for multi-axis drivers.
# - You can manually edit any "bone" or "transform" values in the output JSON.
# - The script expects:
#     - An armature (active or selected), and
#     - One or more selected root objects for the object-based faceboard (e.g. CTRL_faceGUI.001).
#
# Usage:
# - Select your armature (or set ARMATURE_NAME below).
# - Select the root object(s) for your object-based controls (or set CONTROL_ROOTS).
# - Run this script. It writes //faceboard_mapping_auto.json next to your .blend.

import bpy
import json
import re
import difflib
from collections import defaultdict

# ------------- Configuration -------------
ARMATURE_NAME = "Faceboard"  # e.g., "Faceboard"; if None, uses active or any selected armature
CONTROL_ROOTS = []  # e.g., ["CTRL_faceGUI.001"]; if empty, use selected objects as roots

# Where to write the mapping JSON (relative to the .blend by default)
OUTPUT_PATH = bpy.path.abspath(r"G:\faceboard_mapping_auto.json")

# Only CTRL_* objects will be mapped by default. You can extend this if needed.
CONTROL_NAME_PREFIX = "CTRL_"

# Known prefixes to strip for tokenization (does not affect actual mapping keys)
KNOWN_PREFIXES = ("CTRL_", "FRM_", "GRP_", "TEXT_", "LOC_")

# Confidence threshold for accepting fuzzy matches (increase to be more strict)
CONFIDENCE_THRESHOLD = 40.0
# ----------------------------------------


def get_armature():
    """Find the armature to target."""
    if ARMATURE_NAME:
        arm = bpy.data.objects.get(ARMATURE_NAME)
        if arm and arm.type == "ARMATURE":
            return arm
        raise ValueError(f"Armature '{ARMATURE_NAME}' not found or not an Armature")

    obj = bpy.context.active_object
    if obj and obj.type == "ARMATURE":
        return obj

    for o in bpy.context.selected_objects or []:
        if o.type == "ARMATURE":
            return o

    for o in bpy.data.objects:
        if o.type == "ARMATURE":
            return o

    raise ValueError("No armature found. Select an armature or set ARMATURE_NAME.")


def get_control_roots():
    """Resolve root objects for the object-based control hierarchy."""
    if CONTROL_ROOTS:
        roots = []
        for n in CONTROL_ROOTS:
            ob = bpy.data.objects.get(n)
            if ob:
                roots.append(ob)
        if not roots:
            raise ValueError(
                "CONTROL_ROOTS not found. Please correct the names or select roots."
            )
        return roots

    roots = [
        o
        for o in (bpy.context.selected_objects or [])
        if o.type in {"MESH", "EMPTY", "CURVE", "SURFACE", "FONT"}
    ]
    if not roots:
        raise ValueError(
            "Select root object(s) for object-based controls, or set CONTROL_ROOTS."
        )
    return roots


def strip_numeric_suffix(name: str) -> str:
    """Remove trailing .001, .002, ..."""
    return re.sub(r"\.\d+$", "", name)


def detect_side(name: str):
    """
    Try to extract side markers: L/R/C.
    Example: CTRL_L_mouth_upperLipRaise -> 'L'
    """
    base = strip_numeric_suffix(name)
    parts = base.split("_")
    # Common convention: one token is exactly 'L', 'R', or 'C'
    for p in parts:
        if p in {"L", "R", "C"}:
            return p
    # MetaHuman style can include FACIAL_L / FACIAL_R
    if "FACIAL_L" in base:
        return "L"
    if "FACIAL_R" in base:
        return "R"
    return None


def tokenize(name: str):
    """Convert a name into tokens for fuzzy comparison, dropping common control prefixes."""
    base = strip_numeric_suffix(name)
    base = base.replace("__", "_")
    parts = [p for p in base.split("_") if p]
    drop = {"CTRL", "FRM", "GRP", "TEXT", "LOC"}
    tokens = [p for p in parts if p not in drop]
    return [t.lower() for t in tokens]


def collect_control_objects(roots):
    """Collect all control objects under the provided roots matching CONTROL_NAME_PREFIX."""
    found = []

    def rec(o):
        # Only map controls that start with the control prefix
        if o.name.startswith(CONTROL_NAME_PREFIX):
            found.append(o)
        for c in o.children:
            rec(c)

    for r in roots:
        rec(r)

    # Deduplicate by identity (objects are unique anyway)
    return list(dict.fromkeys(found))


def collect_bone_names(arm):
    """Return a set of bone names from the armature."""
    return {b.name for b in arm.data.bones}


def score_match(ctrl_base: str, bone_name: str) -> float:
    """
    Score how well a control base name matches a bone name.
    Components:
      - Exact match bonus
      - Side match bonus
      - Token Jaccard overlap
      - Sequence similarity
    """
    s = 0.0

    # Exact base name match
    if ctrl_base == bone_name:
        s += 100.0

    # Side check
    side_c = detect_side(ctrl_base)
    side_b = detect_side(bone_name)
    if side_c and side_b and side_c == side_b:
        s += 10.0

    # Token overlap
    t_ctrl = set(tokenize(ctrl_base))
    t_bone = set(tokenize(bone_name))
    if t_ctrl and t_bone:
        inter = len(t_ctrl & t_bone)
        union = len(t_ctrl | t_bone)
        jacc = inter / union if union else 0.0
        s += jacc * 20.0

    # Sequence similarity
    s += (
        difflib.SequenceMatcher(None, ctrl_base.lower(), bone_name.lower()).ratio()
        * 50.0
    )

    return s


def build_mapping(arm, roots):
    """
    Build the mapping dict:
      control_object_name -> {"bone": <bone_name or "">, "transform": "AUTO"}
    """
    bones = collect_bone_names(arm)
    controls = collect_control_objects(roots)

    bones_by_base = {strip_numeric_suffix(b): b for b in bones}
    bone_list = sorted(list(bones))

    mapping = {}
    stats = defaultdict(int)
    unresolved = []

    for ob in controls:
        ctrl_name = ob.name
        ctrl_base = strip_numeric_suffix(ctrl_name)

        # 1) Prefer exact base name matches (common in your data).
        if ctrl_base in bones_by_base:
            mapping[ctrl_name] = {"bone": bones_by_base[ctrl_base], "transform": "AUTO"}
            stats["direct"] += 1
            continue

        # 2) Fuzzy match for less direct cases.
        best = None
        best_score = -1e9
        for bn in bone_list:
            sc = score_match(ctrl_base, bn)
            if sc > best_score:
                best_score = sc
                best = bn

        if best and best_score >= CONFIDENCE_THRESHOLD:
            mapping[ctrl_name] = {"bone": best, "transform": "AUTO"}
            stats["fuzzy"] += 1
        else:
            mapping[ctrl_name] = {"bone": "", "transform": "AUTO"}
            unresolved.append((ctrl_name, best, round(best_score, 1)))
            stats["unresolved"] += 1

    return mapping, stats, unresolved


def main():
    arm = get_armature()
    roots = get_control_roots()
    mapping, stats, unresolved = build_mapping(arm, roots)

    with open(OUTPUT_PATH, "w", encoding="utf-8") as f:
        json.dump(mapping, f, indent=2)

    print(f"[Build Mapping] Armature: {arm.name}")
    print(f"[Build Mapping] Roots: {[r.name for r in roots]}")
    print(f"[Build Mapping] Wrote {len(mapping)} entries to: {OUTPUT_PATH}")
    print(
        f"[Build Mapping] Direct matches: {stats['direct']}, Fuzzy: {stats['fuzzy']}, Unresolved: {stats['unresolved']}"
    )

    if unresolved:
        print(
            "[Build Mapping] Unresolved or low-confidence matches (control, best_candidate, score):"
        )
        for c, b, s in unresolved[:50]:  # show first 50
            print("  ", c, "->", b, f"(score: {s})")
        if len(unresolved) > 50:
            print(f"  ... and {len(unresolved) - 50} more")


main()
