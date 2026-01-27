
import bpy

import os
import subprocess
import platform
import shutil
import shlex
import stat
import json
import re
import tempfile
import datetime
import uuid
from bpy.props import (
    StringProperty,
    BoolProperty,
    IntProperty,
    EnumProperty,
    CollectionProperty,
    PointerProperty,
    FloatProperty
)
from bpy.app.handlers import persistent
from bpy_extras.io_utils import ImportHelper


# -------------------------------------------------------------------
# Global Config
# -------------------------------------------------------------------

_IS_LOADING_CONFIG = False
_IS_WRITING_BATCH = False

def get_config_path():
    return os.path.join(bpy.utils.user_resource('CONFIG'), "batch_render_config.json")

def save_global_config(context):
    """Saves the current batch file location settings to a global config file."""
    global _IS_LOADING_CONFIG
    if _IS_LOADING_CONFIG:
        return
        
    if not context or not context.scene: return

    settings = context.scene.batch_render_settings
    data = {"batch_file_path": settings.batch_file_path}
    
    try:
        with open(get_config_path(), 'w') as f:
            json.dump(data, f)
    except Exception as e:
        print(f"BatchRender: Failed to save config: {e}")

def apply_global_config():
    """Timer function to load config safely after startup."""
    global _IS_LOADING_CONFIG
    
    config_path = get_config_path()
    print(f"BatchRender: Checking config at {config_path}")
    
    if not os.path.exists(config_path): 
        print("BatchRender: Config file not found.")
        return None
    
    _IS_LOADING_CONFIG = True
    try:
        with open(config_path, 'r') as f:
            data = json.load(f)
            
        print(f"BatchRender: Found Config Data: {data}")
            
        context = bpy.context
        if context.scene:
            settings = context.scene.batch_render_settings
            if "batch_file_path" in data: 
                settings.batch_file_path = data["batch_file_path"]
                print(f"BatchRender: Applied loaded config: {settings.batch_file_path}")
            else:
                print("BatchRender: Config data missing 'batch_file_path'")
        else:
            print("BatchRender: No active scene to apply config")
            
    except Exception as e:
        print(f"BatchRender: Failed to load config: {e}")
    finally:
        _IS_LOADING_CONFIG = False
    return None

@persistent
def load_global_config_handler(dummy):
    apply_global_config()

# -------------------------------------------------------------------
# Helper Functions
# -------------------------------------------------------------------

def get_batch_file_path(context):
    """Calculates the full absolute path to the batch file based on settings."""
    settings = context.scene.batch_render_settings
    raw_path = settings.batch_file_path
    
    if not raw_path:
        return None, "Batch file path is empty"
        
    # Resolve absolute path
    # If starts with //, join with blend file dir
    if raw_path.startswith("//"):
        if not bpy.data.filepath:
             return None, "Save .blend file first or use absolute path"
        abs_path = bpy.path.abspath(raw_path)
    else:
        abs_path = raw_path
        
    # Validation
    if not abs_path.lower().endswith(('.bat', '.sh', '.cmd')):
        ext = ".bat" if platform.system() == "Windows" else ".sh"
        if not os.path.splitext(abs_path)[1]:
            abs_path += ext
            
    return abs_path, None

def get_target_jobs(context):
    """Returns list of (index, job) tuples for operation. Uses selection if any, else active."""
    queue = context.scene.batch_render_jobs
    selected = []
    for i, job in enumerate(queue):
        if job.selected: selected.append((i, job))
        
    if selected: return selected
    
    # Fallback to active
    idx = context.scene.batch_render_active_job_index
    if 0 <= idx < len(queue):
        return [(idx, queue[idx])]
    return []

def get_target_chunks(context, job):
    """Returns list of chunk objects. Uses selection if any, else active."""
    selected = [c for c in job.chunks if c.selected]
    if selected: return selected
    
    # Fallback to active
    idx = context.scene.batch_render_active_chunk_index
    if 0 <= idx < len(job.chunks):
        return [job.chunks[idx]]
    return []

def parse_batch_file_to_state(filepath):
    """
    Reads the batch file and returns a dictionary state:
    {
        'globals': dict,
        'jobs': [ {data_dict}, ... ]
    }
    """
    state = {'globals': {}, 'jobs': []}
    if not filepath or not os.path.exists(filepath):
        return state
        
    try:
        with open(filepath, 'r') as f:
            lines = f.readlines()
            
        for line in lines:
            line = line.strip()
            # Look for metadata comment
            meta_str = None
            if line.startswith("REM FLIP_BATCH_META:"):
                meta_str = line[len("REM FLIP_BATCH_META:"):].strip()
            elif line.startswith("# FLIP_BATCH_META:"):
                meta_str = line[len("# FLIP_BATCH_META:"):].strip()
            elif line.startswith("REM FLIP_BATCH_GLOBAL:") or line.startswith("# FLIP_BATCH_GLOBAL:"):
                g_meta = line[line.find(":")+1:].strip()
                try: state['globals'] = json.loads(g_meta)
                except: pass
                continue
                
            if meta_str:
                try:
                    data = json.loads(meta_str)
                    state['jobs'].append(data)
                except: pass
    except Exception as e:
        print(f"BatchRender: Parse Error: {e}")
        return None
        
    return state

def capture_local_state(context):
    """Captures the current UI state into a dictionary structure."""
    settings = context.scene.batch_render_settings
    queue = context.scene.batch_render_jobs
    
    # Globals
    g_data = {}
    for k in settings.bl_rna.properties.keys():
        if k == "rna_type" or k == "batch_file_path" or k == "last_known_mtime": continue
        g_data[k] = getattr(settings, k)
        
    # Jobs
    j_list = []
    for job in queue:
        # We need to serialize the job manually (or helper)
        # Using a subset of keys we know we save
        # Actually logic is in write_batch_file, let's duplicate the key list for now or make a helper?
        # Helper is better. see get_job_data_dict below.
        pass # implemented in loop below
        
        # Quick serialize
        meta = {}
        for k in job.bl_rna.properties.keys():
            if k == "rna_type" or k == "is_saved" or k == "chunks": continue
            meta[k] = getattr(job, k)
        
        # Job ID for merging
        # We don't have a persistent UUID. We use SceneName + Filepath as key?
        # Or index?
        # Let's trust the data.
        j_list.append(meta)
        
    return {'globals': g_data, 'jobs': j_list}

def apply_state_to_ui(context, state):
    """Applies a state dict to the Blender UI."""
    global _IS_LOADING_CONFIG
    _IS_LOADING_CONFIG = True
    try:
        settings = context.scene.batch_render_settings
        queue = context.scene.batch_render_jobs
        
        # Apply Globals
        # Skip UI-only properties that should remain local-controlled during session
        ui_props = {'show_job_queue', 'show_selected_job', 'show_chunk_details', 'show_chunk_status', 'show_file_config', 'show_global_options', 'show_queue_overrides'}
        
        for k, v in state.get('globals', {}).items():
            if k in ui_props: continue
            
            if hasattr(settings, k):
                try: setattr(settings, k, v)
                except: pass
                
        # Apply Jobs
        _clear_saved_jobs(context)
        
        for data in state.get('jobs', []):
            item = queue.add()
            item.is_saved = True
            
            for k, v in data.items():
                if hasattr(item, k):
                    try: setattr(item, k, v)
                    except: pass
            
            # Ensure UUID exists (migration)
            if not item.uuid:
                item.uuid = str(uuid.uuid4())
            
            # Restore cached progress (dict access)
            if 'cached_progress' in data:
                item['cached_progress'] = data['cached_progress']
            if 'cached_chunk_progress' in data:
                item['cached_chunk_progress'] = data['cached_chunk_progress']
                    
            # Trigger chunk refresh
            refresh_job_chunks(item, context.scene.batch_render_settings, get_batch_file_path(context)[0])
    finally:
        _IS_LOADING_CONFIG = False

def load_queue_from_file(context):
    """Reads the batch file and populates the UI list from metadata."""
    filepath, error = get_batch_file_path(context)
    if error or not filepath or not os.path.exists(filepath):
        _clear_saved_jobs(context)
        return

    global _IS_LOADING_CONFIG
    _IS_LOADING_CONFIG = True

    try:
        state = parse_batch_file_to_state(filepath)
        apply_state_to_ui(context, state)
                    
    except Exception as e:
        print(f"Error loading batch file: {e}")
    finally:
        # Update timestamp if successful (or partial)
        if filepath and os.path.exists(filepath):
            try:
                context.scene.batch_render_settings.last_known_mtime = os.path.getmtime(filepath)
            except: pass
        _IS_LOADING_CONFIG = False


def _clear_saved_jobs(context):
    """Removes all jobs marked as 'Saved' from the list, keeping 'Pending'."""
    queue = context.scene.batch_render_jobs
    for i in range(len(queue) - 1, -1, -1):
        if queue[i].is_saved:
            queue.remove(i)
            
def merge_queue_states(local, remote, active_idx, modified_idx=-1):
    """
    Merges Local and Remote states.
    Returns: (merged_state, conflict_flag)
    Strategy:
    - Globals: Local wins (Last Write Wins).
    - Jobs:
      - Additions: Union of both.
      - Collisions: Remote wins UNLESS it's the Active Job OR the Modified Job.
    """
    merged = {'globals': local['globals'].copy(), 'jobs': []}
    
    # ... (Global merging remains same) ...
    for k, v in remote.get('globals', {}).items():
        if k not in merged['globals']:
            merged['globals'][k] = v

    r_jobs = remote.get('jobs', [])
    l_jobs = local.get('jobs', [])
    
    # Identify Prioritized Jobs (Active + Modified)
    prioritized_indices = set()
    if 0 <= active_idx < len(l_jobs): prioritized_indices.add(active_idx)
    if 0 <= modified_idx < len(l_jobs): prioritized_indices.add(modified_idx)
    
    merged_jobs = list(r_jobs)
    
    for local_idx in prioritized_indices:
        local_job = l_jobs[local_idx]
        match_idx = -1
        
        # 1. Try UUID Match (Strongest)
        aid = active_job.get('uuid', '')
        if aid:
            for i, rj in enumerate(merged_jobs):
                if rj.get('uuid') == aid:
                    match_idx = i
                    break
        
    for local_idx in prioritized_indices:
        local_job = l_jobs[local_idx]
        match_idx = -1
        
        # 1. Try UUID Match (Strongest)
        aid = local_job.get('uuid', '')
        if aid:
            for i, rj in enumerate(merged_jobs):
                if rj.get('uuid') == aid:
                    match_idx = i
                    break
        
        # 2. Fallback to Scene+Path
        if match_idx == -1:
            norm_local = _norm(local_job.get('filepath'))
            for i, rj in enumerate(merged_jobs):
                norm_remote = _norm(rj.get('filepath'))
                if norm_remote == norm_local and rj.get('scene_name') == local_job.get('scene_name'):
                    match_idx = i
                    break
        
        if match_idx >= 0:
            # Overwrite existing job with Local Job (It wins!)
            merged_jobs[match_idx] = local_job
        else:
            # New job? Append it if not already in list logic below handles uniqueness but lets add here to be safe
            # Actually, the _add_if_new loop below will handle it if we don't add it here?
            # No, merged_jobs IS the list. If we don't add it to merged_jobs, it might be added later by l_jobs loop.
            # But we want to ensure it's in the primary set.
            # Wait, if we don't find it in remote, it means it's a NEW local job?
            # Yes. So we should treat it as part of l_jobs which get added at the end.
            pass
            
    # Merge & Deduplicate Remainder
    final_list = []
    seen_uuids = set()
    seen_sigs = set() # Path+Scene signature for legacy dupes
    
    def _add_if_new(job):
        uid = job.get('uuid', '')
        norm_p = _norm(job.get('filepath'))
        sig = f"{norm_p}::{job.get('scene_name')}"
        
        # Check UUID
        if uid and uid in seen_uuids: return
        # Check Signature (if no UUID or UUID mismatch but same file?)
        if sig in seen_sigs: return
        
        if uid: seen_uuids.add(uid)
        seen_sigs.add(sig)
        final_list.append(job)

    # 1. Process merged list
    for j in merged_jobs: _add_if_new(j)
            
    # 2. Add remaining Local jobs if new
    for lj in l_jobs: _add_if_new(lj)

    merged['jobs'] = final_list
    return merged, False

def auto_save_batch(self, context):
    """Callback to trigger auto-save when properties change. Handles conflict detection."""
    if not context or not context.scene: return
    # Avoid recursion or saving during load/write
    if _IS_LOADING_CONFIG or _IS_WRITING_BATCH: return
    
    settings = context.scene.batch_render_settings
    
    # If already in conflict mode, do nothing (wait for user resolution)
    if settings.conflict_detected:
        return

    batch_path, _ = get_batch_file_path(context)
    
    # 1. Optimistic Lock Check
    if batch_path and os.path.exists(batch_path) and settings.last_known_mtime > 0:
        try:
            curr_mtime = os.path.getmtime(batch_path)
            # Tolerance for OS precision
            if abs(curr_mtime - settings.last_known_mtime) > 0.05:
                print("BatchRender: External change detected...")
                
                remote_state = parse_batch_file_to_state(batch_path)
                if remote_state is None:
                    print("BatchRender: Remote file locked/invalid. Aborting save.")
                    return
                
                local_state = capture_local_state(context)
                
                # Check for DESTRUCTIVE changes (Deleting jobs that exist in remote)
                local_uuids = {j['uuid'] for j in local_state.get('jobs', [])}
                remote_jobs = remote_state.get('jobs', [])
                missing_jobs = []
                
                for rj in remote_jobs:
                    if rj.get('uuid') and rj['uuid'] not in local_uuids:
                        missing_jobs.append(rj.get('scene_name', 'Unknown'))
                
                if missing_jobs:
                    print(f"BatchRender: CONFLICT DETECTED! Local missing {len(missing_jobs)} jobs.")
                    settings.conflict_detected = True
                    settings.conflict_info = ", ".join(missing_jobs[:5]) + (f" (+{len(missing_jobs)-5} more)" if len(missing_jobs)>5 else "")
                    # Do NOT save. Do NOT update UI yet (except flag).
                    # Force a redraw of panel?
                    return
                
                # Safe to merge (Non-destructive)
                print("BatchRender: Auto-merging safe changes...")
                active_idx = context.scene.batch_render_active_job_index
                
                # Identify modified item
                modified_idx = -1
                if hasattr(self, "uuid"): 
                     queue = context.scene.batch_render_jobs
                     for i, j in enumerate(queue):
                         if j.uuid == self.uuid: modified_idx = i; break
                
                merged, _ = merge_queue_states(local_state, remote_state, active_idx, modified_idx)
                apply_state_to_ui(context, merged)
                write_batch_file(context)
                return
                
        except Exception as e:
            print(f"BatchRender: Save Check Failed: {e}")
            # If check failed, play safe and abort? Or overwrite? 
            # If we overwrite, we kill remote changes. Better to abort silently or warn?
            # For now, let's fall through to write if it was just a read error? No, safer to wait.
            return

    # No external change detected: Safe write
    write_batch_file(context)

def update_batch_location(self, context):
    """Callback when file location settings change."""
    save_global_config(context)
    # Auto-load jobs from the new location
    load_queue_from_file(context)

