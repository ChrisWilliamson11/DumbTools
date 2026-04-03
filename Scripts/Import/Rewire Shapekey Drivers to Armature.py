# Rewire Shapekey Drivers to Armature
# -----------------------------------
# This utility rewires shapekey drivers that currently target object-based
# faceboard controls (e.g., CTRL_* meshes/empties) to an armature-based
# faceboard (bones), preserving per-variable transform axes when desired.
#
# Features
# - Reads a mapping JSON of control object -> {"bone": "<bone>", "transform": "AUTO|LOC_X|LOC_Y|LOC_Z|ROT_*|SCALE_*", "space": "LOCAL_SPACE|WORLD_SPACE|TRANSFORM|..."}
# - "transform": "AUTO" preserves the original driver variable's transform_type (e.g., LOC_X vs LOC_Y) per-variable.
# - Preserves transform_space if not overridden by mapping.
# - Detailed reporting of rewired variables, warnings for missing bones, and summary counts.
# - DRY_RUN mode to preview changes without writing.
#
# Expected JSON format (examples):
# {
#   "CTRL_L_mouth_upperLipRaise.001": { "bone": "CTRL_L_mouth_upperLipRaise", "transform": "AUTO" },
#   "CTRL_R_mouth_cornerDepress.001": { "bone": "CTRL_R_mouth_cornerDepress", "transform": "LOC_Y" },
#   "CTRL_swallow.001": { "bone": "CTRL_C_neck_swallow", "transform": "AUTO", "space": "LOCAL_SPACE" }
# }
#
# Usage
# - Set ARMATURE_NAME or make the target armature the active object (or selected).
# - Set MAPPING_PATH to your mapping file (e.g., produced by "Build Faceboard Mapping From Scene").
# - Select the mesh objects whose shapekey drivers you want to rewire (or set ONLY_SELECTED=False to process all meshes).
# - Run the script.
#
# Notes
# - The script rewires driver variables of shape key value FCurves (data_path = key_blocks["..."].value).
# - It looks for variables that target control objects whose names are keys in the mapping JSON.
# - For each such variable, it switches it to TRANSFORMS and points it to the configured armature:bone with the chosen transform.
# - If a control drives multiple things on different axes, keep "transform": "AUTO" so each variable keeps its axis.

import bpy
import json
import re
from typing import Dict, Any, Tuple, Optional, Set

# ------------- Configuration -------------
ARMATURE_NAME: Optional[str] = (
    "Faceboard"  # e.g. "Faceboard"; if None, uses active or any selected armature
)
MAPPING_PATH: str = bpy.path.abspath(
    r"G:\faceboard_mapping_auto.json"
)  # path to your mapping JSON
ONLY_SELECTED: bool = (
    True  # True: process only selected meshes. False: process all meshes in the scene.
)
DRY_RUN: bool = False  # True: preview changes without writing
# ----------------------------------------


def _strip_numeric_suffix(name: str) -> str:
    """Remove trailing .001, .002, ..."""
    return re.sub(r"\.\d+$", "", name)


def _get_armature() -> bpy.types.Object:
    """Resolve the armature to target."""
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

    # Fallback to first armature in the file
    for o in bpy.data.objects:
        if o.type == "ARMATURE":
            return o

    raise ValueError("No armature found. Select an Armature or set ARMATURE_NAME.")


def _load_mapping(path: str) -> Dict[str, Dict[str, Any]]:
    """Load mapping and normalize values. Accepts 'bone' as str and optional 'transform' (default AUTO), 'space' (optional)."""
    with open(path, "r", encoding="utf-8") as f:
        raw = json.load(f)

    mapping: Dict[str, Dict[str, Any]] = {}
    for key, val in raw.items():
        if isinstance(val, str):
            mapping[key] = {"bone": val, "transform": "AUTO"}
        elif isinstance(val, dict):
            bone = val.get("bone", "")
            transform = (val.get("transform") or "AUTO").upper()
            space = val.get(
                "space"
            )  # keep as-is; Blender expects values like 'LOCAL_SPACE'
            mapping[key] = {"bone": bone, "transform": transform, "space": space}
        else:
            mapping[key] = {"bone": "", "transform": "AUTO"}
    return mapping


def _mapping_lookup(
    mapping: Dict[str, Dict[str, Any]], ctrl_name: str
) -> Optional[Dict[str, Any]]:
    """
    Lookup mapping by exact key; if not found, try base without suffix (.001).
    Returns the mapping entry or None.
    """
    entry = mapping.get(ctrl_name)
    if entry:
        return entry
    base = _strip_numeric_suffix(ctrl_name)
    return mapping.get(base)


def _is_shapekey_value_fcurve(fcu: bpy.types.FCurve) -> bool:
    """True if the fcurve points at a shapekey value path."""
    dp = fcu.data_path or ""
    return dp.startswith('key_blocks["') and dp.endswith('"].value')


def _decide_transform(
    existing_transform_type: Optional[str], mapping_transform: Optional[str]
) -> str:
    """
    mapping_transform:
      - "AUTO" or None: keep existing_transform_type; if none, default to "LOC_Y"
      - explicit like "LOC_Y", "ROT_X", "SCALE_Z": override
    """
    if mapping_transform and mapping_transform.upper() != "AUTO":
        return mapping_transform.upper()
    if existing_transform_type:
        return existing_transform_type
    return "LOC_Y"


def _decide_space(existing_space: Optional[str], mapping_space: Optional[str]) -> str:
    """
    mapping_space: if provided, override; otherwise preserve existing_space or default 'LOCAL_SPACE'
    """
    if isinstance(mapping_space, str) and mapping_space:
        return mapping_space
    return existing_space or "LOCAL_SPACE"


