# Tooltip: Patch Rigify UI scripts in text datablocks for Blender 5.0 compatibility
"""
Fix Rigify UI Script for Blender 5.0+ (Bulletproof Regex Patch)

This script patches embedded Rigify UI text datablocks so they work with
Blender 5.0's layered animation system. It uses highly resilient boundary
matches to inject the correct logic regardless of old rig script formatting.

Usage:
    1. Select the armature that has the broken rig UI
    2. Run this script

It will:
    - Read the rig_id from the selected armature's data
    - Find the UI text datablock associated with that rig_id
    - Apply regex patches for Blender 5.0 Action API compatibility
    - Safely overwrite the text block
"""

import bpy
import re

GET_ACTION_FCURVES_CODE = '''def get_action_fcurves(action):
    """Get all FCurves from an action, supporting both legacy and Blender 5.0+ layered animation.
    In Blender 5.0+, Action.fcurves was removed. FCurves now live inside:
        Action -> Layers -> Strips -> Channelbags -> FCurves
    """
    # Blender 5.0+: layered animation system
    if hasattr(action, 'layers'):
        curves = []
        for layer in action.layers:
            for strip in layer.strips:
                if hasattr(strip, 'channelbags'):
                    for channelbag in strip.channelbags:
                        curves.extend(channelbag.fcurves)
        return curves
    # Legacy (Blender 4.x and earlier): fcurves directly on Action
    if hasattr(action, 'fcurves'):
        return list(action.fcurves)
    return []
'''

NEW_CLEAN_ACTION_CODE = '''def clean_action_empty_curves(action):
    "Delete completely empty curves from the given action."
    action = find_action(action)
    if action is None:
        return
    # Blender 5.0+: remove from each channelbag
    if hasattr(action, 'layers'):
        for layer in action.layers:
            for strip in layer.strips:
                if hasattr(strip, 'channelbags'):
                    for channelbag in strip.channelbags:
                        for curve in list(channelbag.fcurves):
                            if curve.is_empty:
                                channelbag.fcurves.remove(curve)
    # Legacy
    elif hasattr(action, 'fcurves'):
        for curve in list(action.fcurves):
            if curve.is_empty:
                action.fcurves.remove(curve)
    if hasattr(action, 'update_tag'):
        action.update_tag()
'''

PATCHES = [
    {
        "description": "Add get_action_fcurves() helper",
        # Match from 'def find_action' all the way down to 'return None'
        "find_regex": r"(def find_action\(action\):[\s\S]*?return None)",
        "replace_str": r"\1\n\n" + GET_ACTION_FCURVES_CODE.strip(),
        "check_already_applied": r"def get_action_fcurves",
    },
    {
        "description": "Update clean_action_empty_curves for layered animation",
        # Match clean_action_empty_curves right up until the invariable 'TRANSFORM_PROPS_LOCATION' constant
        "find_regex": r"def clean_action_empty_curves\(action\):[\s\S]*?(?=TRANSFORM_PROPS_LOCATION)",
        "replace_str": NEW_CLEAN_ACTION_CODE.strip() + "\n\n",
        "check_already_applied": r"channelbag\.fcurves\.remove",
    },
    {
        "description": "Update ActionCurveTable to use get_action_fcurves()",
        "find_regex": r"self\.index_curves\(self\.action\.fcurves\)",
        "replace_str": r"self.index_curves(get_action_fcurves(self.action))",
        "check_already_applied": r"get_action_fcurves\(self\.action\)",
    },
    {
        "description": "Fix INSERTKEY_XYZ_TO_RGB error in get_keying_flags",
        "find_regex": r"if prefs\.edit\.use_insertkey_xyz_to_rgb:\s*flags\.add\('INSERTKEY_XYZ_TO_RGB'\)",
        "replace_str": r"if hasattr(prefs.edit, 'use_insertkey_xyz_to_rgb') and bpy.app.version < (4, 1):\n        flags.add('INSERTKEY_XYZ_TO_RGB')",
        "check_already_applied": r"hasattr\(prefs\.edit, 'use_insertkey_xyz_to_rgb'\) and bpy\.app\.version < \(4, 1\)"
    }
]

def normalize_newlines(text):
    return text.replace('\r\n', '\n').replace('\r', '\n')

def find_text_block_for_rig(rig_id):
    pattern = re.compile(r'^rig_id\s*=\s*["\']' + re.escape(rig_id) + r'["\']', re.MULTILINE)
    matches = []
    for text_block in bpy.data.texts:
        if pattern.search(normalize_newlines(text_block.as_string())):
            matches.append(text_block)
    return matches

def apply_patches(text_block):
    content = normalize_newlines(text_block.as_string())
    results = []

    for patch in PATCHES:
        if re.search(patch["check_already_applied"], content):
            results.append((patch["description"], "already_applied"))
            continue
            
        new_content, count = re.subn(patch["find_regex"], patch["replace_str"], content)
        if count > 0:
            content = new_content
            results.append((patch["description"], True))
        else:
            results.append((patch["description"], False))

    text_block.clear()
    text_block.write(content)
    return results

def main():
    obj = bpy.context.active_object
    if getattr(obj, "type", "") != 'ARMATURE':
        raise RuntimeError("Please select an Armature and try again.")

    rig_id = obj.data.get("rig_id")
    if not rig_id:
        raise RuntimeError(f"Armature '{obj.name}' has no 'rig_id' custom property.")

    text_blocks = find_text_block_for_rig(rig_id)
    if not text_blocks:
        raise RuntimeError(f"No text datablock found containing rig_id = \"{rig_id}\".")

    patched_count = 0
    failed_count = 0

    for text_block in text_blocks:
        print(f"\n[Fix Rigify UI] Processing text block: '{text_block.name}'")
        
        results = apply_patches(text_block)
        
        block_ok = True
        for desc, success in results:
            if success is True:
                print(f"  OK: {desc}")
            elif success == "already_applied":
                print(f"  SKIP: {desc} (already applied)")
            else:
                print(f"  FAIL: {desc}")
                block_ok = False
                
        if block_ok:
            patched_count += 1
        else:
            failed_count += 1

    msg = f"Processed {patched_count + failed_count} text block(s). " + \
          (f"{failed_count} had missing patterns." if failed_count else "All OK.")
          
    def draw_popup(self, context):
        self.layout.label(text=msg)

    bpy.context.window_manager.popup_menu(draw_popup, title="Fix Rigify UI", icon='INFO')
    print(f"\n[Fix Rigify UI] {msg}")

try:
    main()
except RuntimeError as e:
    def draw_error(self, context):
        self.layout.label(text=str(e))
    bpy.context.window_manager.popup_menu(draw_error, title="Fix Rigify UI - Error", icon='ERROR')
    print(f"\n[Fix Rigify UI] ERROR: {e}")