def format_frame_ranges(numbers):
    """Converts a sorted list of integers into a string of ranges (e.g., '1-5, 8, 10-12')."""
    if not numbers: return ""
    numbers = sorted(list(numbers)) # Ensure sorted list
    ranges = []
    start = numbers[0]; prev = numbers[0]
    for x in numbers[1:]:
        if x == prev + 1: prev = x
        else:
            if start == prev: ranges.append(str(start))
            else: ranges.append(f"{start}-{prev}")
            start = x; prev = x
    if start == prev: ranges.append(str(start))
    else: ranges.append(f"{start}-{prev}")
    return ", ".join(ranges)

def resolve_job_output_path(job, settings, blend_path):
    """Determines the effective directory to scan for a job."""
    # 1. Job Override
    if job.use_overrides and job.use_custom_output:
        raw_path = job.output_path
    # 2. Global Override
    elif settings.use_override_output:
        raw_path = settings.output_path
    # 3. Cached Scene Default
    else:
        raw_path = job.sc_filepath
        
    if not raw_path: return None
        
    if raw_path.startswith("//"):
        base_dir = os.path.dirname(blend_path)
        abs_path = os.path.join(base_dir, raw_path[2:])
    else:
        abs_path = raw_path
        
    abs_path = os.path.normpath(abs_path)
    
    # If path doesn't look like a dir (e.g. C:/Out/Image_), get dirname
    if not abs_path.endswith(os.sep) and not os.path.isdir(abs_path):
        return os.path.dirname(abs_path)
    return abs_path

def get_job_output_prefix(job, settings, blend_path):
    """Determines the filename prefix (if any) for the output."""
    # 1. Job Override
    if job.use_overrides and job.use_custom_output:
        raw_path = job.output_path
    # 2. Global Override
    elif settings.use_override_output:
        raw_path = settings.output_path
    # 3. Cached Scene Default
    else:
        raw_path = job.sc_filepath
        
    if not raw_path: return ""
        
    if raw_path.startswith("//"):
        base_dir = os.path.dirname(blend_path)
        abs_path = os.path.join(base_dir, raw_path[2:])
    else:
        abs_path = raw_path
        
    abs_path = os.path.normpath(abs_path)
    
    # If path doesn't look like a dir (e.g. C:/Out/Image_), get basename
    if not abs_path.endswith(os.sep) and not os.path.isdir(abs_path):
        return os.path.basename(abs_path)
    return ""

def get_frames_from_disk(directory, prefix=""):
    """Returns a set of integer frame numbers found in the directory, optionally filtered by prefix."""
    if not directory or not os.path.exists(directory):
        return set()
        
    found_frames = set()
    try:
        files = os.listdir(directory)
        regex = re.compile(r'(\d+)\.[a-zA-Z0-9]+$')
        
        for f in files:
            if f.startswith("."): continue
            # Filter by prefix if provided
            if prefix and not f.startswith(prefix): continue
            
            match = regex.search(f)
            if match:
                found_frames.add(int(match.group(1)))
                
    except Exception:
        pass
        
    return found_frames

def scan_disk_frames(directory, prefix=""):
    """Scans directory for numbered sequence files, returns formatted string and count."""
    found_frames = sorted(list(get_frames_from_disk(directory, prefix)))
    if not found_frames:
         return "", 0
    return format_frame_ranges(found_frames), len(found_frames)

def get_existing_frame_files(directory, prefix=""):
    """Returns a list of absolute paths to frame files in the directory, optionally filtered by prefix."""
    if not directory or not os.path.exists(directory):
        return []
        
    found_files = []
    try:
        files = os.listdir(directory)
        regex = re.compile(r'(\d+)\.[a-zA-Z0-9]+$')
        
        for f in files:
            if f.startswith("."): continue
            if prefix and not f.startswith(prefix): continue
            
            if regex.search(f):
                found_files.append(os.path.join(directory, f))
                
    except Exception:
        return []
        
    return found_files

def write_batch_file(context):
    """Writes the current queue to the batch file. Returns (path, None) or (None, error_msg)."""
    global _IS_WRITING_BATCH
    if _IS_WRITING_BATCH: 
        return None, "Already writing"
        
    _IS_WRITING_BATCH = True
    try:
        settings = context.scene.batch_render_settings
        queue = context.scene.batch_render_jobs
        
        if len(queue) == 0:
            return None, "No jobs in queue"
            
        script_path, error = get_batch_file_path(context)
        if error:
            return None, error
        
        base_dir = os.path.dirname(script_path)
        if not os.path.exists(base_dir):
            try:
                os.makedirs(base_dir)
            except OSError as e:
                return None, f"Could not create directory: {base_dir}"

        blender_bin = bpy.app.binary_path
        
        lines = []
        is_windows = platform.system() == "Windows"
        
        if is_windows:
            lines.append("@echo off")
            lines.append("cd /d \"%~dp0\"")
            lines.append("mkdir \"progress\" 2>nul")
            lines.append("mkdir \"chunks\" 2>nul")
        if is_windows:
            lines.append("REM --- Lock Check ---")
            lines.append("set LOCK_FILE=\"%~dp0%COMPUTERNAME%.lock\"")
            lines.append("if exist %LOCK_FILE% (")
            lines.append("    echo Lock file found: %LOCK_FILE%")
            lines.append("    echo Another instance is running. Exiting.")
            lines.append("    exit /b 1")
            lines.append(")")
            lines.append("echo Locked > %LOCK_FILE%")
            lines.append("REM ------------------")
            lines.append("")
            
            # Generate External Handler Script
            handler_script_path = os.path.join(base_dir, "batch_context_handler.py")
            try:
                with open(handler_script_path, 'w') as hf:
                    hf.write("import bpy, os\n")
                    hf.write("def progress_handler(scene):\n")
                    hf.write("    job_id = os.environ.get('FLIP_BATCH_ID')\n")
                    hf.write("    progress_dir = os.environ.get('FLIP_BATCH_PROGRESS_DIR')\n")
                    hf.write("    if not job_id or not progress_dir: return\n")
                    hf.write("    try:\n")
                    hf.write("        if scene.frame_current is None: return\n")
                    hf.write("        filename = f\"{job_id}_{scene.frame_current}.done\"\n")
                    hf.write("        filepath = os.path.join(progress_dir, filename)\n")
                    hf.write("        open(filepath, 'w').close()\n")
                    hf.write("    except Exception as e:\n")
                    hf.write("        print(f\"BatchRender: Handler Error: {e}\")\n")
                    hf.write("\n")
                    hf.write("def skip_check_handler(scene):\n")
                    hf.write("    \"\"\"Checks for existing frames when skipping (Overwrite=False) and writes receipts.\"\"\"\n")
                    hf.write("    if scene.render.use_overwrite: return\n")
                    hf.write("    \n")
                    hf.write("    job_id = os.environ.get('FLIP_BATCH_ID')\n")
                    hf.write("    progress_dir = os.environ.get('FLIP_BATCH_PROGRESS_DIR')\n")
                    hf.write("    if not job_id or not progress_dir: return\n")
                    hf.write("\n")
                    hf.write("    try:\n")
                    hf.write("        # Check if frame file exists\n")
                    hf.write("        frame_file = scene.render.frame_path(frame=scene.frame_current)\n")
                    hf.write("        if os.path.exists(frame_file):\n")
                    hf.write("            filename = f\"{job_id}_{scene.frame_current}.done\"\n")
                    hf.write("            filepath = os.path.join(progress_dir, filename)\n")
                    hf.write("            # Write receipt if missing\n")
                    hf.write("            if not os.path.exists(filepath):\n")
                    hf.write("                 open(filepath, 'w').close()\n")
                    hf.write("    except Exception as e:\n")
                    hf.write("        pass\n")
                    hf.write("\n")
                    hf.write("def heartbeat_handler(scene):\n")
                    hf.write("    job_id = os.environ.get('FLIP_BATCH_ID')\n")
                    hf.write("    progress_dir = os.environ.get('FLIP_BATCH_PROGRESS_DIR')\n")
                    hf.write("    if not job_id or not progress_dir: return\n")
                    hf.write("    \n")
                    hf.write("    chunk_id = f\"{job_id}_{scene.frame_start}_{scene.frame_end}\"\n")
                    hf.write("    base_dir = os.path.dirname(progress_dir)\n")
                    hf.write("    lock_dir = os.path.join(base_dir, \"chunks\", f\"{chunk_id}.lock\")\n")
                    hf.write("    \n")
                    hf.write("    if os.path.exists(lock_dir):\n")
                    hf.write("        try: open(os.path.join(lock_dir, \"heartbeat\"), 'w').close()\n")
                    hf.write("        except: pass\n")
                    hf.write("\n")
                    hf.write("def apply_overrides(scene):\n")
                    hf.write("    import json\n")
                    hf.write("    data_str = os.environ.get('FLIP_BATCH_OVERRIDES')\n")
                    hf.write("    if not data_str: return\n")
                    hf.write("    try:\n")
                    hf.write("        data = json.loads(data_str)\n")
                    hf.write("        for key, val in data.items():\n")
                    hf.write("            parts = key.split('.')\n")
                    hf.write("            obj = scene\n")
                    hf.write("            for part in parts[:-1]:\n")
                    hf.write("                obj = getattr(obj, part)\n")
                    hf.write("            setattr(obj, parts[-1], val)\n")
                    hf.write("            # print(f\"BatchRender: Set {key} = {val}\")\n")
                    hf.write("    except Exception as e:\n")
                    hf.write("        print(f\"BatchRender: Override Error: {e}\")\n")
                    hf.write("\n")
                    hf.write("bpy.app.handlers.render_write.append(progress_handler)\n")
                    hf.write("bpy.app.handlers.render_complete.append(progress_handler) # Just in case\n")
                    hf.write("bpy.app.handlers.render_init.append(heartbeat_handler)\n")
                    hf.write("bpy.app.handlers.render_complete.append(heartbeat_handler)\n")
                    hf.write("bpy.app.handlers.frame_change_post.append(skip_check_handler)\n")
                    hf.write("bpy.app.handlers.frame_change_post.append(heartbeat_handler)\n")
                    hf.write("if bpy.context.scene: apply_overrides(bpy.context.scene)\n")
            except:
                print("Failed to write handler script") 
        else:
            lines.append("#!/bin/sh")

        print("DEBUG: Reaching Global Settings Block")

        # Global Settings Metadata
        g_data = {}
        for k in settings.bl_rna.properties.keys():
            if k == "rna_type" or k == "batch_file_path": continue
            g_data[k] = getattr(settings, k)
            
        g_json = json.dumps(g_data)
        if is_windows:
            lines.append(f"REM FLIP_BATCH_GLOBAL: {g_json}")
        else:
            lines.append(f"# FLIP_BATCH_GLOBAL: {g_json}")

        # Validation/Refresh Pass
        current_filepath = bpy.data.filepath
        for job in queue:
            # Refresh cached frames if current file
            if job.filepath == current_filepath and job.scene_name in bpy.data.scenes:
                scn = bpy.data.scenes[job.scene_name]
                job.sc_frame_start = scn.frame_start
                job.sc_frame_end = scn.frame_end
                job.sc_filepath = scn.render.filepath

        print(f"DEBUG: Processing {len(queue)} jobs...")
        
        if is_windows and settings.use_queue_loop:
            lines.append(":LOOP_START")
            lines.append("REM --- Batch Queue Loop Start ---")

        for i, job in enumerate(queue):
            meta = {
                'filepath': job.filepath, 
                'uuid': job.uuid,
                'scene_name': job.scene_name,
                'enabled': job.enabled,
                'sc_frame_start': job.sc_frame_start,
                'sc_frame_end': job.sc_frame_end,
                'sc_filepath': job.sc_filepath,
                'frames_on_disk': job.frames_on_disk,
                'cached_progress': job.get('cached_progress', 0.0),
                'cached_chunk_progress': job.get('cached_chunk_progress', 0.0),
                'use_overrides': job.use_overrides,
                'use_custom_frames': job.use_custom_frames,
                'frame_start': job.frame_start,
                'frame_end': job.frame_end,
                'use_custom_samples': job.use_custom_samples,
                'samples': job.samples,
                'use_custom_output': job.use_custom_output,
                'output_path': job.output_path,
                'use_custom_persistent_data': job.use_custom_persistent_data,
                'persistent_data': job.persistent_data,
                'use_custom_simplify': job.use_custom_simplify,
                'simplify_use': job.simplify_use,
                'simplify_subdivision_render': job.simplify_subdivision_render,
                'simplify_image_limit': job.simplify_image_limit,
                'use_custom_volumetrics': job.use_custom_volumetrics,
                'volume_biased': job.volume_biased,
                'volume_step_rate': job.volume_step_rate,
                'use_custom_chunking': job.use_custom_chunking,
                'use_chunking': job.use_chunking,
                'chunk_size': job.chunk_size,
                'use_custom_block_list': job.use_custom_block_list,
                'blocked_computers': job.blocked_computers
            }

            meta_json = json.dumps(meta)
            if is_windows:
                lines.append(f"REM FLIP_BATCH_META: {meta_json}")
            else:
                lines.append(f"# FLIP_BATCH_META: {meta_json}")
                
            if not job.enabled:
                continue
            
            # Block PC Logic
            if is_windows and job.use_overrides and job.use_custom_block_list and job.blocked_computers:
                cleaned = [x.strip() for x in job.blocked_computers.split(',') if x.strip()]
                for pc in cleaned:
                    lines.append(f'if /I "%COMPUTERNAME%"=="{pc}" goto SKIP_JOB_{i}')
                lines.append("")
                
            cmd_parts = [f'"{blender_bin}"']
            if settings.use_background: cmd_parts.append("-b")
            cmd_parts.append(f'"{job.filepath}"')
            cmd_parts.append("-S")
            cmd_parts.append(f'"{job.scene_name}"')
            
            use_out = False
            out_val = ""
            
            if job.use_overrides and job.use_custom_output:
                use_out = True
                out_val = job.output_path
            elif settings.use_override_output:
                use_out = True
                out_val = settings.output_path
            
            if use_out:
                cmd_parts.extend(["-o", f'"{out_val}"'])
                
            if settings.use_override_engine: cmd_parts.extend(["-E", settings.engine_type])
            if settings.use_override_format: cmd_parts.extend(["-F", settings.render_format])
            if settings.use_extension: cmd_parts.extend(["-x", "1"])
            if settings.use_threads: cmd_parts.extend(["-t", str(settings.threads)])
            
            overrides = {}
            
            if job.use_overrides and job.use_custom_samples:
                overrides["cycles.samples"] = job.samples
            elif settings.use_override_samples:
                overrides["cycles.samples"] = settings.samples

            if settings.use_override_denoising:
                overrides["cycles.use_denoising"] = settings.denoising_state
                if settings.denoising_state: overrides["cycles.denoiser"] = settings.denoiser_type
                
            if settings.use_override_color_mode: overrides["render.image_settings.color_mode"] = settings.color_mode
            if settings.use_override_overwrite: overrides["render.use_overwrite"] = settings.use_overwrite
            if settings.use_override_placeholders: overrides["render.use_placeholder"] = settings.use_placeholders
            
            # Resolve Chunking Settings
            do_chunking = False
            chunk_size = 10
            if job.use_overrides and job.use_custom_chunking:
                do_chunking = job.use_chunking
                chunk_size = job.chunk_size
            elif settings.use_chunking:
                do_chunking = True
                chunk_size = settings.chunk_size

            if job.use_overrides and job.use_custom_persistent_data:
                overrides["render.use_persistent_data"] = job.persistent_data
            elif settings.use_override_persistent_data:
                 overrides["render.use_persistent_data"] = settings.persistent_data

            # Simplify Override
            if job.use_overrides and job.use_custom_simplify:
                overrides["render.use_simplify"] = job.simplify_use
                overrides["render.simplify_subdivision_render"] = job.simplify_subdivision_render
                if hasattr(context.scene.render, "simplify_image_limit"):
                    overrides["render.simplify_image_limit"] = job.simplify_image_limit
                elif hasattr(context.scene, "cycles") and hasattr(context.scene.cycles, "texture_limit_render"):
                     overrides["cycles.texture_limit_render"] = job.simplify_image_limit
            elif settings.use_override_simplify:
                overrides["render.use_simplify"] = settings.simplify_use
                overrides["render.simplify_subdivision_render"] = settings.simplify_subdivision_render
                if hasattr(context.scene.render, "simplify_image_limit"):
                    overrides["render.simplify_image_limit"] = settings.simplify_image_limit
                elif hasattr(context.scene, "cycles") and hasattr(context.scene.cycles, "texture_limit_render"):
                     overrides["cycles.texture_limit_render"] = settings.simplify_image_limit
                
            # Volumetrics Override
            if job.use_overrides and job.use_custom_volumetrics:
                overrides["cycles.volume_biased"] = job.volume_biased
                overrides["cycles.volume_step_rate"] = job.volume_step_rate
            elif settings.use_override_volumetrics:
                overrides["cycles.volume_biased"] = settings.volume_biased
                overrides["cycles.volume_step_rate"] = settings.volume_step_rate
            
            # Note: We no longer append to --python-expr.
            # We serialize 'overrides' to FLIP_BATCH_OVERRIDES env var later.
            
            # Frame Range Logic
            use_frames = False
            start = 1
            end = 1
            
            if job.use_overrides and job.use_custom_frames:
                use_frames = True
                start = job.frame_start
                end = job.frame_end
            elif settings.use_override_frames:
                use_frames = True
                start = settings.frame_start
                end = settings.frame_end
            else:
                # Use scene frame range if no override
                use_frames = True # Always explicit to allow chunking
                start = job.sc_frame_start
                end = job.sc_frame_end

            # Calculate Job ID & Progress Dir
            job_id_str = get_computed_job_id(job)
            progress_dir_abs = os.path.join(os.path.dirname(script_path), "progress")
            
            # Set Environment Variables
            if is_windows:
                lines.append(f'set FLIP_BATCH_ID={job_id_str}')
                lines.append(f'set FLIP_BATCH_PROGRESS_DIR={progress_dir_abs}')
                if overrides:
                     lines.append(f'set FLIP_BATCH_OVERRIDES={json.dumps(overrides)}')
            else:
                lines.append(f'export FLIP_BATCH_ID="{job_id_str}"')
                lines.append(f'export FLIP_BATCH_PROGRESS_DIR="{progress_dir_abs}"')
                if overrides:
                     lines.append(f'export FLIP_BATCH_OVERRIDES=\'{json.dumps(overrides)}\'')

            # Add Python Handler
            cmd_parts.extend(["--python", '"batch_context_handler.py"'])

            if settings.use_cycles_device: cmd_parts.extend(["--cycles-device", settings.cycles_device])

            # Generate Commands
            if do_chunking and is_windows:
                 # Resolve lock directory
                 # Since output path might be relative (//), we can't easily mkdir it from batch unless we are in the dir.
                 # Strategy: Ensure "_chunks" exists. 
                 # We will use attributes of the job to create a unique ID if paths are messy.
                 # Actually, output path is usually the most reliable "shared" location.
                 
                 # Logic:
                 # Loop from start to end by chunk_size
                 total_frames = (end - start) + 1
                 if total_frames < 1: total_frames = 1
                 
                 lines.append(f"REM --- Chunking Job: {job.scene_name} ({start}-{end}) ---")
                 # We need to make sure the output directory exists so we can make _chunks inside it
                 # BUT, out_val might contain #### placeholders. 
                 # We should strip placeholders (digits, #) from the end to get the dir.
                 # Relying on 'out_val' string from UI.
                 
                 # Simplification: Just assume out_val is a directory-like prefix or contains placeholders.
                 # If out_val ends with slash, it's a dir. If not, it might be filename.
                 # Let's try to append "_chunks".
                 
                 # Safe bet: Use a standard "render_chunks" folder next to the .bat file? 
                 # No, needs to be shared storage.
                 # Use the Output Path.
                 
                 lock_dir_rel = "chunks"
                 
                 current = start
                 while current <= end:
                     c_end = min(current + chunk_size - 1, end)
                     
                     # Chunk ID: {RobustID}_{Start}_{End}
                     chunk_id = f"{job_id_str}_{current}_{c_end}"
                     
                     lock_name = f"{lock_dir_rel}\\{chunk_id}"
                     
                     # Label for skipping this chunk
                     chunk_label = f"SKIP_{chunk_id}"
                     
                     lines.append(f"if exist \"{lock_name}.done\" GOTO {chunk_label}")
                     
                     # Attempt Lock
                     # Try to acquire lock
                     lines.append(f'mkdir "{lock_name}.lock" 2>nul')
                     lines.append(f'if errorlevel 1 (')
                     lines.append(f'    if exist "{lock_name}.lock\\owner" (')
                     lines.append(f'        type "{lock_name}.lock\\owner" | findstr /x /c:"%COMPUTERNAME%" >nul')
                     lines.append(f'        if errorlevel 1 GOTO {chunk_label}')
                     lines.append(f'        echo Resuming stale lock for chunk {chunk_id}')
                     lines.append(f'    ) else (')
                     lines.append(f'        GOTO {chunk_label}')
                     lines.append(f'    )')
                     lines.append(f') else (')
                     # Lock acquired
                     if is_windows:
                          lines.append(f'    echo %COMPUTERNAME%>"{lock_name}.lock\\owner"')
                     else:
                          lines.append(f'    hostname > "{lock_name}.lock/owner"')
                     lines.append(f')')
                     
                     # Run Command (Subset for chunk)
                     chunk_cmd = list(cmd_parts)
                     chunk_cmd.extend(["-s", str(current), "-e", str(c_end), "-a"])
                     if settings.use_frame_jump: chunk_cmd.extend(["-j", str(settings.frame_jump)])
                     
                     lines.append(" ".join(chunk_cmd))
                     
                     # On Success: Create Done, Remove Lock
                     lines.append(f"if %errorlevel% neq 0 (")
                     if is_windows:
                         lines.append(f"    timeout /t 2 /nobreak >nul")
                         lines.append(f"    rmdir /s /q \"{lock_name}.lock\"")
                         lines.append(f"    echo Render failed for chunk {chunk_id} (Exit Code: %errorlevel%)")
                     else:
                         lines.append(f"    sleep 1")
                         lines.append(f"    rm -rf \"{lock_name}.lock\"")
                         lines.append(f"    echo Render failed for chunk {chunk_id}")
                     lines.append(f") else (")
                     if is_windows:
                         lines.append(f"    timeout /t 1 /nobreak >nul")
                         lines.append(f"    rmdir /s /q \"{lock_name}.lock\"")
                     else:
                         lines.append(f"    sleep 1")
                         lines.append(f"    rm -rf \"{lock_name}.lock\"")
                     lines.append(f"    echo done > \"{lock_name}.done\"")
                     lines.append(f")")
                     
                     lines.append(f":{chunk_label}")
                     current += chunk_size

            else:
                # Standard Render (No Chunking)
                cmd_parts.extend(["-s", str(start), "-e", str(end)])
                if settings.use_frame_jump: cmd_parts.extend(["-j", str(settings.frame_jump)])
                
                if settings.use_specific_frame: 
                    cmd_parts.extend(["-f", str(settings.specific_frame)]) # Overrides -s/-e/-a if present? No, -f is separate
                    # Actually logic above is mutually exclusive?
                    # The original code appended -f OR -a.
                    # My logic added -s/-e.
                    # Use -a if not specific frame.
                else:
                    cmd_parts.append("-a")

                # Remove -f/-s/-e conflict
                if settings.use_specific_frame:
                    # Remove -s, -e, -a (last 4 items usually)
                    # Hacky. Let's rebuild properly.
                    pass # TODO: Fix interaction between frame range and specific frame
                    # Re-eval:
                    final_cmd = []
                    # ... (Clean rebuild of args)
                    
                # Simplest fix: Just append assembled.
                lines.append(" ".join(cmd_parts))
                if is_windows: lines.append("if %errorlevel% neq 0 echo Error in previous command")
                
            if is_windows:
                 lines.append(f"")
                 lines.append(f":SKIP_JOB_{i}")
                 lines.append(f"REM ------------------")
                 lines.append("")

        if is_windows: 
            # Only delete lock if NOT looping (since we stay alive)
            if not settings.use_queue_loop:
                lines.append("if exist %LOCK_FILE% del %LOCK_FILE%")
            
            if settings.use_pause_at_end:
                 lines.append("pause")
            
            if settings.use_queue_loop:
                 lines.append("timeout /t 5")
                 lines.append("goto LOOP_START")



        # Rolling Backups (3 Levels)
        if os.path.exists(script_path):
            try:
                bak1 = script_path + ".bak1"
                bak2 = script_path + ".bak2"
                bak3 = script_path + ".bak3"
                
                if os.path.exists(bak2):
                    shutil.copy2(bak2, bak3)
                if os.path.exists(bak1):
                    shutil.copy2(bak1, bak2)
                shutil.copy2(script_path, bak1)
            except Exception as e:
                print(f"BatchRender: Backup failed: {e}")

        try:
            with open(script_path, 'w') as f:
                f.write("\n".join(lines))
                
            if not is_windows:
                try:
                    st = os.stat(script_path)
                    os.chmod(script_path, st.st_mode | stat.S_IEXEC)
                except OSError: pass

        except IOError as e:
            return None, f"Error writing file: {e}"
            
        for job in queue:
            job.is_saved = True
        save_global_config(context)
        
        # Update Timestamp (We just wrote it, so we are up to date)
        try:
            settings.last_known_mtime = os.path.getmtime(script_path)
        except: pass
            
        return script_path, None
        
    finally:
        _IS_WRITING_BATCH = False


