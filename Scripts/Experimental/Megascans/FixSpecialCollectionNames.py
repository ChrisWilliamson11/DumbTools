import bpy
import os
from typing import List, Optional, Tuple

# Root folder to scan (update as needed)
ROOT_FOLDER = r"H:\000_Projects\Goliath\00_Assets\Game"

# Files that trigger special naming behavior
# Progress log settings
CONTINUE_FROM_LOG = True  # When True, skip sources already listed in the log
CLEAR_LOG_ON_START = False  # When True, delete the existing log at start
LOG_PATH = os.path.join(ROOT_FOLDER, "_FixSpecialCollectionNames.log")

SPECIAL_SUFFIXES = {"base_mesh", "render", "raycast", "render_only", "shadowproxy", "working"}
SUPPORTED_EXTS = (".fbx", ".usd", ".usda", ".usdc", ".usdz")


# --- Progress log helpers ---

def _parse_log_line(line: str) -> str:
    line = line.strip()
    if not line:
        return ""
    # Expected formats: "STATUS|<src>|..." or just "<src>"
    parts = line.split("|", 2)
    if len(parts) >= 2:
        return parts[1]
    return line


def load_processed_sources(log_path: str) -> set:
    processed = set()
    try:
        with open(log_path, "r", encoding="utf-8", errors="ignore") as f:
            for ln in f:
                src = _parse_log_line(ln)
                if src:
                    processed.add(src)
    except FileNotFoundError:
        pass
    except Exception as e:
        print(f"Warning: could not read log '{log_path}': {e}")
    return processed


def log_progress(src: str, status: str, message: str = "") -> None:
    try:
        with open(LOG_PATH, "a", encoding="utf-8", errors="ignore") as f:
            f.write(f"{status}|{src}|{message}\n")
    except Exception as e:
        print(f"Warning: could not write progress log: {e}")


def _prefixed(name: str, prefix: str) -> bool:
    return name.lower().startswith((prefix + "-").lower())


def _ensure_prefix(name: str, prefix: str) -> str:
    return name if _prefixed(name, prefix) else f"{prefix}-{name}"


def get_prefix_for_blend(blend_path: str) -> Optional[str]:
    """Return the folder name two directories above the .blend file."""
    try:
        d1 = os.path.dirname(blend_path)
        d2 = os.path.dirname(d1)
        pref = os.path.basename(d2)
        return pref or None
    except Exception:
        return None


def find_model_blends(root: str) -> List[str]:
    """Find .blend files whose immediate parent folder is 'model' or 'models'."""
    matches: List[str] = []
    for dirpath, _, files in os.walk(root):
        folder = os.path.basename(dirpath).lower()
        if folder not in {"model", "models"}:
            continue
        for name in files:
            if name.lower().endswith(".blend"):
                matches.append(os.path.join(dirpath, name))
    return matches


def rename_assets_in_blend(blend_path: str, prefix: str) -> Tuple[bool, str]:
    """Open the blend, prefix asset-marked collections and mesh objects with '<prefix>-', and save.
    Returns (changed, message).
    """
    try:
        bpy.ops.wm.open_mainfile(filepath=blend_path)
    except Exception as e:
        return False, f"Failed to open {blend_path}: {e}"

    changed = 0
    try:
        # Collections
        for coll in bpy.data.collections:
            if getattr(coll, "asset_data", None):
                new_name = _ensure_prefix(coll.name, prefix)
                if new_name != coll.name:
                    coll.name = new_name
                    changed += 1
        # Mesh objects
        for obj in bpy.data.objects:
            if obj.type == "MESH" and getattr(obj, "asset_data", None):
                new_name = _ensure_prefix(obj.name, prefix)
                if new_name != obj.name:
                    obj.name = new_name
                    changed += 1
    except Exception as e:
        return False, f"Error while renaming in {blend_path}: {e}"

    if changed > 0:
        try:
            bpy.ops.wm.save_mainfile()
        except Exception as e:
            return False, f"Renamed {changed} but failed to save {blend_path}: {e}"
        return True, f"Prefixed {changed} asset(s) with '{prefix}-' in {blend_path}"
    else:
        return False, f"No rename needed in {blend_path}"


def main():
    root = ROOT_FOLDER
    print(f"Scanning for .blend files under: {root}")

    # Handle progress log controls
    if CLEAR_LOG_ON_START:
        try:
            os.remove(LOG_PATH)
            print(f"Cleared progress log: {LOG_PATH}")
        except FileNotFoundError:
            pass
        except Exception as e:
            print(f"Warning: could not clear log '{LOG_PATH}': {e}")

    processed = set()
    if CONTINUE_FROM_LOG:
        processed = load_processed_sources(LOG_PATH)
        if processed:
            print(f"Continue-from-log: will skip {len(processed)} already-listed source(s)")

    blends = find_model_blends(root)
    if not blends:
        print("No .blend files found under model/models folders.")
        return

    print(f"Found {len(blends)} .blend file(s) in model/models. Processing...")
    changed = 0
    skipped = 0
    errors: List[str] = []

    for blend_path in blends:
        if CONTINUE_FROM_LOG and blend_path in processed:
            print(f"Skipping (already in log): {blend_path}")
            continue

        prefix = get_prefix_for_blend(blend_path)
        if not prefix:
            msg = f"Could not compute prefix for {blend_path}"
            print(msg)
            errors.append(msg)
            log_progress(blend_path, "MISS", msg)
            continue

        did_change, msg = rename_assets_in_blend(blend_path, prefix)
        print(msg)
        log_progress(blend_path, "CHANGED" if did_change else "SKIP", msg)
        if did_change:
            changed += 1
        else:
            skipped += 1

    print("\n===== SUMMARY =====")
    print(f"Changed: {changed}")
    print(f"Unchanged/Skipped: {skipped}")
    if errors:
        print("Errors:")
        for e in errors:
            print(f" - {e}")
    print("===================\n")


if __name__ == "__main__":
    main()