def _ensure_single_target(var: bpy.types.DriverVariable) -> bpy.types.DriverTarget:
    """Ensure the variable has at least one target and return it; prune extras."""
    tgt = var.targets[0] if var.targets else var.targets.new()
    while len(var.targets) > 1:
        var.targets.remove(var.targets[-1])
    return tgt


def _rewire_variable_to_bone(
    obj_name: str,
    fcu: bpy.types.FCurve,
    var: bpy.types.DriverVariable,
    ctrl_obj_name: str,
    arm_obj: bpy.types.Object,
    bone_name: str,
    new_transform_type: str,
    new_space: str,
    report_lines: list,
) -> None:
    """Switch variable to TRANSFORMS and point to the armature/bone with chosen transform and space."""
    # Logging before mutation
    report_lines.append(
        f"[Rewire] {obj_name}: {fcu.data_path} | var '{var.name}' - "
        f"{ctrl_obj_name} -> {arm_obj.name}:{bone_name} ({new_transform_type}, {new_space})"
    )

    if DRY_RUN:
        return

    var.type = "TRANSFORMS"
    tgt = _ensure_single_target(var)
    tgt.id = arm_obj
    tgt.bone_target = bone_name
    tgt.transform_type = new_transform_type  # e.g., 'LOC_Y', 'ROT_X', 'SCALE_Z'
    tgt.transform_space = new_space


def rewire_shapekey_drivers_to_armature(
    mapping: Dict[str, Dict[str, Any]],
    arm_obj: bpy.types.Object,
    only_selected: bool = True,
) -> None:
    """
    Rewire shapekey drivers on meshes to point to the given armature & bone per mapping.

    mapping: control_object_name -> {"bone": str, "transform": "AUTO|LOC_*|ROT_*|SCALE_*", "space": optional}
    """
    # Stats and reporting
    total_meshes = 0
    total_driver_fc = 0
    total_vars_rewired = 0
    missing_bones: Set[str] = set()
    missing_controls: Set[str] = set()
    report_lines: list = []

    # Build set of meshes to process
    meshes = []
    if only_selected:
        for obj in bpy.context.selected_objects or []:
            if obj.type == "MESH":
                meshes.append(obj)
    else:
        for obj in bpy.data.objects:
            if obj.type == "MESH":
                meshes.append(obj)

    for obj in meshes:
        key_data = getattr(obj.data, "shape_keys", None)
        if not key_data or not key_data.animation_data:
            continue

        total_meshes += 1
        drivers = list(key_data.animation_data.drivers)

        for fcu in drivers:
            if not _is_shapekey_value_fcurve(fcu):
                continue

            total_driver_fc += 1
            drv = fcu.driver
            if not drv or not drv.variables:
                continue

            for var in drv.variables:
                # Evaluate all targets; rewire first mapped control found
                targets = list(var.targets)
                for t in targets:
                    ctrl_id = getattr(t, "id", None)
                    ctrl_name = getattr(ctrl_id, "name", None) if ctrl_id else None
                    if not ctrl_name:
                        continue

                    entry = _mapping_lookup(mapping, ctrl_name)
                    if not entry:
                        # Not mapped, keep searching
                        continue

                    bone_name = (entry.get("bone") or "").strip()
                    if not bone_name:
                        missing_bones.add(ctrl_name)
                        continue

                    # Validate bone exists
                    if not (arm_obj.pose and arm_obj.pose.bones.get(bone_name)):
                        missing_bones.add(f"{ctrl_name} -> {bone_name}")
                        continue

                    # Decide transform/space
                    existing_tt = getattr(t, "transform_type", None)
                    existing_space = getattr(t, "transform_space", None)
                    chosen_tt = _decide_transform(existing_tt, entry.get("transform"))
                    chosen_space = _decide_space(existing_space, entry.get("space"))

                    _rewire_variable_to_bone(
                        obj_name=obj.name,
                        fcu=fcu,
                        var=var,
                        ctrl_obj_name=ctrl_name,
                        arm_obj=arm_obj,
                        bone_name=bone_name,
                        new_transform_type=chosen_tt,
                        new_space=chosen_space,
                        report_lines=report_lines,
                    )
                    total_vars_rewired += 1
                    break  # next variable (we rewire one target per variable)

    # Print detailed per-var report
    for line in report_lines:
        print(line)

    # Print summary
    print(f"[Rewire] Meshes processed: {total_meshes}")
    print(f"[Rewire] Shapekey driver FCurves scanned: {total_driver_fc}")
    print(f"[Rewire] Variables rewired: {total_vars_rewired}")
    if missing_bones:
        print(
            f"[Rewire] Missing or invalid bone mappings for controls: {sorted(missing_bones)}"
        )
    if missing_controls:
        print(
            f"[Rewire] Controls used by drivers but not found in mapping: {sorted(missing_controls)}"
        )
    if DRY_RUN:
        print("[Rewire] DRY_RUN=True (no changes written)")


def main():
    try:
        arm = _get_armature()
    except Exception as e:
        print(f"[Rewire] ERROR resolving armature: {e}")
        return

    try:
        mapping = _load_mapping(MAPPING_PATH)
    except Exception as e:
        print(f"[Rewire] ERROR loading mapping JSON '{MAPPING_PATH}': {e}")
        return

    print(f"[Rewire] Armature: {arm.name}")
    print(f"[Rewire] Mapping file: {MAPPING_PATH}")
    print(f"[Rewire] Only selected meshes: {ONLY_SELECTED}")
    print(f"[Rewire] DRY_RUN: {DRY_RUN}")

    rewire_shapekey_drivers_to_armature(mapping, arm, ONLY_SELECTED)
    print("[Rewire] Done.")


main()