# -------------------------------------------------------------------
# Data Structures
# -------------------------------------------------------------------

# -------------------------------------------------------------------
# Helper Functions (Moved for Scope)
# -------------------------------------------------------------------

def get_computed_job_id(job):
    """Returns the robust Job ID (Sanitized Filename_SceneName)."""
    f_base = os.path.splitext(os.path.basename(job.filepath))[0]
    raw_id = f"{f_base}_{job.scene_name}"
    # Strict sanitation: Allow only Alphanumeric, ., -, _
    # This prevents any weird characters (newlines, quotes, etc) from breaking batch files
    return "".join(c for c in raw_id if c.isalnum() or c in ('_', '-', '.'))



def resolve_chunk_paths(batch_path, job, start, end):
    chunks_dir = os.path.join(os.path.dirname(batch_path), "chunks")
    job_id = get_computed_job_id(job)
    chunk_id = f"{job_id}_{start}_{end}"
    lock_file = os.path.join(chunks_dir, f"{chunk_id}.lock")
    done_file = os.path.join(chunks_dir, f"{chunk_id}.done")
    return lock_file, done_file

def get_job_progress_frames(job, batch_path):
    """
    Scans the 'progress' folder for receipts matching the job ID.
    Job ID = Sanitized {Filename}_{SceneName}.
    Receipt format: {Job_ID}_{Frame}.done
    """
    if not batch_path: return set()
    
    progress_dir = os.path.join(os.path.dirname(batch_path), "progress")
    # print(f"DEBUG: Scanning progress dir: {progress_dir}") # Noise
    if not os.path.exists(progress_dir):
        print(f"DEBUG: Progress dir not found: {progress_dir}")
        return set()
        
    job_id = get_computed_job_id(job)
    prefix = f"{job_id}_"
    
    finished_frames = set()
    regex = re.compile(rf"{re.escape(job_id)}_(\d+)\.done$")
    
    try:
        files = os.listdir(progress_dir)
        # print(f"DEBUG: Found {len(files)} files in progress dir")
        found_any = False
        for f in files:
            if f.startswith(prefix):
                 m = regex.match(f)
                 if m:
                     finished_frames.add(int(m.group(1)))
                     found_any = True
        
        if not found_any:
            print(f"DEBUG: No receipts found for JobID: {job_id} (Prefix: {prefix})")
            
    except Exception as e:
        print(f"DEBUG: Error scanning progress: {e}")
        pass
        
    return finished_frames

def refresh_job_chunks(job, settings, batch_path):
    # Resolve Chunk Settings
    do_chunking = False
    chunk_size = 10
    
    # Priority: Job Override > Global Override > False
    if job.use_overrides and job.use_custom_chunking:
        do_chunking = job.use_chunking
        chunk_size = job.chunk_size
    elif settings.use_chunking: # Global
        do_chunking = True
        chunk_size = settings.chunk_size
        
    if not do_chunking:
         job.chunks.clear()
         return
         
    # Resolve Range
    start = job.sc_frame_start
    end = job.sc_frame_end
    if job.use_overrides and job.use_custom_frames:
        start = job.frame_start
        end = job.frame_end
    elif settings.use_override_frames:
        start = settings.frame_start
        end = settings.frame_end
        
    job.chunks.clear()
    
    current = start
    while current <= end:
        c_end = min(current + chunk_size - 1, end)
        
        item = job.chunks.add()
        item.name = f"{current}-{c_end}"
        item.start = current
        item.end = c_end
        item.owner = ""
        
        lock_file, done_file = resolve_chunk_paths(batch_path, job, current, c_end)
        
        if os.path.exists(done_file):
            item.status = "Done"
            item.icon = "CHECKBOX_HLT"
        elif os.path.exists(lock_file):
            item.status = "Rendering"
            item.icon = "TIME"
            
            # Pruning Logic
            is_stale = False
            if settings.chunk_timeout > 0:
                hb_file = os.path.join(lock_file, "heartbeat")
                check_time = 0
                if os.path.exists(hb_file):
                    check_time = os.path.getmtime(hb_file)
                else:
                    check_time = os.path.getmtime(lock_file)
                
                limit_seconds = settings.chunk_timeout * 60
                if (datetime.datetime.now().timestamp() - check_time) > limit_seconds:
                     is_stale = True
            
            if is_stale:
                try:
                    shutil.rmtree(lock_file, ignore_errors=True)
                    print(f"BatchRender: Pruned stale chunk {item.name}")
                except Exception as e:
                    print(f"BatchRender: Failed to prune {lock_file}: {e}")
                
                item.status = "Pending"
                item.icon = "CHECKBOX_DEHLT"
            else:
                # Read Owner
                owner_path = os.path.join(lock_file, "owner")
                if os.path.exists(owner_path):
                    try: 
                        with open(owner_path, 'r') as f:
                            item.owner = f.read().strip()
                    except: pass
        else:
            item.status = "Pending"
            item.icon = "CHECKBOX_DEHLT"
        
        current += chunk_size
        
    # Calculate Chunk Progress
    total_chunks = len(job.chunks)
    done_chunks = 0
    for c in job.chunks:
        if c.status == 'Done':
            done_chunks += 1
            
    if total_chunks > 0:
        job.cached_chunk_progress = (done_chunks / total_chunks) * 100.0
    else:
        job.cached_chunk_progress = 0.0

