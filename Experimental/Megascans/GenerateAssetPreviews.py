import bpy
import os
import time
import gc


def wait_for_preview_generation(max_wait_seconds: int = 60) -> bool:
    """Wait until Blender finishes preview generation jobs, or timeout.
    Returns True if jobs finished, False if timed out.
    """
    start = time.time()
    while bpy.app.is_job_running("RENDER_PREVIEW"):
        if time.time() - start > max_wait_seconds:
            print("Preview generation timed out")
            return False
        time.sleep(0.1)
    return True


def get_all_assets_in_file():
    """Collect asset-tagged IDs in the currently open .blend."""
    assets = []
    # Objects and collections are our primary targets, but include materials if present
    for coll in bpy.data.collections:
        if getattr(coll, "asset_data", None):
            assets.append(coll)
    for obj in bpy.data.objects:
        if getattr(obj, "asset_data", None):
            assets.append(obj)
    for mat in bpy.data.materials:
        if getattr(mat, "asset_data", None):
            assets.append(mat)
    return assets


def generate_previews_for_current_file() -> int:
    """Generate previews for all assets in the current file. Returns count generated."""
    assets = get_all_assets_in_file()
    if not assets:
        print("No assets found in this file; nothing to preview.")
        return 0

    print(f"Generating previews for {len(assets)} asset(s)...")
    generated = 0
    for id_block in assets:
        try:
            id_block.asset_generate_preview()
            generated += 1
        except Exception as e:
            print(f"Failed to generate preview for '{getattr(id_block, 'name', '<unknown>')}': {e}")

    wait_for_preview_generation()
    print(f"Finished preview generation for {generated} asset(s).")
    return generated


def process_blend_file(blend_path: str) -> int:
    """Open a .blend, generate previews for assets inside, then save. Returns count generated."""
    print(f"\nOpening blend: {blend_path}")
    bpy.ops.wm.open_mainfile(filepath=blend_path)
    gc.collect()

    count = generate_previews_for_current_file()

    try:
        bpy.ops.wm.save_mainfile()  # Save to the same file
        print(f"Saved: {blend_path}")
    except Exception as e:
        print(f"Failed to save '{blend_path}': {e}")

    return count


def main():
    """Recurse the root; for each .blend file, generate previews for assets and save the file."""
    root_folder = r"H:\000_Projects\Goliath\00_Assets"
    print(f"Scanning for .blend files at: {root_folder}")

    to_process = []
    for dirpath, _, filenames in os.walk(root_folder):
        for name in filenames:
            if name.lower().endswith('.blend'):
                to_process.append(os.path.join(dirpath, name))

    if not to_process:
        print("\n==============================")
        print("NO BLEND FILES FOUND")
        print("==============================\n")
        return

    total = 0
    files_done = 0
    for blend_path in to_process:
        total += process_blend_file(blend_path)
        files_done += 1
        gc.collect()

    print("\n====================================")
    print(f"Processed {files_done} .blend file(s)")
    print(f"Generated previews for {total} asset(s) in total")
    print("====================================\n")


if __name__ == "__main__":
    main()

