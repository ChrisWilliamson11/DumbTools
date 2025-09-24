import bpy
import os
import time
import gc

# Progress log configuration
CONTINUE_FROM_LOG = False
CLEAR_LOG_ON_START = True
# LOG_PATH will be constructed in main() using the chosen root folder


def _parse_log_line(line: str) -> str:
    line = line.strip()
    if not line:
        return ""
    parts = line.split("|", 2)
    if len(parts) >= 2:
        return parts[1]
    return line


def load_processed_sources(log_path: str) -> set:
    processed = set()
    try:
        with open(log_path, "r", encoding="utf-8", errors="ignore") as f:
            for ln in f:
                p = _parse_log_line(ln)
                if p:
                    processed.add(p)
    except FileNotFoundError:
        pass
    except Exception as e:
        print(f"Warning: could not read log '{log_path}': {e}")
    return processed


def log_progress(log_path: str, path: str, status: str, message: str = "") -> None:
    try:
        with open(log_path, "a", encoding="utf-8", errors="ignore") as f:
            f.write(f"{status}|{path}|{message}\n")
    except Exception as e:
        print(f"Warning: could not write progress log: {e}")


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


def process_blend_file(blend_path: str) -> tuple[int, str]:
    """Open a .blend, generate previews for assets inside, then save.
    Returns (count_generated, status), where status is one of:
      - 'OK'        (opened, generated previews, attempted save)
      - 'OPEN_FAIL' (file could not be opened)
      - 'GEN_ERR'   (error during preview generation)
      - 'SAVE_ERR'  (error during save)
    """
    print(f"\nOpening blend: {blend_path}")
    try:
        bpy.ops.wm.open_mainfile(filepath=blend_path)
    except Exception as e:
        print(f"Failed to open '{blend_path}': {e} — skipping")
        return 0, 'OPEN_FAIL'

    gc.collect()

    status = 'OK'
    try:
        count = generate_previews_for_current_file()
    except Exception as e:
        print(f"Error while generating previews in '{blend_path}': {e}")
        count = 0
        status = 'GEN_ERR'

    try:
        bpy.ops.wm.save_mainfile()  # Save to the same file
        print(f"Saved: {blend_path}")
    except Exception as e:
        print(f"Failed to save '{blend_path}': {e}")
        if status == 'OK':
            status = 'SAVE_ERR'

    return count, status


def main():
    """Recurse the root; for each .blend file, generate previews for assets and save the file.
    Supports "continue from log" so interrupted runs can resume.
    """
    root_folder = r"H:\000_Projects\Goliath\00_Assets\Game\01_Environment\Palette_RAW"
    print(f"Scanning for .blend files at: {root_folder}")

    log_path = os.path.join(root_folder, "_GenerateAssetPreviews.log")
    if CLEAR_LOG_ON_START:
        try:
            os.remove(log_path)
            print(f"Cleared progress log: {log_path}")
        except FileNotFoundError:
            pass
        except Exception as e:
            print(f"Warning: could not clear log '{log_path}': {e}")

    to_process = []
    for dirpath, _, filenames in os.walk(root_folder):
        for name in filenames:
            if name.lower().endswith('.blend'):
                to_process.append(os.path.join(dirpath, name))

    if CONTINUE_FROM_LOG:
        processed = load_processed_sources(log_path)
        if processed:
            before = len(to_process)
            to_process = [p for p in to_process if p not in processed]
            print(f"Continue-from-log: {before - len(to_process)} already listed; {len(to_process)} to do")

    if not to_process:
        print("\n==============================")
        print("NO BLEND FILES FOUND")
        print("==============================\n")
        return

    total = 0
    files_done = 0
    for blend_path in to_process:
        count, status = process_blend_file(blend_path)
        total += count
        files_done += 1
        log_progress(log_path, blend_path, status, f"count={count}")
        gc.collect()

    print("\n====================================")
    print(f"Processed {files_done} .blend file(s)")
    print(f"Generated previews for {total} asset(s) in total")
    print("====================================\n")


if __name__ == "__main__":
    main()