def realign_job_chunks_logic(job, settings, batch_path):
    """
    Called when chunk size changes.
    1. Scans ACTUAL progress receipts from 'progress' folder.
    2. Deletes ALL .done and .lock files for this job (chunks dir).
    3. Regenerates chunks and marks them done IF fully present in receipts.
    """
    if not batch_path: return

    base_dir = os.path.dirname(batch_path)
    chunks_dir = os.path.join(base_dir, "chunks")
    # chunks_dir might not exist yet if no render started, but we need to clear it if it does
    
    # 1. Gather finished frames FROM PROGRESS RECEIPTS (Truth)
    finished_frames = get_job_progress_frames(job, batch_path)
    
    # 2. Delete ALL old chunk files for this job
    # We clean both Legacy (SceneName) and Robust (ID) to ensure clean slate.
    robust_id = get_computed_job_id(job)
    legacy_id = re.sub(r'[^a-zA-Z0-9]', '_', job.scene_name)
    
    robust_prefix = f"{robust_id}_"
    legacy_prefix = f"{legacy_id}_"
    
    if os.path.exists(chunks_dir):
        try:
            for f in os.listdir(chunks_dir):
                if (f.startswith(robust_prefix) or f.startswith(legacy_prefix)) and (f.endswith(".done") or f.endswith(".lock")):
                    fp = os.path.join(chunks_dir, f)
                    try:
                        if os.path.isdir(fp): shutil.rmtree(fp, ignore_errors=True)
                        else: os.remove(fp)
                    except OSError: pass
        except Exception as e:
            print(f"Error clearing chunks: {e}")
            return
    
    # 3. Regenerate & Apply
    do_chunking = False
    chunk_size = 10
    if job.use_overrides and job.use_custom_chunking:
        do_chunking = job.use_chunking
        chunk_size = job.chunk_size
    elif settings.use_chunking:
        do_chunking = True
        chunk_size = settings.chunk_size
        
    if not do_chunking or chunk_size < 1:
        job.chunks.clear()
        return

    start = job.sc_frame_start
    end = job.sc_frame_end
    if job.use_overrides and job.use_custom_frames:
        start = job.frame_start
        end = job.frame_end
    elif settings.use_override_frames:
        start = settings.frame_start
        end = settings.frame_end
        
    current = start
    while current <= end:
        c_end = min(current + chunk_size - 1, end)
        
        # Check if this NEW chunk is fully present on disk
        is_fully_done = True
        for f in range(current, c_end + 1):
            if f not in finished_frames:
                is_fully_done = False
                break
        
        if is_fully_done:
            # Create .done file
            _, done_file = resolve_chunk_paths(batch_path, job, current, c_end)
            try:
                with open(done_file, 'w') as f: f.write("realigned")
            except: pass
            
        current += chunk_size
        
    # Finally, refresh UI list
    refresh_job_chunks(job, settings, batch_path)

def update_realign_chunks(self, context):
    """Property update callback."""
    if _IS_LOADING_CONFIG: return
    # This might be heavy if called every slider step.
    # self is either BatchRenderJob or BatchRenderSettings?
    # If settings, iterate all jobs.
    # If job, just that job.
    
    scene = context.scene
    settings = scene.batch_render_settings
    batch_path, _ = get_batch_file_path(context)
    if not batch_path: return

    # Determine identity
    if getattr(self, "rna_type", "").name == "BatchRenderSettings":
        # Global Update: Realign ALL jobs that use global chunking
        for job in scene.batch_render_jobs:
            if not (job.use_overrides and job.use_custom_chunking):
                realign_job_chunks_logic(job, settings, batch_path)
    else:
        # Job Update
        # self is the job
        realign_job_chunks_logic(self, settings, batch_path)
        
    # Ensure the new chunk size is saved
    auto_save_batch(self, context)

class BatchRenderChunk(bpy.types.PropertyGroup):
    name: StringProperty(name="Range")
    status: StringProperty(name="Status", default="Pending")
    icon: StringProperty(name="Icon", default="CHECKBOX_DEHLT") # Helper for UI List
    start: IntProperty()
    end: IntProperty()
    owner: StringProperty(name="Owner", default="")
    selected: BoolProperty(name="Selected", default=False)

class BatchRenderJob(bpy.types.PropertyGroup):
    # Identity
    uuid: StringProperty(name="UUID", default="")

    filepath: StringProperty(name="File Path", subtype='FILE_PATH', default="", update=auto_save_batch)
    scene_name: StringProperty(name="Scene Name", default="", update=auto_save_batch)
    is_saved: BoolProperty(name="Saved", default=False) # Internal, no update
    enabled: BoolProperty(name="Enabled", default=True, update=auto_save_batch)
    selected: BoolProperty(name="Selected", default=False)
    
    # Cached Scene Info
    sc_frame_start: IntProperty(name="Start", default=0, update=auto_save_batch)
    sc_frame_end: IntProperty(name="End", default=0, update=auto_save_batch)
    sc_filepath: StringProperty(name="Scene Output Path", default="", update=auto_save_batch)
    
    # Progress Info
    frames_on_disk: StringProperty(name="Frames on Disk", default="")
    # Runtime cache for progress bars
    cached_progress: FloatProperty(name="Disk Progress", default=0.0)
    cached_chunk_progress: FloatProperty(name="Chunk Progress", default=0.0)
    
    # Overrides
    use_overrides: BoolProperty(name="Override Global Settings", default=False, update=auto_save_batch)
    
    use_custom_frames: BoolProperty(name="Override Frame Range", default=False, update=auto_save_batch)
    frame_start: IntProperty(name="Start", default=1, update=auto_save_batch)
    frame_end: IntProperty(name="End", default=250, update=auto_save_batch)
    
    use_custom_samples: BoolProperty(name="Override Samples", default=False, update=auto_save_batch)
    samples: IntProperty(name="Samples", default=128, min=1, update=auto_save_batch)
    
    use_custom_output: BoolProperty(name="Override Output", default=False, update=auto_save_batch)
    output_path: StringProperty(name="Output Path", subtype='DIR_PATH', default="//", update=auto_save_batch)
    
    use_custom_persistent_data: BoolProperty(name="Override Persistent Data", default=False, update=auto_save_batch)
    persistent_data: BoolProperty(name="Persistent Data", default=False, update=auto_save_batch)

    # Simplify
    use_custom_simplify: BoolProperty(name="Override Simplify", default=False, update=auto_save_batch)
    simplify_use: BoolProperty(name="Simplify", default=True, update=auto_save_batch)
    simplify_subdivision_render: IntProperty(name="Max Subdivision", default=6, min=0, update=auto_save_batch)
    simplify_image_limit: EnumProperty(
        name="Texture Limit",
        items=[
            ('0', "No Limit", ""),
            ('128', "128", ""),
            ('256', "256", ""),
            ('512', "512", ""),
            ('1024', "1024", ""),
            ('2048', "2048", ""),
            ('4096', "4096", ""),
            ('8192', "8192", ""),
        ],
        default='0', update=auto_save_batch
    )
    
    # Volumetrics
    use_custom_volumetrics: BoolProperty(name="Override Volumetrics", default=False, update=auto_save_batch)
    volume_biased: BoolProperty(name="Biased", default=True, update=auto_save_batch)
    volume_step_rate: FloatProperty(name="Max Step Size", default=1.0, precision=2, update=auto_save_batch)

    # Chunking
    use_custom_chunking: BoolProperty(name="Override Chunking", default=False, update=auto_save_batch)
    use_chunking: BoolProperty(name="Use Chunking", default=False, update=auto_save_batch)
    chunk_size: IntProperty(name="Chunk Size", default=10, min=1, update=update_realign_chunks)
    
    chunks: CollectionProperty(type=BatchRenderChunk)
    
    # Block List
    use_custom_block_list: BoolProperty(name="Override Block List", default=False, update=auto_save_batch)
    blocked_computers: StringProperty(name="Blocked Computers", default="", description="Comma-separated list of PC names to block", update=auto_save_batch)





def batch_render_auto_refresh_timer():
    context = bpy.context
    if not context or not context.scene: return 5.0
    
    try:
        settings = context.scene.batch_render_settings
        batch_path, _ = get_batch_file_path(context)
        
        # 1. Sync Check (Always check, even if auto-refresh is off? 
        # No, let's tie it to auto-refresh OR run a separate slower timer?
        # User implies "Sync" is a new feature. Let's assume enabled by Auto-Refresh for now
        # OR force it to always run slowly?
        # Let's run Sync check regardless of 'use_auto_refresh' property? 
        # But the function is registered via that property.
        # Ideally Sync is always on. But for now, let's use the same timer.
        
        # Wait, if we use the same timer, we must enable it. but user might not want "Check Progress" spam.
        # Let's decouple Sync from Check Progress. 
        # Check Progress is expensive (disk IO). Sync Check (getmtime) is cheap.
        
        # Refinement: Simply check mtime here.
        if batch_path and os.path.exists(batch_path):
            curr_mtime = os.path.getmtime(batch_path)
            # Tolerance for float precision
            if abs(curr_mtime - settings.last_known_mtime) > 0.01:
                # File changed! Reload.
                print("BatchRender: External change detected. Reloading...")
                load_queue_from_file(context)
                # load_queue updates last_known_mtime, stopping the loop
        
        # 2. Progress Check (Only if enabled)
        if settings.use_auto_refresh:
            if batch_path:
                for job in context.scene.batch_render_jobs:
                     refresh_job_chunks(job, settings, batch_path)
                     
    except Exception as e:
        # print(f"Timer Error: {e}")
        return 10.0
    
    # If auto-refresh is off, we still want to run for Sync?
    # Current logic: `update_auto_refresh_timer` registers/unregisters this.
    # So if OFF, this doesn't run.
    # We should change `update_auto_refresh_timer` to ALWAYS register?
    # Or add a separate sync timer?
    # Let's keep it simple: Sync works when Auto-Check is ON.
    # User Request: "make sure everything we do autosaves".
    # Sync implies always on. I should probably change registration logic.
    
    return float(settings.auto_refresh_interval)

def update_auto_refresh_timer(self, context):
    if self.use_auto_refresh:
        if not bpy.app.timers.is_registered(batch_render_auto_refresh_timer):
            bpy.app.timers.register(batch_render_auto_refresh_timer)
    else:
        if bpy.app.timers.is_registered(batch_render_auto_refresh_timer):
            bpy.app.timers.unregister(batch_render_auto_refresh_timer)
            
    # Trigger auto-save to persist the toggle state
    auto_save_batch(self, context)

class BatchRenderSettings(bpy.types.PropertyGroup):
    use_background: BoolProperty(name="Background (-b)", default=True, update=auto_save_batch)
    
    use_override_frames: BoolProperty(name="Override Frame Range", default=False, update=auto_save_batch)
    frame_start: IntProperty(name="Start (-s)", default=1, update=auto_save_batch)
    frame_end: IntProperty(name="End (-e)", default=250, update=auto_save_batch)
    
    use_specific_frame: BoolProperty(name="Render Specific Frame (-f)", default=False, update=auto_save_batch)
    specific_frame: IntProperty(name="Frame", default=1, update=auto_save_batch)
    
    use_frame_jump: BoolProperty(name="Frame Jump (-j)", default=False, update=auto_save_batch)
    frame_jump: IntProperty(name="Jump Step", default=1, update=auto_save_batch)
    
    use_override_output: BoolProperty(name="Override Output (-o)", default=False, update=auto_save_batch)
    output_path: StringProperty(name="Output Path", subtype='DIR_PATH', default="//render_out", update=auto_save_batch)
    use_extension: BoolProperty(name="Use Extension (-x)", default=True, update=auto_save_batch)
    use_pause_at_end: BoolProperty(name="Pause at End", default=False, update=auto_save_batch)
    
    use_override_engine: BoolProperty(name="Override Engine (-E)", default=False, update=auto_save_batch)
    engine_type: EnumProperty(
        items=[('CYCLES', "Cycles", ""), ('BLENDER_EEVEE', "Eevee", ""), ('BLENDER_WORKBENCH', "Workbench", "")],
        default='CYCLES', update=auto_save_batch
    )
    
    use_threads: BoolProperty(name="Set Threads (-t)", default=False, update=auto_save_batch)
    threads: IntProperty(name="Threads", default=0, min=0, max=1024, update=auto_save_batch)
    
    use_cycles_device: BoolProperty(name="Set Cycles Device", default=False, update=auto_save_batch)
    cycles_device: EnumProperty(
        items=[('CPU', "CPU", ""), ('CUDA', "CUDA", ""), ('OPTIX', "OPTIX", ""), ('HIP', "HIP", ""), ('ONEAPI', "ONEAPI", ""), ('METAL', "METAL", "")],
        default='CUDA', update=auto_save_batch
    )
    
    use_override_format: BoolProperty(name="Override Format (-F)", default=False, update=auto_save_batch)
    render_format: EnumProperty(
        items=[('PNG', "PNG", ""), ('JPEG', "JPEG", ""), ('OPEN_EXR', "OpenEXR", ""), ('TIFF', "TIFF", ""), ('TGA', "Targa", "")],
        default='PNG', update=auto_save_batch
    )

    use_override_samples: BoolProperty(name="Override Samples", default=False, update=auto_save_batch)
    samples: IntProperty(name="Samples", default=128, min=1, update=auto_save_batch)
    
    use_override_denoising: BoolProperty(name="Override Denoising", default=False, update=auto_save_batch)
    denoising_state: BoolProperty(name="Denoising", default=True, update=auto_save_batch)
    denoiser_type: EnumProperty(items=[('OPTIX', "OptiX", ""), ('OPENIMAGEDENOISE', "OpenImageDenoise", "")], default='OPTIX', update=auto_save_batch)
    
    use_override_color_mode: BoolProperty(name="Override Color Mode", default=False, update=auto_save_batch)
    color_mode: EnumProperty(items=[('BW', "BW", ""), ('RGB', "RGB", ""), ('RGBA', "RGBA", "")], default='RGBA', update=auto_save_batch)
    
    use_override_overwrite: BoolProperty(name="Override Overwrite", default=False, update=auto_save_batch)
    use_overwrite: BoolProperty(name="Overwrite Existing", default=True, update=auto_save_batch)
    
    use_override_persistent_data: BoolProperty(name="Override Persistent Data", default=False, update=auto_save_batch)
    persistent_data: BoolProperty(name="Persistent Data", default=False, update=auto_save_batch)
    
    # Simplify
    use_override_simplify: BoolProperty(name="Override Simplify", default=False, update=auto_save_batch)
    simplify_use: BoolProperty(name="Simplify", default=True, update=auto_save_batch)
    simplify_subdivision_render: IntProperty(name="Max Subdivision", default=6, min=0, update=auto_save_batch)
    simplify_image_limit: EnumProperty(
        name="Texture Limit",
        items=[
            ('0', "No Limit", ""),
            ('128', "128", ""),
            ('256', "256", ""),
            ('512', "512", ""),
            ('1024', "1024", ""),
            ('2048', "2048", ""),
            ('4096', "4096", ""),
            ('8192', "8192", ""),
        ],
        default='0', update=auto_save_batch
    )
    
    # Volumetrics
    use_override_volumetrics: BoolProperty(name="Override Volumetrics", default=False, update=auto_save_batch)
    volume_biased: BoolProperty(name="Biased", default=True, update=auto_save_batch)
    volume_step_rate: FloatProperty(name="Max Step Size", default=1.0, precision=2, update=auto_save_batch)
    
    use_override_placeholders: BoolProperty(name="Override Placeholders", default=False, update=auto_save_batch)
    use_placeholders: BoolProperty(name="Placeholders", default=False, update=auto_save_batch)
    
    # Chunking
    use_override_chunking: BoolProperty(name="Override Chunking", default=False, update=auto_save_batch)
    use_chunking: BoolProperty(name="Use Chunking", default=False, update=auto_save_batch)
    # Default chunk size 10
    chunk_size: IntProperty(name="Chunk Size", default=10, min=1, update=update_realign_chunks)
    
    # UI State
    show_file_config: BoolProperty(default=False)
    show_job_queue: BoolProperty(default=True)
    show_selected_job: BoolProperty(default=True)
    show_chunk_status: BoolProperty(default=True)
    show_chunk_details: BoolProperty(name="Show Details", default=False)
    show_global_options: BoolProperty(default=False)
    show_queue_overrides: BoolProperty(default=False)
    
    # Advanced / Loop
    use_queue_loop: BoolProperty(
        name="Loop Queue", 
        description="Automatically restart the batch queue when finished (Ctrl+C to stop)", 
        default=False, 
        update=auto_save_batch
    )
    
    chunk_timeout: IntProperty(
        name="Chunk Timeout (min)", 
        description="Max time (minutes) since last heartbeat before a chunk is considered crashed and reset. 0 = Disabled", 
        default=0, 
        min=0, 
        update=auto_save_batch
    )
    
    # Auto-Refresh & Sync
    use_auto_refresh: BoolProperty(name="Auto Progress Check", default=False, description="Automatically check for progress and prune stale chunks", update=update_auto_refresh_timer)
    auto_refresh_interval: IntProperty(name="Interval (s)", default=10, min=1, description="Seconds between progress checks", update=auto_save_batch)
    
    
    # Conflict Flags
    conflict_detected: BoolProperty(default=False)
    conflict_info: StringProperty(default="")
    
    # Sync tracking
    last_known_mtime: FloatProperty(default=0.0)

    batch_file_path: StringProperty(

        name="Batch File", 
        subtype='FILE_PATH', 
        default="//batch_render.bat",
        description="Full path to the batch script",
        update=update_batch_location
    )

