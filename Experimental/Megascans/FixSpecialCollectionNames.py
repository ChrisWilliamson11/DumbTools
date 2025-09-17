import bpy
import os
from typing import List, Optional, Tuple

# Root folder to scan (update as needed)
ROOT_FOLDER = r"H:\000_Projects\Goliath\00_Assets\Game"

# Files that trigger special naming behavior
SPECIAL_SUFFIXES = {"base_mesh", "render", "raycast", "render_only", "shadowproxy", "working"}
SUPPORTED_EXTS = (".fbx", ".usd", ".usda", ".usdc", ".usdz")


def compute_blend_basename(src_path: str) -> str:
    """Return the base filename for the .blend using the same rule as CreateMegascans3D.

    If the source base name is a utility (SPECIAL_SUFFIXES) and the folder is named
    'model' or 'models', use the parent folder name.
    """
    directory = os.path.dirname(src_path)
    folder = os.path.basename(directory)
    base = os.path.splitext(os.path.basename(src_path))[0]

    if base.lower() in SPECIAL_SUFFIXES:
        if folder.lower() in {"model", "models"}:
            parent_dir = os.path.dirname(directory)
            parent_name = os.path.basename(parent_dir) or folder
            folder = parent_name
        return f"{folder}-{base}"
    return base


def get_target_blend_path(src_path: str) -> str:
    directory = os.path.dirname(src_path)
    base_for_blend = compute_blend_basename(src_path)
    return os.path.join(directory, f"{base_for_blend}.blend")


def find_special_imports(root: str) -> List[str]:
    matches: List[str] = []
    for dirpath, _dirs, files in os.walk(root):
        for name in files:
            lower = name.lower()
            ext = os.path.splitext(lower)[1]
            base = os.path.splitext(lower)[0]
            if ext in SUPPORTED_EXTS and base in SPECIAL_SUFFIXES:
                matches.append(os.path.join(dirpath, name))
    return matches


def pick_asset_collection(target_name: str) -> Optional[bpy.types.Collection]:
    """Pick the collection to rename.
    Preference order:
      1) Asset-marked collection whose name is one of the special suffixes
      2) Single asset-marked collection (if only one)
      3) Asset-marked collection with the most objects
    """
    asset_colls = [c for c in bpy.data.collections if getattr(c, "asset_data", None)]
    if not asset_colls:
        return None

    special_named = [c for c in asset_colls if c.name.lower() in SPECIAL_SUFFIXES]
    if special_named:
        return special_named[0]

    if len(asset_colls) == 1:
        return asset_colls[0]

    # Fallback: pick the one with the most objects
    asset_colls.sort(key=lambda c: len(getattr(c, "objects", [])), reverse=True)
    return asset_colls[0]


def rename_collection_in_blend(blend_path: str, new_name: str) -> Tuple[bool, str]:
    """Open the blend, rename the chosen asset collection to new_name, and save.
    Returns (changed, message).
    """
    try:
        bpy.ops.wm.open_mainfile(filepath=blend_path)
    except Exception as e:
        return False, f"Failed to open {blend_path}: {e}"

    coll = pick_asset_collection(new_name)
    if coll is None:
        return False, f"No asset-marked collection found in {blend_path}"

    if coll.name == new_name:
        # Already correct
        return False, f"Collection already named '{new_name}' in {blend_path}"

    # Try the rename
    try:
        coll.name = new_name
    except Exception as e:
        return False, f"Could not rename collection in {blend_path}: {e}"

    # Save in place
    try:
        bpy.ops.wm.save_mainfile()
    except Exception as e:
        return False, f"Renamed but failed to save {blend_path}: {e}"

    return True, f"Renamed collection to '{new_name}' in {blend_path}"


def main():
    root = ROOT_FOLDER
    print(f"Scanning for special-name imports under: {root}")

    special_sources = find_special_imports(root)
    if not special_sources:
        print("No special-name import files found.")
        return

    print(f"Found {len(special_sources)} special import file(s). Processing...")
    changed = 0
    skipped = 0
    errors: List[str] = []

    for src in special_sources:
        target_blend = get_target_blend_path(src)
        if not os.path.exists(target_blend):
            msg = f"Blend not found for {src} -> {target_blend}"
            print(msg)
            errors.append(msg)
            continue

        desired_name = compute_blend_basename(src)
        did_change, msg = rename_collection_in_blend(target_blend, desired_name)
        print(msg)
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