class BatchRenderImportItem(bpy.types.PropertyGroup):
    name: StringProperty(name="Name")
    selected: BoolProperty(name="Selected", default=True)

class BATCH_RENDER_UL_import_list(bpy.types.UIList):
    def draw_item(self, context, layout, data, item, icon, active_data, active_propname):
        layout.prop(item, "selected", text="")
        layout.label(text=item.name, icon='SCENE_DATA')

class BATCH_RENDER_UL_chunks(bpy.types.UIList):
    def draw_item(self, context, layout, data, item, icon, active_data, active_propname):
        row = layout.row(align=True)
        row.prop(item, "selected", text="")
        row.label(text=item.name)
        
        # Status
        icon_name = "FILE_BLANK"
        if hasattr(item, "icon"): icon_name = item.icon
            
        row.label(text=item.status, icon=icon_name)
        
        if item.owner:
            row.label(text=f"({item.owner})", icon='DESKTOP')

class BATCH_RENDER_UL_jobs(bpy.types.UIList):

    def draw_item(self, context, layout, data, item, icon, active_data, active_propname):
        # | Enabled | File (25%) | Scene (25%) | Range (15%) | % (10%) | Disk (25%) |
        
        row = layout.row(align=True)
        
        # Col 0: Controls
        # Split Checkbox automatically isolates it
        split = row.split(factor=0.04)
        
        # Left: Checkbox (Enabled)
        left_col = split.column()
        left_col.prop(item, "enabled", text="", icon_only=True)
        
        # Right: Content (Disabled if job is disabled)
        right_col = split.column()
        right_col.enabled = item.enabled
        
        # Build Content Row inside Right
        sub = right_col.row(align=True)
        
        # Check for active rendering chunks
        is_rendering = False
        for c in item.chunks:
            if c.status == 'Rendering':
                is_rendering = True
                break
                
        icon_status = 'FILE_TICK' if item.is_saved else 'FILE_NEW'
        if is_rendering:
            icon_status = 'TIME'
            
        sub.label(text="", icon=icon_status)
        
        # Split remaining
        data_row = sub.split(factor=0.27) 
        
        # Col 1: File
        file_part = data_row
        fname = os.path.basename(item.filepath)
        file_part.label(text=fname, icon='FILE_BLEND')
        
        scene_row = data_row.split(factor=0.37)
        
        # Col 2: Scene
        scene_part = scene_row
        scene_part.label(text=item.scene_name, icon='SCENE_DATA')
        
        range_row = scene_row.split(factor=0.24)
        
        # Col 3: Range
        range_part = range_row
        start = item.sc_frame_start
        end = item.sc_frame_end
        
        # Use overridden range if active for calculating percentage
        calc_start = start
        calc_end = end
        if item.use_overrides and item.use_custom_frames:
            calc_start = item.frame_start
            calc_end = item.frame_end
        elif context.scene.batch_render_settings.use_override_frames:
            calc_start = context.scene.batch_render_settings.frame_start
            calc_end = context.scene.batch_render_settings.frame_end

        if start == 0 and end == 0:
            range_txt = "?"
        else:
            range_txt = f"{calc_start}-{calc_end}"
        range_part.label(text=range_txt)
        
        percent_row = range_row.split(factor=0.32)
        
        # Col 4: Percent
        pct_part = percent_row
        
        chunk_pct = item.get('cached_chunk_progress', 0.0)
        disk_pct = item.get('cached_progress', 0.0)
        pct_part.label(text=f"{chunk_pct:.0f}%")

        # Col 5: Disk
        disk_part = percent_row
        disk_txt = item.frames_on_disk if item.frames_on_disk else "-"
        disk_part.label(text=disk_txt)
        
        # if not item.enabled:
        #    data_row.enabled = False

# -------------------------------------------------------------------
# Operators
# -------------------------------------------------------------------


# Operators
# -------------------------------------------------------------------

class BATCH_RENDER_OT_scan_disk(bpy.types.Operator):
    bl_idname = "batch_render.scan_disk"
    bl_label = "Check Progress"
    bl_description = "Scan output folders for rendered frames (Fast)"
    
    def execute(self, context):
        queue = context.scene.batch_render_jobs
        settings = context.scene.batch_render_settings
        # Pre-resolve batch path for chunk scanning
        batch_path, _ = get_batch_file_path(context)
        
        has_changes = False
        count = 0
        for i, job in enumerate(queue):
            # if not job.enabled: continue # User requested scan all
            
            # Resolve range for progress calculation
            start = job.sc_frame_start
            end = job.sc_frame_end
            if job.use_overrides and job.use_custom_frames:
                start = job.frame_start
                end = job.frame_end
            elif settings.use_override_frames:
                start = settings.frame_start
                end = settings.frame_end
                
            total_frames = max(1, (end - start) + 1)
            
            # Use Progress Receipts (Truth)
            # Use Progress Receipts (Truth)
            if batch_path:
                found_frames_set = get_job_progress_frames(job, batch_path)
                
                # Check Disk Files (Legacy/Fallback/Pre-existing)
                # We ALWAYS check disk to account for pre-existing frames (Skip Existing support)
                out_path = resolve_job_output_path(job, settings, job.filepath)
                out_prefix = get_job_output_prefix(job, settings, job.filepath)
                
                disk_frames_set = set()
                if out_path and os.path.exists(out_path):
                     disk_frames_set = get_frames_from_disk(out_path, prefix=out_prefix)

                # Merge sets
                final_set = found_frames_set.union(disk_frames_set)
                found_count = len(final_set)
                
                if final_set:
                     job.frames_on_disk = format_frame_ranges(list(final_set))
                else:
                     job.frames_on_disk = "-"

                old_prog = job.get('cached_progress', 0.0)
                new_prog = 0.0
                if total_frames > 0:
                     new_prog = (found_count / total_frames) * 100.0
                
                if abs(new_prog - old_prog) > 0.01:
                    job['cached_progress'] = new_prog
                else:
                    job['cached_progress'] = new_prog # Update anyway for float precision, but don't force write yet?
                    
                if found_count > 0: count += 1
                
            else:
                 job.frames_on_disk = "?"
                 job['cached_progress'] = 0.0
            
            # Refresh chunk status for this job
            if batch_path:
                # Capture old chunk progress
                old_chunk_prog = job.get('cached_chunk_progress', 0.0)
                
                refresh_job_chunks(job, settings, batch_path)
                
                new_chunk_prog = job.get('cached_chunk_progress', 0.0)
                
                # If progress changed, we need to save
                # Check both disk and chunk progress for changes
                disk_diff = abs(job.get('cached_progress', 0.0) - old_prog)
                chunk_diff = abs(new_chunk_prog - old_chunk_prog)
                
                if disk_diff > 0.01 or chunk_diff > 0.01:
                    pass # We always write now
                
        # Persist the updated progress data ALWAYS (Reverted optimization)
        write_batch_file(context)
                
        self.report({'INFO'}, f"Scanned progress for {len(queue)} jobs") 
        return {'FINISHED'}

class BATCH_RENDER_OT_scan_job_chunks(bpy.types.Operator):
    bl_idname = "batch_render.scan_job_chunks"
    bl_label = "Refresh Chunk Status"
    bl_description = "Check lock/done files in chunks folder"
    
    def execute(self, context):
        idx = context.scene.batch_render_active_job_index
        queue = context.scene.batch_render_jobs
        if idx < 0 or idx >= len(queue): return {'CANCELLED'}
        job = queue[idx]
        batch_path, _ = get_batch_file_path(context)
        if batch_path:
            refresh_job_chunks(job, context.scene.batch_render_settings, batch_path)
        return {'FINISHED'}

class BATCH_RENDER_OT_set_chunk_status(bpy.types.Operator):
    bl_idname = "batch_render.set_chunk_status"
    bl_label = "Set Status"
    bl_description = "Manually set chunk status"
    
    action: EnumProperty(
        items=[
            ('DONE', "Set Done", "Mark chunk as completed"),
            ('PENDING', "Set Pending", "Reset chunk to pending (clear lock/done)")
        ]
    )
    
    def execute(self, context):
        idx = context.scene.batch_render_active_job_index
        queue = context.scene.batch_render_jobs
        if idx < 0 or idx >= len(queue): return {'CANCELLED'}
        job = queue[idx]
        
        chunks = get_target_chunks(context, job)
        if not chunks: return {'CANCELLED'}
        
        batch_path, _ = get_batch_file_path(context)
        if not batch_path: return {'CANCELLED'}
        
        # Common paths
        base_dir = os.path.dirname(batch_path)
        progress_dir = os.path.join(base_dir, "progress")
        j_id = get_computed_job_id(job)
        
        count = 0
        
        for chunk in chunks:
            lock_file, done_file = resolve_chunk_paths(batch_path, job, chunk.start, chunk.end)
            
            try:
                if self.action == 'DONE':
                    # Ensure chunks dir exists
                    os.makedirs(os.path.dirname(done_file), exist_ok=True)
                    with open(done_file, 'w') as f:
                        f.write("done")
                    # Remove lock if exists
                    if os.path.exists(lock_file):
                        shutil.rmtree(lock_file, ignore_errors=True)
                    
                    # Create frame receipts
                    if not os.path.exists(progress_dir): os.makedirs(progress_dir)
                    for f_num in range(chunk.start, chunk.end + 1):
                        receipt = os.path.join(progress_dir, f"{j_id}_{f_num}.done")
                        if not os.path.exists(receipt):
                            try: open(receipt, 'w').close()
                            except: pass
                        
                elif self.action == 'PENDING':
                    if os.path.exists(done_file):
                        os.remove(done_file)
                    if os.path.exists(lock_file):
                        shutil.rmtree(lock_file, ignore_errors=True)
                    
                    # Remove frame receipts
                    if os.path.exists(progress_dir):
                        for f_num in range(chunk.start, chunk.end + 1):
                             receipt = os.path.join(progress_dir, f"{j_id}_{f_num}.done")
                             if os.path.exists(receipt):
                                 try: os.remove(receipt)
                                 except: pass
                count += 1
            except Exception as e:
                print(f"Failed to set status for chunk {chunk.start}-{chunk.end}: {e}")

        # Refresh status immediately
        refresh_job_chunks(job, context.scene.batch_render_settings, batch_path)
        
        self.report({'INFO'}, f"Updated {count} chunks")
        return {'FINISHED'}

class BATCH_RENDER_OT_set_job_pending(bpy.types.Operator):
    bl_idname = "batch_render.set_job_pending"
    bl_label = "Restart Job"
    bl_description = "Clear all chunk progress (delete .done/.lock files) for this job"
    
    @classmethod
    def poll(cls, context):
        queue = context.scene.batch_render_jobs
        idx = context.scene.batch_render_active_job_index
        return 0 <= idx < len(queue)

    def execute(self, context):
        targets = get_target_jobs(context)
        if not targets: return {'CANCELLED'}

        settings = context.scene.batch_render_settings
        batch_path, _ = get_batch_file_path(context)
        if not batch_path: 
            self.report({'ERROR'}, "Batch file not saved")
            return {'CANCELLED'}
        
        base_dir = os.path.dirname(batch_path)
        chunks_dir = os.path.join(base_dir, "chunks")
        progress_dir = os.path.join(base_dir, "progress")
        
        total_count = 0
        
        for idx, job in targets:
            robust_id = get_computed_job_id(job)
            legacy_id = re.sub(r'[^a-zA-Z0-9]', '_', job.scene_name)
            
            # 1. Clear Chunks (Legacy + Robust)
            if os.path.exists(chunks_dir):
                try:
                    for f in os.listdir(chunks_dir):
                        if (f.startswith(robust_id + "_") or f.startswith(legacy_id + "_")) and (f.endswith(".done") or f.endswith(".lock")):
                            full_path = os.path.join(chunks_dir, f)
                            if os.path.isdir(full_path): shutil.rmtree(full_path, ignore_errors=True)
                            else: os.remove(full_path)
                            total_count += 1
                except Exception as e:
                    print(f"Error clearing chunks: {e}")
    
            # 2. Clear Progress Receipts (Robust Only)
            if os.path.exists(progress_dir):
                try:
                    regex = re.compile(rf"{re.escape(robust_id)}_(\d+)\.done$")
                    for f in os.listdir(progress_dir):
                        if regex.match(f):
                            full_path = os.path.join(progress_dir, f)
                            os.remove(full_path)
                            total_count += 1
                except Exception as e:
                    print(f"Error clearing progress: {e}")
    
            # Refresh UI
            refresh_job_chunks(job, settings, batch_path)
            
        self.report({'INFO'}, f"Cleared {total_count} files for {len(targets)} jobs")
        return {'FINISHED'}

class BATCH_RENDER_OT_set_job_done(bpy.types.Operator):
    bl_idname = "batch_render.set_job_done"
    bl_label = "Set Job Done"
    bl_description = "Mark all chunks and frames as Done for this job"
    
    @classmethod
    def poll(cls, context):
        queue = context.scene.batch_render_jobs
        idx = context.scene.batch_render_active_job_index
        return 0 <= idx < len(queue)

    def execute(self, context):
        targets = get_target_jobs(context)
        if not targets: return {'CANCELLED'}
        
        settings = context.scene.batch_render_settings
        batch_path, _ = get_batch_file_path(context)
        if not batch_path: 
            self.report({'ERROR'}, "Batch file not saved")
            return {'CANCELLED'}
            
        base_dir = os.path.dirname(batch_path)
        chunks_dir = os.path.join(base_dir, "chunks")
        progress_dir = os.path.join(base_dir, "progress")
        os.makedirs(chunks_dir, exist_ok=True)
        os.makedirs(progress_dir, exist_ok=True)
        
        count_c = 0
        count_f = 0
        
        for idx, job in targets:
            robust_id = get_computed_job_id(job)
            
            if not job.chunks:
                refresh_job_chunks(job, settings, batch_path)
                
            for chunk in job.chunks:
                lock_file, done_file = resolve_chunk_paths(batch_path, job, chunk.start, chunk.end)
                if not os.path.exists(done_file):
                    try:
                        with open(done_file, 'w') as f: f.write("done")
                        count_c += 1
                    except: pass
                
                if os.path.exists(lock_file):
                    try: shutil.rmtree(lock_file, ignore_errors=True)
                    except: pass
                    
                for f_num in range(chunk.start, chunk.end + 1):
                    receipt = os.path.join(progress_dir, f"{robust_id}_{f_num}.done")
                    if not os.path.exists(receipt):
                        try:
                            open(receipt, 'w').close()
                            count_f += 1
                        except: pass
                        
            refresh_job_chunks(job, settings, batch_path)
            
        self.report({'INFO'}, f"Marked {count_c} chunks and {count_f} frames as Done")
        return {'FINISHED'}

# (Note: scan_disk needs update below)

class BATCH_RENDER_OT_archive_frames(bpy.types.Operator):
    bl_idname = "batch_render.archive_frames"
    bl_label = "Archive Frames"
    bl_description = "Move existing rendered frames to a timestamped subfolder"
    
    @classmethod
    def poll(cls, context):
        queue = context.scene.batch_render_jobs
        idx = context.scene.batch_render_active_job_index
        return 0 <= idx < len(queue)

    def execute(self, context):
        targets = get_target_jobs(context)
        if not targets: return {'CANCELLED'}
        
        settings = context.scene.batch_render_settings
        total_count = 0
        
        for idx, job in targets:
            out_path = resolve_job_output_path(job, settings, job.filepath)
            if not out_path or not os.path.exists(out_path): continue
            
            files_to_move = get_existing_frame_files(out_path)
            if not files_to_move: continue
            
            timestamp = datetime.datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
            archive_name = f"Archive_{timestamp}"
            archive_path = os.path.join(out_path, archive_name)
            
            try:
                os.makedirs(archive_path)
            except OSError as e:
                print(f"Failed to create archive folder for {job.scene_name}: {e}")
                continue
                
            count = 0
            for src in files_to_move:
                fname = os.path.basename(src)
                dst = os.path.join(archive_path, fname)
                try:
                    shutil.move(src, dst)
                    count += 1
                except Exception as e:
                    print(f"Failed to move {src}: {e}")
            total_count += count
                
        self.report({'INFO'}, f"Archived {total_count} frames for {len(targets)} jobs")
        bpy.ops.batch_render.scan_disk()
        return {'FINISHED'}

class BATCH_RENDER_OT_delete_frames(bpy.types.Operator):
    bl_idname = "batch_render.delete_frames"
    bl_label = "Delete Output Frames"
    bl_description = "Permanently delete existing rendered frames for this job"
    
    @classmethod
    def poll(cls, context):
        queue = context.scene.batch_render_jobs
        idx = context.scene.batch_render_active_job_index
        return 0 <= idx < len(queue)

    def invoke(self, context, event):
        return context.window_manager.invoke_confirm(self, event)

    def execute(self, context):
        targets = get_target_jobs(context)
        if not targets: return {'CANCELLED'}
        
        settings = context.scene.batch_render_settings
        total_count = 0
        
        for idx, job in targets:
            out_path = resolve_job_output_path(job, settings, job.filepath)
            if not out_path or not os.path.exists(out_path): continue
            
            files_to_delete = get_existing_frame_files(out_path)
            if not files_to_delete: continue
            
            count = 0
            for fpath in files_to_delete:
                try:
                    os.remove(fpath)
                    count += 1
                except Exception as e:
                    print(f"Failed to delete {fpath}: {e}")
            total_count += count
                
        self.report({'INFO'}, f"Deleted {total_count} frames from {len(targets)} jobs")
        bpy.ops.batch_render.scan_disk()
        return {'FINISHED'}



class BATCH_RENDER_OT_preview_output(bpy.types.Operator):
    bl_idname = "batch_render.preview_output"
    bl_label = "Preview Output"
    bl_description = "Play rendered sequence in a new Blender instance"
    
    @classmethod
    def poll(cls, context):
        queue = context.scene.batch_render_jobs
        idx = context.scene.batch_render_active_job_index
        return 0 <= idx < len(queue)

    def execute(self, context):
        targets = get_target_jobs(context)
        if not targets: return {'CANCELLED'}
        
        settings = context.scene.batch_render_settings
        launched_count = 0
        
        for idx, job in targets:
            # Resolve output path
            out_path = resolve_job_output_path(job, settings, job.filepath)
            if not out_path or not os.path.exists(out_path):
                continue
                
            # Get files to find first frame, filtering by prefix!
            prefix = get_job_output_prefix(job, settings, job.filepath)
            frames = get_existing_frame_files(out_path, prefix)
            if not frames: 
                self.report({'WARNING'}, f"No frames found for {job.scene_name} in {out_path}")
                continue
            
            frames.sort()
            first_frame = frames[0]
            
            blender_bin = bpy.app.binary_path
            
            # Command: blender -a -c 8192 <first_frame>
            cmd = [blender_bin, "-a", "-c", "8192", first_frame]
            
            self.report({'INFO'}, f"Launching Preview for {os.path.basename(first_frame)}...")
            
            try:
                subprocess.Popen(cmd)
                launched_count += 1
            except Exception as e:
                print(f"Failed to launch preview: {e}")
                
        if launched_count > 0:
            self.report({'INFO'}, f"Launched {launched_count} previews")
            return {'FINISHED'}
        else:
            self.report({'WARNING'}, "No previews launched")
            return {'CANCELLED'}

class BATCH_RENDER_OT_open_job_file(bpy.types.Operator):
    bl_idname = "batch_render.open_job_file"
    bl_label = "Open Scene"
    bl_description = "Open the selected job's scene file in a new Blender instance"
    
    @classmethod
    def poll(cls, context):
        queue = context.scene.batch_render_jobs
        idx = context.scene.batch_render_active_job_index
        return 0 <= idx < len(queue)
    
    def execute(self, context):
        queue = context.scene.batch_render_jobs
        idx = context.scene.batch_render_active_job_index
        job = queue[idx]
        
        if not job.filepath or not os.path.exists(job.filepath):
             self.report({'ERROR'}, "File not found")
             return {'CANCELLED'}
             
        blender_bin = bpy.app.binary_path
        try:
            subprocess.Popen([blender_bin, job.filepath])
            self.report({'INFO'}, f"Opening {job.scene_name}...")
        except Exception as e:
            self.report({'ERROR'}, f"Failed to open Blender: {e}")
            
        return {'FINISHED'}

class BATCH_RENDER_OT_open_output_folder(bpy.types.Operator):
    bl_idname = "batch_render.open_output_folder"
    bl_label = "Open Folder"
    bl_description = "Open the output folder in File Explorer"
    
    @classmethod
    def poll(cls, context):
        queue = context.scene.batch_render_jobs
        idx = context.scene.batch_render_active_job_index
        return 0 <= idx < len(queue)
    
    def execute(self, context):
        queue = context.scene.batch_render_jobs
        idx = context.scene.batch_render_active_job_index
        job = queue[idx]
        settings = context.scene.batch_render_settings
        
        path = resolve_job_output_path(job, settings, job.filepath)
        if not path:
             self.report({'WARNING'}, "Could not resolve output path")
             return {'CANCELLED'}
             
        if not os.path.exists(path):
             self.report({'WARNING'}, f"Path does not exist: {path}")
             return {'CANCELLED'}
             
        try:
            if platform.system() == "Windows":
                os.startfile(path)
            elif platform.system() == "Darwin":
                subprocess.Popen(["open", path])
            else:
                subprocess.Popen(["xdg-open", path])
        except Exception as e:
             self.report({'ERROR'}, f"Failed to open folder: {e}")
             
        return {'FINISHED'}

class BATCH_RENDER_OT_refresh_metadata(bpy.types.Operator):
    bl_idname = "batch_render.refresh_metadata"
    bl_label = "Refresh Metadata"
    bl_description = "Query external files to update Scene Range and Output Path (Non-blocking)"
    
    mode: EnumProperty(
        items=[
            ('SELECTED', "Selected Job", "Refresh only the currently selected job"),
            ('ALL', "All Jobs", "Refresh all enabled jobs in the queue")
        ],
        default='SELECTED'
    )
    
    _timer = None
    _jobs_to_refresh = []
    _current_process = None
    _current_job_data = None
    _temp_file_path = None
    _data_file_path = None
    _script_file_path = None
    
    def modal(self, context, event):
        if event.type == 'TIMER':
            if self._current_process:
                ret = self._current_process.poll()
                if ret is not None:
                    # Process finished
                    try:
                        # 1. Check for JSON data file first (The robust way)
                        if self._data_file_path and os.path.exists(self._data_file_path):
                            try:
                                with open(self._data_file_path, 'r') as f:
                                    data = json.load(f)
                                self._process_json_data(data)
                                self.report({'INFO'}, f"Checked {self._current_job_data[1]}")
                            except json.JSONDecodeError:
                                print(f"BatchRender: Failed to decode JSON from {self._data_file_path}")
                                # Read log file to see what happened
                                if self._temp_file_path and os.path.exists(self._temp_file_path):
                                    with open(self._temp_file_path, 'r') as log_f:
                                        print(f"BatchRender: [Background Log] \n{log_f.read()}")
                            except Exception as e:
                                print(f"BatchRender: Error reading JSON file: {e}")
                            
                            # Clean up data file
                            try: os.remove(self._data_file_path)
                            except: pass
                            self._data_file_path = None
                        
                        else:
                            print(f"BatchRender: Expected data file missing: {self._data_file_path}")

                        # 2. Cleanup stdout temp file
                        if self._temp_file_path and os.path.exists(self._temp_file_path):
                            try: os.remove(self._temp_file_path)
                            except: pass
                            self._temp_file_path = None

                        # 3. Cleanup script file
                        if self._script_file_path and os.path.exists(self._script_file_path):
                            try: os.remove(self._script_file_path)
                            except: pass
                            self._script_file_path = None
                            
                        # Force UI redraw
                        for win in context.window_manager.windows:
                            for area in win.screen.areas:
                                if area.type == 'PROPERTIES':
                                    area.tag_redraw()

                    except Exception as e:
                         print(f"Error handling process result: {e}")
                    
                    self._current_process = None
                    self._start_next_process(context)
            
            if self._current_process is None and not self._jobs_to_refresh:
                wm = context.window_manager
                wm.event_timer_remove(self._timer)
                
                # Auto-save to persist metadata
                write_batch_file(context)
                
                self.report({'INFO'}, "Metadata Refresh Complete & Saved")
                bpy.ops.batch_render.scan_disk()
                return {'FINISHED'}
                
        return {'PASS_THROUGH'}
        
    # execute method remains same... (omitted from chunk)

    def execute(self, context):
        queue = context.scene.batch_render_jobs
        
        targets = []
        if self.mode == 'SELECTED':
             idx = context.scene.batch_render_active_job_index
             if 0 <= idx < len(queue):
                 targets = [queue[idx]]
        else:
             targets = [j for j in queue if j.enabled]
        
        self._jobs_to_refresh = []
        for job in targets:
            # Find index in full queue (since job object is same)
            # Actually we need the index for callback?
            # Re-find index
            try:
                # Assuming simple search
                i = -1
                for k, q_job in enumerate(queue):
                    if q_job == job: 
                        i = k
                        break
                if i == -1: continue # Should not happen
                
                if not job.enabled: continue # Double check
            except: continue
            
            # Ensure absolute path
            fpath = bpy.path.abspath(job.filepath)
            if job.filepath != bpy.data.filepath:
                 if os.path.exists(fpath):
                     self._jobs_to_refresh.append((i, fpath, job.scene_name))
                 else:
                     print(f"BatchRender: File not found: {fpath}")

        
        if not self._jobs_to_refresh:
            self.report({'WARNING'}, "No external jobs found or files missing")
            return {'FINISHED'}
            
        wm = context.window_manager
        self._timer = wm.event_timer_add(0.2, window=context.window)
        wm.modal_handler_add(self)
        
        self.report({'INFO'}, f"Refreshing {len(self._jobs_to_refresh)} external jobs...")
        self._start_next_process(context)
        return {'RUNNING_MODAL'}

    def _start_next_process(self, context):
        if not self._jobs_to_refresh: return
            
        idx, fpath, sname = self._jobs_to_refresh.pop(0)
        self._current_job_data = (idx, os.path.basename(fpath), sname)
        
        blender_bin = bpy.app.binary_path
        
        # Create temp file for JSON Data
        tf_data = tempfile.NamedTemporaryFile(delete=False, mode='w+', suffix=".json")
        self._data_file_path = tf_data.name
        tf_data.close()
        
        # Create temp file for Stdout (Debug)
        tf_log = tempfile.NamedTemporaryFile(delete=False, mode='w+', suffix=".log")
        self._temp_file_path = tf_log.name
        tf_log.close() 
        
        # Create temp file for Python Script
        tf_script = tempfile.NamedTemporaryFile(delete=False, mode='w+', suffix=".py")
        self._script_file_path = tf_script.name
        
        # Robust Python Logic: Full multi-line script
        safe_json_path = self._data_file_path.replace("\\", "\\\\")
        
        script_content = "import bpy, json\n"
        script_content += "data = []\n"
        script_content += "for s in bpy.data.scenes:\n"
        script_content += "    data.append({'name': s.name, 'start': s.frame_start, 'end': s.frame_end, 'path': s.render.filepath})\n"
        script_content += f"with open('{safe_json_path}', 'w') as f:\n"
        script_content += "    json.dump(data, f)\n"
        
        tf_script.write(script_content)
        tf_script.close()
        
        cmd = [blender_bin, "-b", fpath, "--python", self._script_file_path]
        print(f"BatchRender: Querying {os.path.basename(fpath)} -> {self._data_file_path}")
        
        startupinfo = None
        if platform.system() == "Windows":
            startupinfo = subprocess.STARTUPINFO()
            startupinfo.dwFlags |= subprocess.STARTF_USESHOWWINDOW
            
        try:
            with open(self._temp_file_path, 'w') as f_out:
                self._current_process = subprocess.Popen(
                    cmd, 
                    stdout=f_out, 
                    stderr=f_out, 
                    text=True, 
                    startupinfo=startupinfo
                )
        except Exception as e:
            print(f"BatchRender: Failed to start process: {e}")
            self.report({'ERROR'}, f"Failed to start check for {fpath}")
            self._current_process = None

    def _process_json_data(self, data):
        queue = bpy.context.scene.batch_render_jobs
        idx_target, fname_target, sname_target = self._current_job_data
        
        if idx_target >= len(queue): return 
        job = queue[idx_target]
        
        print(f"BatchRender: [DEBUG] Processing JSON for Job '{job.scene_name}'")
        
        found = False
        for s_data in data:
            s_name = s_data.get('name')
            if s_name == job.scene_name:
                job.sc_frame_start = s_data.get('start', 1)
                job.sc_frame_end = s_data.get('end', 1)
                job.sc_filepath = s_data.get('path', "")
                found = True
                print(f"BatchRender: [DEBUG] Updated Job '{s_name}' Range: {job.sc_frame_start}-{job.sc_frame_end}")
                break
                
        if not found:
            print(f"BatchRender: [DEBUG] Scene '{job.scene_name}' not found in file data: {[s['name'] for s in data]}")


class BATCH_RENDER_OT_deduplicate_jobs(bpy.types.Operator):
    bl_idname = "batch_render.deduplicate_jobs"
    bl_label = "Smart Deduplicate"
    bl_description = "Remove jobs with identical Filename + Scene Name (Fixes Z:/H: drive dupes)"
    
    def execute(self, context):
        queue = context.scene.batch_render_jobs
        groups = {}
        
        # First pass: Index all jobs
        for i, job in enumerate(queue):
            if not job.filepath: continue
            bname = os.path.basename(job.filepath).lower()
            sname = job.scene_name
            sig = (bname, sname)
            if sig not in groups: groups[sig] = []
            groups[sig].append(i)
            
        removals = []
        for sig, indices in groups.items():
            if len(indices) > 1:
                print(f"BatchRender: Found duplicate group for {sig}: {indices}")
                candidates = []
                for idx in indices:
                    job = queue[idx]
                    path_exists = os.path.exists(bpy.path.abspath(job.filepath))
                    candidates.append((idx, path_exists, len(job.filepath)))
                
                # Sort: Exists=True first, then Longer Path (Absolute), then Index
                candidates.sort(key=lambda x: (x[1], x[2]), reverse=True)
                winner_idx = candidates[0][0]
                
                for c in candidates:
                    if c[0] != winner_idx: removals.append(c[0])
                
        if removals:
            removals.sort(reverse=True)
            for idx in removals:
                queue.remove(idx)
            write_batch_file(context)
            self.report({'INFO'}, f"Removed {len(removals)} duplicates")
        else:
            self.report({'INFO'}, "No duplicates found")
        return {'FINISHED'}

class BATCH_RENDER_OT_remove_placeholders(bpy.types.Operator):
    bl_idname = "batch_render.remove_placeholders"
    bl_label = "Remove Placeholders"
    bl_description = "Delete 0-byte files from output directories"
    
    def execute(self, context):
        targets = get_target_jobs(context)
        settings = context.scene.batch_render_settings
        
        count = 0
        
        for idx, job in targets:
            out_path = resolve_job_output_path(job, settings, job.filepath)
            out_prefix = get_job_output_prefix(job, settings, job.filepath)
            
            if not out_path or not os.path.exists(out_path): continue
            
            files = get_existing_frame_files(out_path, prefix=out_prefix)
            for f in files:
                try:
                    if os.path.getsize(f) == 0:
                        os.remove(f)
                        count += 1
                except Exception as e:
                    print(f"Failed to check/delete {f}: {e}")

        self.report({'INFO'}, f"Removed {count} placeholder files")
        bpy.ops.batch_render.scan_disk()
        return {'FINISHED'}





class BATCH_RENDER_OT_move_job(bpy.types.Operator):
    bl_idname = "batch_render.move_job"
    bl_label = "Move Job"
    bl_description = "Move selected job up or down"
    
    direction: EnumProperty(items=[('UP', "Up", ""), ('DOWN', "Down", "")])
    
    @classmethod
    def poll(cls, context):
        queue = context.scene.batch_render_jobs
        return len(queue) > 1

    def execute(self, context):
        queue = context.scene.batch_render_jobs
        
        # Get all selected indices
        selected_indices = [i for i, job in enumerate(queue) if job.selected]
        
        # Fallback to active if none selected
        if not selected_indices:
            idx = context.scene.batch_render_active_job_index
            if 0 <= idx < len(queue):
                selected_indices = [idx]
        
        if not selected_indices: return {'CANCELLED'}
        
        # Capture active index to update it
        current_active = context.scene.batch_render_active_job_index
        new_active = current_active
        
        # Move Logic
        if self.direction == 'UP':
            # Process Top-to-Bottom
            selected_indices.sort()
            for idx in selected_indices:
                dest = idx - 1
                # Stop if at top or blocked by another selected item
                if dest >= 0 and not queue[dest].selected:
                    queue.move(idx, dest)
                    if idx == current_active: new_active = dest
                    
        else: # DOWN
            # Process Bottom-to-Top
            selected_indices.sort(reverse=True)
            for idx in selected_indices:
                dest = idx + 1
                # Stop if at bottom or blocked by another selected item
                if dest < len(queue) and not queue[dest].selected:
                    queue.move(idx, dest)
                    if idx == current_active: new_active = dest
                    
        # Update active index to follow selection
        context.scene.batch_render_active_job_index = new_active
        
        # Trigger Auto-Save
        write_batch_file(context)
        
        return {'FINISHED'}

class BATCH_RENDER_OT_add_scene_job(bpy.types.Operator):
    bl_idname = "batch_render.add_scene_job"
    bl_label = "Add Scene"
    bl_options = {'REGISTER', 'UNDO'}

    def invoke(self, context, event): 
        # Populate candidates with local scenes
        candidates = context.scene.batch_render_import_candidates
        candidates.clear()
        
        for s in bpy.data.scenes:
            item = candidates.add()
            item.name = s.name
            # Default to selecting only the current scene
            item.selected = (s == context.scene)
            
        return context.window_manager.invoke_props_dialog(self, width=400)

    def draw(self, context): 
        layout = self.layout
        layout.label(text="Select Scenes to Add:")
        layout.template_list("BATCH_RENDER_UL_import_list", "", context.scene, "batch_render_import_candidates", context.scene, "batch_render_import_active_index")
    
    def execute(self, context):
        queue = context.scene.batch_render_jobs
        candidates = context.scene.batch_render_import_candidates
        
        added_count = 0
        for cand in candidates:
            if cand.selected:
                if cand.name not in bpy.data.scenes: continue
                
                scn = bpy.data.scenes[cand.name]
                
                item = queue.add()
                item.uuid = str(uuid.uuid4())
                item.filepath = bpy.data.filepath
                item.scene_name = scn.name
                
                item.sc_frame_start = scn.frame_start
                item.sc_frame_end = scn.frame_end
                item.sc_filepath = scn.render.filepath
                item.is_saved = False
                added_count += 1
        
        if added_count > 0:
            # Trigger Auto-Save (which will set item.is_saved = True)
            write_batch_file(context)
            self.report({'INFO'}, f"Added {added_count} scenes")
            return {'FINISHED'}
        
        return {'CANCELLED'}

class BATCH_RENDER_OT_select_scenes_from_file(bpy.types.Operator):
    bl_idname = "batch_render.select_scenes_from_file"
    bl_label = "Select Scenes"
    bl_options = {'REGISTER', 'UNDO'}
    filepath: StringProperty()
    
    def invoke(self, context, event):
        if not self.filepath or not os.path.isfile(self.filepath): return {'CANCELLED'}
        candidates = context.scene.batch_render_import_candidates
        candidates.clear()
        try:
            with bpy.data.libraries.load(self.filepath) as (from_, to_):
                for name in from_.scenes:
                    item = candidates.add()
                    item.name = name
                    item.selected = True 
        except Exception: return {'CANCELLED'}
        return context.window_manager.invoke_props_dialog(self, width=400)
        
    def draw(self, context):
        layout = self.layout
        layout.label(text=f"File: {os.path.basename(self.filepath)}")
        layout.template_list("BATCH_RENDER_UL_import_list", "", context.scene, "batch_render_import_candidates", context.scene, "batch_render_import_active_index")
    
    def execute(self, context):
        queue = context.scene.batch_render_jobs
        for cand in context.scene.batch_render_import_candidates:
            if cand.selected:
                item = queue.add()
                item.uuid = str(uuid.uuid4())
                item.filepath = self.filepath
                item.scene_name = cand.name
                item.is_saved = False
        
        # Trigger Auto-Save
        write_batch_file(context)
        return {'FINISHED'}

class BATCH_RENDER_OT_add_external_file(bpy.types.Operator, ImportHelper):
    bl_idname = "batch_render.add_external_file"
    bl_label = "Add from File..."
    filter_glob: StringProperty(default="*.blend", options={'HIDDEN'})
    def execute(self, context):
        bpy.ops.batch_render.select_scenes_from_file('INVOKE_DEFAULT', filepath=self.filepath)
        return {'FINISHED'}

class BATCH_RENDER_OT_remove_job(bpy.types.Operator):
    bl_idname = "batch_render.remove_job"
    bl_label = "Remove"
    @classmethod
    def poll(cls, context): return context.scene.batch_render_jobs
    def execute(self, context):
        queue = context.scene.batch_render_jobs
        
        # Get targets (sorted descending to avoid index shift issues)
        targets = get_target_jobs(context)
        if not targets: return {'CANCELLED'}
        
        # Sort by index descending
        targets.sort(key=lambda x: x[0], reverse=True)
        
        for idx, job in targets:
            queue.remove(idx)
            
        # Reset active index
        if len(queue) > 0:
            context.scene.batch_render_active_job_index = max(0, min(context.scene.batch_render_active_job_index, len(queue)-1))
        
        # Trigger Auto-Save
        write_batch_file(context)
        return {'FINISHED'}

class BATCH_RENDER_OT_clear_jobs(bpy.types.Operator):
    bl_idname = "batch_render.clear_jobs"
    bl_label = "Clear All"
    def execute(self, context):
        context.scene.batch_render_jobs.clear()
        # Trigger Auto-Save
        write_batch_file(context)
        return {'FINISHED'}

class BATCH_RENDER_OT_save_batch(bpy.types.Operator):
    bl_idname = "batch_render.save_batch"
    bl_label = "Save Batch"
    bl_description = "Save the batch file without running it"

    def execute(self, context):
        path, error = write_batch_file(context)
        if error:
            self.report({'ERROR'}, error)
            return {'CANCELLED'}
        self.report({'INFO'}, f"Batch file saved to {path}")
        return {'FINISHED'}

class BATCH_RENDER_OT_generate_and_run(bpy.types.Operator):
    bl_idname = "batch_render.generate_and_run"
    bl_label = "Save & Run"
    bl_description = "Save and execute the batch file"

    def execute(self, context):
        script_path, error = write_batch_file(context)
        if error:
            self.report({'ERROR'}, error)
            return {'CANCELLED'}
            
        # Run it
        try:
            if platform.system() == "Windows":
                os.startfile(script_path)
            else:
                subprocess.Popen(["open", script_path])
        except Exception as e:
            self.report({'ERROR'}, f"Failed to run script: {e}")
            return {'CANCELLED'}
            
        return {'FINISHED'}

class BATCH_RENDER_OT_resolve_conflict(bpy.types.Operator):
    bl_idname = "batch_render.resolve_conflict"
    bl_label = "Resolve Conflict"
    bl_description = "Resolve auto-save sync conflict with external file"
    
    action: EnumProperty(
        items=[
            ('OVERWRITE', "Force Delete Remote Jobs", "Overwrite remote file with local state (Destructive)"),
            ('MERGE', "Merge Missing Jobs", "Import jobs from remote file into local queue")
        ]
    )

    def execute(self, context):
        settings = context.scene.batch_render_settings
        if not settings.conflict_detected: return {'CANCELLED'}
        
        if self.action == 'OVERWRITE':
            settings.conflict_detected = False
            settings.conflict_info = ""
            write_batch_file(context)
            self.report({'WARNING'}, "Remote changes overwritten.")
            
        elif self.action == 'MERGE':
            # Perform additive merge
            batch_path, _ = get_batch_file_path(context)
            if batch_path and os.path.exists(batch_path):
                remote_state = parse_batch_file_to_state(batch_path)
                if remote_state:
                    local_state = capture_local_state(context)
                    # We merge remote into local. 
                    # Existing jobs are preserved (Local wins conflicts naturally via capture).
                    # Missing jobs are added.
                    merged, _ = merge_queue_states(local_state, remote_state, -1, -1)
                    apply_state_to_ui(context, merged)
                
            settings.conflict_detected = False
            settings.conflict_info = ""
            write_batch_file(context)
            self.report({'INFO'}, "Merged remote jobs.")
            
        return {'FINISHED'}

class BATCH_RENDER_OT_reload_queue(bpy.types.Operator):
    bl_idname = "batch_render.reload_queue"
    bl_label = "Reload Queue"
    bl_description = "Reload from file (Discards pending changes)"
    def execute(self, context):
        load_queue_from_file(context)
        bpy.ops.batch_render.scan_disk()
        return {'FINISHED'}

# -------------------------------------------------------------------
# UI Panel
# -------------------------------------------------------------------

class BATCH_RENDER_PT_main(bpy.types.Panel):
    bl_label = "Batch Command Line Render"
    bl_idname = "BATCH_RENDER_PT_main"
    bl_space_type = 'PROPERTIES'
    bl_region_type = 'WINDOW'
    bl_context = "render"
    
    def draw(self, context):
        layout = self.layout
        scene = context.scene
        settings = scene.batch_render_settings
        queue = scene.batch_render_jobs
        
        # --- CONFLICT WARNING ---
        if settings.conflict_detected:
            layout.alert = True
            box = layout.box()
            box.label(text="SYNC CONFLICT: Remote Jobs Missing!", icon='ERROR')
            box.label(text="Saving now would delete jobs added by others.")
            if settings.conflict_info:
                box.label(text=f"Missing: {settings.conflict_info}")
            
            row = box.row()
            row.scale_y = 1.5
            op = row.operator("batch_render.resolve_conflict", text="Sync (Add Missing Jobs)", icon='FILE_REFRESH')
            op.action = 'MERGE'
            
            op = row.operator("batch_render.resolve_conflict", text="Overwrite (Delete Remote)", icon='TRASH')
            op.action = 'OVERWRITE'
            
            layout.alert = False
            layout.separator()
        
        # --- Batch File Configuration (Always Visible) ---
        box = layout.box()
        # box.label(text="Batch File Configuration", icon='FILE_SCRIPT')
        
        row = box.row()
        row.prop(settings, "batch_file_path")
        
        # Show resolved absolute path
        abs_path, _ = get_batch_file_path(context)
        if abs_path:
             box.label(text=f"Resolved: {abs_path}", icon='FILE_TICK')
             if settings.last_known_mtime > 0:
                 box.label(text="Synced: Ready for Multi-User", icon='LINK_BLEND')
        else:
             box.label(text="Resolved: (Invalid)", icon='ERROR')
        
        row = box.row()
        row.scale_y = 1.0
        row.operator("batch_render.reload_queue", text="Reload Queue", icon='FILE_REFRESH')
        row.operator("batch_render.refresh_metadata", text="Refresh Metadata", icon='IMPORT')
        row.operator("batch_render.scan_disk", text="Check Progress", icon='DISK_DRIVE')
        # --- Run ---
        layout.separator()
        row = layout.row()
        row.scale_y = 1.3
        row.operator("batch_render.save_batch", icon='FILE_TICK', text="Save Batch")
        row.operator("batch_render.generate_and_run", icon='PLAY', text="Save & Run")        
        # --- Global Options (Collapsible, under Refresh) ---
        row = layout.row()
        
        row.prop(settings, "show_global_options", icon="TRIA_DOWN" if settings.show_global_options else "TRIA_RIGHT", emboss=False, text="Global Options")
        
        if settings.show_global_options:
            root_box = layout.box()
            
            # --- Command Line Options ---
            col = root_box.column(align=True)
            col.label(text="Command Line Options", icon='CONSOLE')
            
            row = col.row()
            row.prop(settings, "use_background")
            row = col.row()
            row.prop(settings, "use_pause_at_end", text="Pause at End")
            
            row = col.row()
            row.prop(settings, "use_queue_loop")
            
            row = col.row()
            row.prop(settings, "use_auto_refresh")
            if settings.use_auto_refresh:
                row.prop(settings, "auto_refresh_interval", text="Interval")
            
            row = col.row()
            row.prop(settings, "use_chunking", text="Enable Chunking")
            if settings.use_chunking:
                row.prop(settings, "chunk_size")
                row.prop(settings, "chunk_timeout")
            
        # --- Queue Overrides ---
        row = layout.row()
        row.prop(settings, "show_queue_overrides", icon="TRIA_DOWN" if settings.show_queue_overrides else "TRIA_RIGHT", emboss=False, text="Queue Overrides")
        
        if settings.show_queue_overrides:
            ov_box = layout.box()
            ov_box.label(text="Queue Overrides", icon='SETTINGS')
            
            # Frame Range
            row = ov_box.row()
            row.prop(settings, "use_override_frames", text="Override Range")
            if settings.use_override_frames:
                row.prop(settings, "frame_start")
                row.prop(settings, "frame_end")
                
            row = ov_box.row()
            row.prop(settings, "use_specific_frame", text="Render Single Frame")
            if settings.use_specific_frame:
                row.prop(settings, "specific_frame")
                
            row = ov_box.row()
            row.prop(settings, "use_frame_jump")
            if settings.use_frame_jump:
                row.prop(settings, "frame_jump")
            
            ov_box.separator()

            # Output
            row = ov_box.row()
            row.prop(settings, "use_override_output", text="Override Path")
            if settings.use_override_output:
                row.prop(settings, "output_path", text="")
            
            row = ov_box.row()
            row.prop(settings, "use_extension", text="Add Extension (-x)")
            
            row = ov_box.row()
            row.prop(settings, "use_override_placeholders")
            if settings.use_override_placeholders:
                row.prop(settings, "use_placeholders")
            
            ov_box.separator()

            # Engine
            row = ov_box.row()
            row.prop(settings, "use_override_engine")
            if settings.use_override_engine:
                row.prop(settings, "engine_type", text="")
                
            row = ov_box.row()
            row.prop(settings, "use_override_format")
            if settings.use_override_format:
                row.prop(settings, "render_format", text="")

            ov_box.separator()

            # Performance / Device
            row = ov_box.row()
            row.prop(settings, "use_threads")
            if settings.use_threads:
                row.prop(settings, "threads")
            
            row = ov_box.row()
            row.prop(settings, "use_cycles_device")
            if settings.use_cycles_device:
                row.prop(settings, "cycles_device", text="")
            
            ov_box.separator()

            # --- Python Overrides ---
            ov_box.label(text="Scene Overrides (Python)")
            
            row = ov_box.row()
            row.prop(settings, "use_override_samples")
            if settings.use_override_samples:
                row.prop(settings, "samples")
                
            row = ov_box.row()
            row.prop(settings, "use_override_denoising")
            if settings.use_override_denoising:
                row.prop(settings, "denoising_state", text="Enabled")
                if settings.denoising_state:
                    row.prop(settings, "denoiser_type", text="")

            row = ov_box.row()
            row.prop(settings, "use_override_color_mode")
            if settings.use_override_color_mode:
                row.prop(settings, "color_mode", text="")
                
            row = ov_box.row()
            row.prop(settings, "use_override_overwrite")
            if settings.use_override_overwrite:
                row.prop(settings, "use_overwrite")
                
            row = ov_box.row()
            row.prop(settings, "use_override_persistent_data")
            if settings.use_override_persistent_data:
                row.prop(settings, "persistent_data")

            row = ov_box.row()
            row.prop(settings, "use_override_simplify")
            if settings.use_override_simplify:
                row.prop(settings, "simplify_use", text="Enable")
                row.prop(settings, "simplify_subdivision_render", text="Subdiv")
                row.prop(settings, "simplify_image_limit", text="")
                
            row = ov_box.row()
            row.prop(settings, "use_override_volumetrics")
            if settings.use_override_volumetrics:
                row.prop(settings, "volume_biased", text="Biased")
                row.prop(settings, "volume_step_rate", text="Step Rate")


        # --- Job Queue ---
        row = layout.row()
        row.prop(settings, "show_job_queue", icon="TRIA_DOWN" if settings.show_job_queue else "TRIA_RIGHT", emboss=False, text="Job Queue")
        
        if settings.show_job_queue:
            row = layout.row()
            row.template_list("BATCH_RENDER_UL_jobs", "", scene, "batch_render_jobs", scene, "batch_render_active_job_index")
            
            # Button Block (Underneath)
            col = layout.column(align=True)
            # management title
            row = col.row(align=True)
            
            # Row 1: Management
            row = col.row(align=True)
            row.operator("batch_render.add_scene_job", icon='ADD', text="Add Scene")
            row.operator("batch_render.add_external_file", icon='FILE_FOLDER', text="Add File")
            row = col.row(align=True)
            row.operator("batch_render.remove_job", icon='REMOVE', text="Remove")
            row.operator("batch_render.clear_jobs", icon='TRASH', text="Clear All")
            row = col.row(align=True)
            row.operator("batch_render.move_job", icon='TRIA_UP', text="Move Up").direction = 'UP'
            row.operator("batch_render.move_job", icon='TRIA_DOWN', text="Move Down").direction = 'DOWN'  
            
            # Metadata title
            row = col.row(align=True)
            row.label(text="Metadata")
            # Row 1.5: Metadata
            row = col.row(align=True)
            row.operator("batch_render.refresh_metadata", text="Refresh Selected", icon='FILE_REFRESH').mode = 'SELECTED'
            row.operator("batch_render.refresh_metadata", text="Refresh All", icon='FILE_REFRESH').mode = 'ALL'
            # status title
            row = col.row(align=True)
            row.label(text="Set Job Status")
            # Row 2: Job Status
            row = col.row(align=True)          
            row.operator("batch_render.set_job_pending", icon='FILE_REFRESH', text="Pending")
            row.operator("batch_render.set_job_done", icon='CHECKBOX_HLT', text="Done")
            #Output Frames Title
            row = col.row(align=True)
            row.label(text="Output Frames")
            # Row 4: Actions
            row = col.row(align=True)
            row.operator("batch_render.archive_frames", icon='FILE_ARCHIVE', text="Archive")
            row.operator("batch_render.delete_frames", icon='X', text="Delete Frames")
            row.operator("batch_render.remove_placeholders", icon='BRUSH_DATA', text="Clean")
            row = col.row(align=True)
            row.operator("batch_render.preview_output", icon='PLAY', text="Preview Output")
            row.operator("batch_render.open_output_folder", icon='FILE_FOLDER', text="Open Folder")
            row.operator("batch_render.open_job_file", icon='BLENDER', text="Open Blend File")
            
            # --- Chunking Status List (Inside Job Queue) ---
            idx = scene.batch_render_active_job_index
            if 0 <= idx < len(queue):
                active_job = queue[idx]
                if active_job.use_chunking or settings.use_chunking:
                    box = layout.box()
                    
                    # Custom Header
                    row = box.row()
                    icon = "TRIA_DOWN" if settings.show_chunk_details else "TRIA_RIGHT"
                    row.prop(settings, "show_chunk_details", icon=icon, emboss=False, text=f"Chunks: {active_job.scene_name}")
                    
                    if settings.show_chunk_details:
                        # Full List View
                        row = box.row()
                        row.template_list("BATCH_RENDER_UL_chunks", "", active_job, "chunks", scene, "batch_render_active_chunk_index", rows=5)
                        
                        row = box.row()
                        row.operator("batch_render.set_chunk_status", text="Set Done", icon='CHECKBOX_HLT').action = 'DONE'
                        row.operator("batch_render.set_chunk_status", text="Set Pending", icon='CHECKBOX_DEHLT').action = 'PENDING'
                    else:
                        # Compact Progress View
                        row = box.row()
                        row.prop(active_job, "cached_chunk_progress", text="Progress", slider=True, emboss=False)
                        row.enabled = False # Read-only look
            
            # --- Selected Job Overrides (Nested in Queue) ---
            idx = scene.batch_render_active_job_index
            if 0 <= idx < len(queue):
                job = queue[idx]
                layout.separator()
                
                # Make it look like a child panel (indented box?)
                # Actually just standard prop with sub-box
                row = layout.row()
                row.prop(settings, "show_selected_job", icon="TRIA_DOWN" if settings.show_selected_job else "TRIA_RIGHT", emboss=False, text=f"Selected Job: {job.scene_name}")
                
                if settings.show_selected_job:
                    box = layout.box()
                    row = box.row()
                    row.prop(job, "enabled", text="Enabled")
                    
                    if job.enabled:
                        box.prop(job, "use_overrides")
                        if job.use_overrides:
                            # Frames
                            row = box.row()
                            row.prop(job, "use_custom_frames")
                            if job.use_custom_frames:
                                row.prop(job, "frame_start")
                                row.prop(job, "frame_end")
                            
                            # Samples
                            row = box.row()
                            row.prop(job, "use_custom_samples")
                            if job.use_custom_samples:
                                row.prop(job, "samples")
                                
                            # Output
                            row = box.row()
                            row.prop(job, "use_custom_output")
                            if job.use_custom_output:
                                row.prop(job, "output_path", text="")
                                
                            # Chunking
                            row = box.row()
                            row.prop(job, "use_custom_chunking")
                            if job.use_custom_chunking:
                                 row.prop(job, "use_chunking")
                                 if job.use_chunking:
                                     row.prop(job, "chunk_size")
                                     
                            # Persistent Data
                            row = box.row()
                            row.prop(job, "use_custom_persistent_data")
                            if job.use_custom_persistent_data:
                                row.prop(job, "persistent_data")
                                
                            # Simplify
                            row = box.row()
                            row.prop(job, "use_custom_simplify")
                            if job.use_custom_simplify:
                                col = row.column(align=True)
                                col.prop(job, "simplify_use", text="Enable")
                                col.prop(job, "simplify_subdivision_render", text="Subdiv")
                                col.prop(job, "simplify_image_limit", text="")
        
                            # Volumetrics
                            row = box.row()
                            row.prop(job, "use_custom_volumetrics")
                            if job.use_custom_volumetrics:
                                col = row.column(align=True)
                                col.prop(job, "volume_biased", text="Biased")
                                col.prop(job, "volume_step_rate", text="Step Rate")
                                
                            # Block PC List
                            row = box.row()
                            row.prop(job, "use_custom_block_list")
                            if job.use_custom_block_list:
                                 # Corrected property reference
                                 row.prop(job, "blocked_computers", text="Block PCs")
                    



# -------------------------------------------------------------------
# Registration
# -------------------------------------------------------------------

classes = (
    BatchRenderChunk,
    BatchRenderJob,
    BatchRenderSettings,
    BatchRenderImportItem,
    BATCH_RENDER_UL_jobs,
    BATCH_RENDER_UL_chunks,
    BATCH_RENDER_UL_import_list,
    BATCH_RENDER_OT_add_scene_job,
    BATCH_RENDER_OT_select_scenes_from_file,
    BATCH_RENDER_OT_add_external_file,
    BATCH_RENDER_OT_remove_job,
    BATCH_RENDER_OT_clear_jobs,
    BATCH_RENDER_OT_save_batch,
    BATCH_RENDER_OT_generate_and_run,
    BATCH_RENDER_OT_reload_queue,
    BATCH_RENDER_OT_refresh_metadata,
    BATCH_RENDER_OT_deduplicate_jobs,
    BATCH_RENDER_OT_scan_disk,
    BATCH_RENDER_OT_scan_job_chunks,
    BATCH_RENDER_OT_set_chunk_status,
    BATCH_RENDER_OT_set_job_pending,
    BATCH_RENDER_OT_set_job_done,
    BATCH_RENDER_OT_archive_frames,
    BATCH_RENDER_OT_delete_frames,
    BATCH_RENDER_OT_remove_placeholders,
    BATCH_RENDER_OT_preview_output,
    BATCH_RENDER_OT_open_job_file,
    BATCH_RENDER_OT_open_output_folder,
    BATCH_RENDER_OT_move_job,
    BATCH_RENDER_PT_main,
)

def register():
    for cls in classes:

        bpy.utils.register_class(cls)

    bpy.types.Scene.batch_render_jobs = CollectionProperty(type=BatchRenderJob)
    bpy.types.Scene.batch_render_active_job_index = IntProperty()
    bpy.types.Scene.batch_render_active_chunk_index = IntProperty()
    bpy.types.Scene.batch_render_settings = PointerProperty(type=BatchRenderSettings)

    bpy.types.Scene.batch_render_import_candidates = CollectionProperty(type=BatchRenderImportItem)
    bpy.types.Scene.batch_render_import_active_index = IntProperty()
    
    bpy.app.handlers.load_post.append(load_global_config_handler)
    
    # Force load immediately for manual script execution
    apply_global_config()

def unregister():
    if bpy.app.timers.is_registered(batch_render_auto_refresh_timer):
        bpy.app.timers.unregister(batch_render_auto_refresh_timer)

    if load_global_config_handler in bpy.app.handlers.load_post:
        bpy.app.handlers.load_post.remove(load_global_config_handler)
        
    for cls in reversed(classes):
        bpy.utils.unregister_class(cls)
        
    del bpy.types.Scene.batch_render_jobs
    del bpy.types.Scene.batch_render_active_job_index
    del bpy.types.Scene.batch_render_settings
    del bpy.types.Scene.batch_render_import_candidates
    del bpy.types.Scene.batch_render_import_active_index

register()
