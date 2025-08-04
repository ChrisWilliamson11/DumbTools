import json
import subprocess
import tempfile
import os
import time
import bpy
import shutil

# Initialize variables - get deadline path from preferences or use default
def get_deadline_path():
    try:
        prefs = bpy.context.preferences.addons["DumbTools"].preferences
        return getattr(prefs, 'deadline_path', "\\DeadlineRepository10\\bin\\Windows\\64bit\\deadlinecommand.exe")
    except:
        # Fallback to hardcoded path if preferences aren't available
        return "\\\\wlgsrvrnd\\DeadlineRepository10\\bin\\Windows\\64bit\\deadlinecommand.exe"

def save_pools_to_cache(pools):
    """Save pools to JSON cache file"""
    try:
        with open(POOLS_CACHE_PATH, 'w') as f:
            json.dump({"pools": pools, "timestamp": time.time()}, f)
        print(f"DEBUG: Saved pools to cache: {pools}")
    except Exception as e:
        print(f"DEBUG: Failed to save pools cache: {e}")

def load_pools_from_cache():
    """Load pools from JSON cache file"""
    try:
        if os.path.exists(POOLS_CACHE_PATH):
            with open(POOLS_CACHE_PATH, 'r') as f:
                data = json.load(f)
                pools = data.get("pools", ["blendergpu"])
                print(f"DEBUG: Loaded pools from cache: {pools}")
                return pools
        else:
            print("DEBUG: No pools cache file found")
            return None
    except Exception as e:
        print(f"DEBUG: Failed to load pools cache: {e}")
        return None

def create_clean_deadline_environment():
    """Create a clean environment for Deadline commands to avoid Python conflicts"""
    env = os.environ.copy()

    # Remove all Python-related environment variables that might conflict
    python_vars_to_remove = [
        'PYTHONPATH', 'PYTHONHOME', 'PYTHON', 'PYTHONSTARTUP', 'PYTHONIOENCODING',
        'PYTHONEXECUTABLE', 'PYTHONDONTWRITEBYTECODE', 'PYTHONUNBUFFERED',
        'PYTHONOPTIMIZE', 'PYTHONDEBUG', 'PYTHONVERBOSE', 'PYTHONCASEOK',
        'PYTHONUSERBASE', 'PYTHONUSERSITE', 'PYTHONHASHSEED', 'PYTHONMALLOCSTATS',
        'PYTHONASYNCIODEBUG', 'PYTHONTRACEMALLOC', 'PYTHONFAULTHANDLER',
        'PYTHONLEGACYWINDOWSFSENCODING', 'PYTHONLEGACYWINDOWSSTDIO',
        'PYTHONCOERCECLOCALE', 'PYTHONDEVMODE', 'PYTHONWARNINGS'
    ]

    for var in python_vars_to_remove:
        env.pop(var, None)

    # Also remove any Blender-specific Python paths that might interfere
    blender_vars_to_remove = [
        'BLENDER_SYSTEM_PYTHON', 'BLENDER_USER_SCRIPTS', 'BLENDER_SYSTEM_SCRIPTS'
    ]

    for var in blender_vars_to_remove:
        env.pop(var, None)

    return env

def get_deadline_pools_from_server():
    """Get available pools directly from Deadline server"""
    try:
        deadline_cmd = get_deadline_path()
        print(f"DEBUG: Using Deadline command: {deadline_cmd}")

        # Create clean environment
        env = create_clean_deadline_environment()

        # Try multiple approaches to work around Python environment issues
        approaches = [
            # Approach 1: Use clean environment with shell=False
            {
                'cmd': [deadline_cmd, "-GetPoolNames"],
                'shell': False,
                'env': env,
                'description': 'Clean environment, no shell'
            },
            # Approach 2: Use clean environment with shell=True
            {
                'cmd': f'"{deadline_cmd}" -GetPoolNames',
                'shell': True,
                'env': env,
                'description': 'Clean environment, with shell'
            },
            # Approach 3: Use minimal environment (only keep essential Windows vars)
            {
                'cmd': [deadline_cmd, "-GetPoolNames"],
                'shell': False,
                'env': {
                    'PATH': env.get('PATH', ''),
                    'SYSTEMROOT': env.get('SYSTEMROOT', ''),
                    'WINDIR': env.get('WINDIR', ''),
                    'TEMP': env.get('TEMP', ''),
                    'TMP': env.get('TMP', ''),
                    'USERNAME': env.get('USERNAME', ''),
                    'USERPROFILE': env.get('USERPROFILE', ''),
                    'COMPUTERNAME': env.get('COMPUTERNAME', ''),
                },
                'description': 'Minimal environment'
            }
        ]

        for i, approach in enumerate(approaches, 1):
            print(f"DEBUG: Trying approach {i}: {approach['description']}")

            try:
                result = subprocess.run(
                    approach['cmd'],
                    shell=approach['shell'],
                    stdout=subprocess.PIPE,
                    stderr=subprocess.PIPE,
                    text=True,
                    env=approach['env'],
                    timeout=30  # Add timeout to prevent hanging
                )

                print(f"DEBUG: Approach {i} - Return code: {result.returncode}")
                if result.stderr:
                    print(f"DEBUG: Approach {i} - Stderr: {result.stderr}")

                if result.returncode == 0:
                    pools = [pool.strip() for pool in result.stdout.strip().split('\n') if pool.strip()]
                    print(f"DEBUG: Approach {i} succeeded - Found pools: {pools}")
                    return pools
                else:
                    print(f"DEBUG: Approach {i} failed with return code {result.returncode}")

            except subprocess.TimeoutExpired:
                print(f"DEBUG: Approach {i} timed out")
            except Exception as e:
                print(f"DEBUG: Approach {i} exception: {e}")

        # If all approaches failed, return fallback
        print("DEBUG: All approaches failed, using fallback pools")
        return ["blendergpu"]  # Fallback to your current hardcoded pool

    except Exception as e:
        print(f"DEBUG: Error getting pools from server: {e}")
        return ["blendergpu"]  # Fallback to your current hardcoded pool

def get_deadline_pools():
    """Get available pools - first try cache, then server"""
    # Try to load from cache first
    cached_pools = load_pools_from_cache()
    if cached_pools:
        return cached_pools

    # If no cache, get from server and save to cache
    print("DEBUG: No cached pools found, fetching from server...")
    pools = get_deadline_pools_from_server()
    save_pools_to_cache(pools)
    return pools

# Cache for pools - only query once when needed
_cached_pools = None

def get_cached_deadline_pools():
    """Get pools with one-time caching"""
    global _cached_pools

    if _cached_pools is None:
        print("DEBUG: Querying pools for the first time...")
        _cached_pools = get_deadline_pools()

    return _cached_pools

# Remove the manual copy function - we'll use Deadline's auxiliary file system instead

def create_sample_subset_script():
    """Create a Python script that sets sample subset parameters from command line arguments"""
    script_content = '''import bpy
import sys

def setup_sample_subset():
    """Setup sample subset parameters from command line arguments"""
    print("=== SAMPLE SUBSET SETUP SCRIPT STARTED ===")
    # Find arguments after '--'
    try:
        dash_index = sys.argv.index('--')
        args = sys.argv[dash_index + 1:]
    except ValueError:
        print("ERROR: No arguments found after '--'")
        return False

    if len(args) < 6:
        print("ERROR: Expected 6 arguments: offset, length, total_samples, output_path, disable_denoising, disable_adaptive")
        print(f"Got {len(args)} arguments: {args}")
        return False

    try:
        offset = int(args[0])
        length = int(args[1])
        total_samples = int(args[2])
        output_path = args[3]
        disable_denoising = args[4].lower() == 'true'
        disable_adaptive = args[5].lower() == 'true'

        print(f"Setting up sample subset: offset={offset}, length={length}, total_samples={total_samples}")
        print(f"Output path: {output_path}")
        print(f"Disable denoising: {disable_denoising}, Disable adaptive: {disable_adaptive}")

        scene = bpy.context.scene

        # Log current state before changes
        print(f"BEFORE: use_sample_subset={scene.cycles.use_sample_subset}, samples={scene.cycles.samples}")
        print(f"BEFORE: sample_offset={scene.cycles.sample_offset}, sample_subset_length={scene.cycles.sample_subset_length}")
        print(f"Render engine: {scene.render.engine}")

        # Set sample subset parameters
        scene.cycles.use_sample_subset = True
        scene.cycles.sample_offset = offset
        scene.cycles.sample_subset_length = length
        # DO NOT set scene.cycles.samples - let Blender use the subset length for actual rendering

        # Log state after changes to verify they were applied
        print(f"AFTER: use_sample_subset={scene.cycles.use_sample_subset}, samples={scene.cycles.samples}")
        print(f"AFTER: sample_offset={scene.cycles.sample_offset}, sample_subset_length={scene.cycles.sample_subset_length}")

        # Verify the render engine is Cycles
        if scene.render.engine != 'CYCLES':
            print("WARNING: Render engine is not CYCLES - sample subset feature only works with Cycles!")
            return False

        # Set output path
        scene.render.filepath = output_path

        # Force OpenEXR format for sample subset rendering (must be EXR for merging)
        print(f"Changing output format from {scene.render.image_settings.file_format} to OPEN_EXR")
        scene.render.image_settings.file_format = 'OPEN_EXR'

        # Also set EXR-specific settings for better compatibility
        scene.render.image_settings.exr_codec = 'ZIP'  # Use ZIP compression
        scene.render.image_settings.color_depth = '32'  # 32-bit float

        # Disable denoising and adaptive sampling if requested
        if disable_denoising:
            scene.cycles.use_denoising = False

        if disable_adaptive:
            scene.cycles.use_adaptive_sampling = False

        print("Sample subset setup complete")
        return True

    except (ValueError, IndexError) as e:
        print(f"ERROR: Failed to parse arguments: {e}")
        return False

# Run setup when script is executed
if __name__ == "__main__":
    print("=== SAMPLE SUBSET SETUP SCRIPT STARTING ===")
    if not setup_sample_subset():
        print("=== SAMPLE SUBSET SETUP FAILED ===")
        sys.exit(1)
    else:
        print("=== SAMPLE SUBSET SETUP COMPLETED SUCCESSFULLY ===")

# Also run setup immediately when imported (in case Deadline runs it differently)
print("Sample subset setup script loaded - running setup...")
setup_sample_subset()
'''

    # Write the script to a temporary file
    script_filename = "sample_subset_setup.py"
    script_path = os.path.join(temp_dir, script_filename)

    with open(script_path, 'w') as f:
        f.write(script_content)

    print(f"DEBUG: Created sample subset setup script: {script_path}")
    return script_path

def submit_split_frame_jobs(scene, filename, context):
    """Submit multiple jobs for split frame rendering using sample subsets"""
    job_count = context.window_manager.split_frame_jobs
    current_frame = context.scene.frame_current

    # Get total samples from the scene
    total_samples = scene.cycles.samples
    if total_samples <= 0:
        total_samples = 128  # Default fallback

    # Calculate samples per job
    samples_per_job = total_samples // job_count
    remaining_samples = total_samples % job_count

    print(f"DEBUG: Split frame rendering - Total samples: {total_samples}, Jobs: {job_count}, Samples per job: {samples_per_job}")

    # Validate sample distribution and warn user if problematic
    if samples_per_job < 4:
        print(f"WARNING: Very low samples per job ({samples_per_job}). This may result in poor noise distribution.")
        print(f"RECOMMENDATION: Reduce job count to {max(2, total_samples // 8)} or fewer for better results.")
    elif samples_per_job < 8:
        print(f"WARNING: Low samples per job ({samples_per_job}). Consider reducing job count for better noise distribution.")
        print(f"RECOMMENDATION: Try {max(2, total_samples // 16)} jobs for optimal balance.")
    elif job_count > total_samples:
        print(f"ERROR: More jobs ({job_count}) than total samples ({total_samples}). This is not possible.")
        print(f"MAXIMUM: You can split into at most {total_samples} jobs (1 sample per job).")
        return []

    # Store original scene settings to restore later
    original_use_sample_subset = scene.cycles.use_sample_subset
    original_sample_offset = scene.cycles.sample_offset
    original_sample_subset_length = scene.cycles.sample_subset_length
    original_use_denoising = scene.cycles.use_denoising
    original_use_adaptive_sampling = scene.cycles.use_adaptive_sampling
    original_file_format = scene.render.image_settings.file_format
    original_filepath = scene.render.filepath

    # Get original output path
    if original_filepath.startswith("//"):
        original_filepath = bpy.path.abspath(original_filepath)

    subset_job_ids = []

    try:
        # Submit jobs for each sample subset
        for job_index in range(job_count):
            # Calculate offset and length for this job
            offset = job_index * samples_per_job
            length = samples_per_job

            # Add remaining samples to the last job
            if job_index == job_count - 1:
                length += remaining_samples

            # Create subset output filename
            path_without_ext, extension = os.path.splitext(original_filepath)
            subset_filepath = f"{path_without_ext}_subset_{job_index + 1:02d}_of_{job_count:02d}.exr"

            print(f"DEBUG: Subset job {job_index + 1}: offset={offset}, length={length}, output={subset_filepath}")

            # Modify scene settings for this subset
            scene.cycles.use_sample_subset = True
            scene.cycles.sample_offset = offset
            scene.cycles.sample_subset_length = length
            scene.cycles.use_denoising = False  # Disable denoising for subset rendering
            scene.cycles.use_adaptive_sampling = False  # Disable adaptive sampling
            scene.render.image_settings.file_format = 'OPEN_EXR'  # Force EXR format
            scene.render.filepath = subset_filepath

            # Create temporary scene file with subset settings
            temp_scene_path = create_temp_scene_file(job_index, job_count)

            # Create job info for this subset
            subset_filename = f"{filename}_subset_{job_index + 1:02d}_of_{job_count:02d}"
            write_split_frame_job_info(scene, subset_filename, current_frame, subset_filepath)
            write_split_frame_plugin_info_with_temp_scene(scene.name, temp_scene_path, subset_filepath)

            # Submit the subset job
            cmd_list = [get_deadline_path(), "-SubmitJob", JOB_INFO_PATH, PLUGIN_INFO_PATH]

            # Add the temporary scene file as auxiliary file
            cmd_list.append(temp_scene_path)

            # Execute submission
            env = os.environ.copy()
            python_vars_to_remove = ['PYTHONPATH', 'PYTHONHOME', 'PYTHON', 'PYTHONSTARTUP', 'PYTHONIOENCODING']
            for var in python_vars_to_remove:
                env.pop(var, None)

            cmd = " ".join(f'"{arg}"' for arg in cmd_list)
            result = subprocess.run(
                cmd,
                shell=True,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                env=env
            )

            if result.returncode == 0:
                # Extract job ID from output
                job_id = None
                for line in result.stdout.split('\n'):
                    if "JobID=" in line:
                        job_id = line.split("JobID=")[1].strip()
                        break

                if job_id:
                    subset_job_ids.append(job_id)
                    print(f"DEBUG: Subset job {job_index + 1} submitted with ID: {job_id}")
                else:
                    print(f"WARNING: Failed to get job ID for subset job {job_index + 1}")
            else:
                print(f"ERROR: Failed to submit subset job {job_index + 1}")
                print(f"STDERR: {result.stderr}")

    finally:
        # Restore original scene settings
        scene.cycles.use_sample_subset = original_use_sample_subset
        scene.cycles.sample_offset = original_sample_offset
        scene.cycles.sample_subset_length = original_sample_subset_length
        scene.cycles.use_denoising = original_use_denoising
        scene.cycles.use_adaptive_sampling = original_use_adaptive_sampling
        scene.render.image_settings.file_format = original_file_format
        scene.render.filepath = original_filepath
        print("DEBUG: Restored original scene settings")

    return subset_job_ids

def create_temp_scene_file(job_index, job_count):
    """Create a temporary scene file with current settings for this subset job"""
    # Get the original scene file path
    original_scene_path = bpy.data.filepath
    if not original_scene_path:
        raise ValueError("Scene must be saved before submitting split frame jobs")

    # Create temporary file path
    scene_dir = os.path.dirname(original_scene_path)
    scene_name = os.path.splitext(os.path.basename(original_scene_path))[0]
    temp_scene_path = os.path.join(temp_dir, f"{scene_name}_subset_{job_index + 1:02d}_of_{job_count:02d}.blend")

    # Save the current scene with subset settings to the temporary file
    bpy.ops.wm.save_as_mainfile(filepath=temp_scene_path, copy=True)

    print(f"DEBUG: Created temporary scene file: {temp_scene_path}")
    return temp_scene_path

def write_split_frame_plugin_info_with_temp_scene(scene_name, temp_scene_path, output_path):
    """Write plugin info for split frame subset jobs using temporary scene file"""
    with open(PLUGIN_INFO_PATH, "w") as f:
        # Use the temporary scene file with subset settings already applied
        f.write(f"SceneFile={os.path.normpath(temp_scene_path)}\n")
        f.write(f"Scene={scene_name}\n")
        f.write(f"OutputFile={output_path}\n")
        f.write("Threads=0\n")

        # Disable progress tracking to avoid issues with sample subset rendering
        f.write("EnableProgressReports=false\n")
        f.write("StrictErrorChecking=false\n")

def write_split_frame_job_info(scene, filename, frame_number, output_path):
    """Write job info for split frame subset jobs - use same format as normal jobs"""
    with open(JOB_INFO_PATH, "w") as f:
        f.write("Plugin=Blender\n")
        f.write(f"Name={filename}\n")
        f.write(f"Frames={frame_number}-{frame_number}\n")  # Use range format like normal jobs
        f.write(f"ChunkSize=1\n")  # Single frame
        f.write(f"Priority={bpy.context.window_manager.job_priority}\n")

        # Use selected pool from dropdown
        selected_pool = bpy.context.window_manager.deadline_pool
        f.write(f"Pool={selected_pool}\n")

        # Add suspended state if selected
        if bpy.context.window_manager.submit_suspended:
            f.write("InitialStatus=Suspended\n")

        # Add output directory and filename (critical for Deadline plugin)
        output_directory = os.path.dirname(output_path)

        # Create the output directory if it doesn't exist
        if not os.path.exists(output_directory):
            os.makedirs(output_directory)
            print(f"DEBUG: Created output directory: {output_directory}")

        f.write(f"OutputDirectory0={output_directory}\n")
        f.write(f"OutputFilename0={output_path}\n")

def write_split_frame_plugin_info(scene_name, setup_script_path, offset, length, total_samples, output_path):
    """Write plugin info for split frame subset jobs"""
    with open(PLUGIN_INFO_PATH, "w") as f:
        # Use the original scene file
        scene_filepath = bpy.data.filepath
        if scene_filepath.startswith("//"):
            scene_filepath = bpy.path.abspath(scene_filepath)

        file_path = os.path.normpath(scene_filepath)
        f.write(f"SceneFile={file_path}\n")
        f.write(f"Scene={scene_name}\n")
        f.write(f"OutputFile={output_path}\n")
        # Don't specify OutputFormat here - let the setup script handle it
        f.write("Threads=0\n")

        # Disable progress tracking to avoid division by zero in sample subset rendering
        f.write("EnableProgressReports=false\n")
        f.write("StrictErrorChecking=false\n")

        # Add the setup script and arguments - use just the filename since it's an auxiliary file
        setup_script_filename = os.path.basename(setup_script_path)
        f.write(f"Arguments=-P {setup_script_filename} -- {offset} {length} {total_samples} {output_path} true true\n")



def create_merge_only_script(scene, filename, job_count, subset_job_ids):
    """Create a Python script that only merges images without any rendering"""
    current_frame = bpy.context.scene.frame_current

    # Get the base output path
    render_filepath = scene.render.filepath
    if render_filepath.startswith("//"):
        render_filepath = bpy.path.abspath(render_filepath)

    # Create the merge script content that exits before any rendering
    script_content = f'''import bpy
import os
import sys

# Immediately disable rendering to prevent any render operations
print("Merge script starting - disabling all render operations...")

# Exit render mode immediately
try:
    bpy.ops.render.render('INVOKE_DEFAULT', write_still=False)
except:
    pass

# Merge sample subset images
def merge_subset_images():
    print("Starting sample subset merge...")

    # Define input and output paths
    base_path = r"{os.path.dirname(render_filepath)}"
    output_filename = r"{os.path.basename(render_filepath)}"

    # Build list of subset files
    subset_files = []
'''

    # Add subset file paths to the script
    for job_index in range(job_count):
        path_without_ext, extension = os.path.splitext(render_filepath)
        subset_filepath = f"{path_without_ext}_subset_{job_index + 1:02d}_of_{job_count:02d}.exr"
        script_content += f'    subset_files.append(r"{subset_filepath}")\n'

    script_content += f'''
    # Verify all subset files exist
    missing_files = []
    for subset_file in subset_files:
        if not os.path.exists(subset_file):
            missing_files.append(subset_file)

    if missing_files:
        print(f"ERROR: Missing subset files: {{missing_files}}")
        return False

    # Start with the first file
    if len(subset_files) < 2:
        print("ERROR: Need at least 2 subset files to merge")
        return False

    # Merge files sequentially
    current_output = subset_files[0]

    for i in range(1, len(subset_files)):
        next_input = subset_files[i]

        if i == len(subset_files) - 1:
            # Final merge - use the original output filename
            final_output = r"{render_filepath}"
        else:
            # Intermediate merge
            final_output = r"{os.path.splitext(render_filepath)[0]}_temp_merge_{{i}}.exr"

        print(f"Merging {{current_output}} + {{next_input}} -> {{final_output}}")

        try:
            bpy.ops.cycles.merge_images(
                input_filepath1=current_output,
                input_filepath2=next_input,
                output_filepath=final_output
            )

            # Clean up intermediate files (except the first subset file)
            if i > 1 and os.path.exists(current_output) and "temp_merge" in current_output:
                os.remove(current_output)
                print(f"Cleaned up intermediate file: {{current_output}}")

            current_output = final_output

        except Exception as e:
            print(f"ERROR: Failed to merge images: {{e}}")
            return False

    print(f"Successfully merged {{len(subset_files)}} subset images into {{current_output}}")

    # Clean up subset files
    for subset_file in subset_files:
        try:
            if os.path.exists(subset_file):
                os.remove(subset_file)
                print(f"Cleaned up subset file: {{subset_file}}")
        except Exception as e:
            print(f"WARNING: Failed to clean up {{subset_file}}: {{e}}")

    return True

# Run the merge immediately and exit
if __name__ == "__main__":
    print("Merge-only script executing...")
    success = merge_subset_images()
    if success:
        print("Split frame merge completed successfully")
        # Force exit to prevent any rendering
        sys.exit(0)
    else:
        print("Split frame merge failed")
        sys.exit(1)
'''

    # Write the script to a temporary file
    script_filename = f"{filename}_merge_only_script.py"
    script_path = os.path.join(temp_dir, script_filename)

    with open(script_path, 'w') as f:
        f.write(script_content)

    print(f"DEBUG: Created merge-only script: {script_path}")
    return script_path

def submit_merge_job(scene, filename, job_count, subset_job_ids, context):
    """Submit a job to merge the sample subset images"""
    if not subset_job_ids:
        print("WARNING: No subset job IDs provided for merge job")
        return None

    # Create the merge-only script (no rendering)
    script_path = create_merge_only_script(scene, filename, job_count, subset_job_ids)

    # Create an empty Blender scene for merge job to avoid any rendering
    empty_scene_path = create_empty_scene_for_merge()

    # Create job info for merge job
    merge_job_info_path = os.path.join(temp_dir, "merge_job_info.job")
    merge_plugin_info_path = os.path.join(temp_dir, "merge_plugin_info.plugin")

    # Write merge job info
    with open(merge_job_info_path, "w") as f:
        f.write("Plugin=Blender\n")
        f.write(f"Name={filename}_merge\n")
        f.write(f"Frames=1-1\n")  # Single frame job
        f.write(f"ChunkSize=1\n")
        f.write(f"Priority={context.window_manager.job_priority}\n")

        # Use selected pool from dropdown
        selected_pool = context.window_manager.deadline_pool
        f.write(f"Pool={selected_pool}\n")

        # Add dependencies on all subset jobs
        dependencies = ",".join(subset_job_ids)
        f.write(f"JobDependencies={dependencies}\n")

        # Add suspended state if selected
        if context.window_manager.submit_suspended:
            f.write("InitialStatus=Suspended\n")

    # Write merge plugin info
    with open(merge_plugin_info_path, "w") as f:
        # Use the empty scene file to avoid any rendering
        script_filename = os.path.basename(script_path)

        f.write(f"SceneFile={os.path.normpath(empty_scene_path)}\n")
        f.write(f"Arguments=-P {script_filename}\n")  # Run the merge-only script
        f.write("Threads=0\n")

        # Explicitly disable rendering
        f.write("EnableProgressReports=false\n")
        f.write("StrictErrorChecking=false\n")

    # Submit the merge job
    cmd_list = [get_deadline_path(), "-SubmitJob", merge_job_info_path, merge_plugin_info_path]

    # Add auxiliary files: the original scene file and the merge script
    if bpy.data.filepath:
        cmd_list.append(bpy.data.filepath)
    cmd_list.append(script_path)

    env = os.environ.copy()
    python_vars_to_remove = ['PYTHONPATH', 'PYTHONHOME', 'PYTHON', 'PYTHONSTARTUP', 'PYTHONIOENCODING']
    for var in python_vars_to_remove:
        env.pop(var, None)

    result = subprocess.run(
        cmd_list,
        shell=False,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        env=env
    )

    print(f"Merge job - Return code: {result.returncode}")
    print(f"Merge job - Output: {result.stdout}")
    if result.stderr:
        print(f"Merge job - Errors: {result.stderr}")

    # Get merge job ID
    merge_job_id = None
    for line in result.stdout.splitlines():
        if "JobID=" in line:
            merge_job_id = line.split("JobID=")[1].strip()
            break

    if merge_job_id:
        print(f"DEBUG: Merge job submitted with ID: {merge_job_id}")
    else:
        print("WARNING: Failed to get merge job ID")

    return merge_job_id

def get_selected_cameras():
    """Get all selected camera objects"""
    selected_cameras = []
    for obj in bpy.context.selected_objects:
        if obj.type == 'CAMERA':
            selected_cameras.append(obj)
    return selected_cameras

def submit_camera_job(scene, camera, filename, context):
    """Submit a job for a specific camera"""
    print(f"DEBUG: Submitting job for camera: {camera.name}")

    # Store original camera
    original_camera = scene.camera

    # Set the camera as active
    scene.camera = camera

    # Modify the output filename to include camera name
    original_filepath = scene.render.filepath

    # Clean camera name for filename - replace dots with underscores to avoid confusion with frame numbers
    clean_camera_name = camera.name.replace('.', '_')

    # Insert camera name before the file extension or frame number
    if "#" in original_filepath:
        # Handle frame number patterns like #### or %04d
        parts = original_filepath.split("#")
        if len(parts) >= 2:
            base_part = parts[0]
            frame_part = "#" + "#".join(parts[1:])
            new_filepath = f"{base_part}_{clean_camera_name}_{frame_part}"
        else:
            new_filepath = f"{original_filepath}_{clean_camera_name}_"
    else:
        # No frame numbers - split the original path first, then insert camera name
        path_without_ext, extension = os.path.splitext(original_filepath)
        new_filepath = f"{path_without_ext}_{clean_camera_name}_{extension}"

    scene.render.filepath = new_filepath
    print(f"DEBUG: Modified output path for camera {camera.name}: {new_filepath}")

    # Save the scene with the new camera and output path
    print(f"DEBUG: Saving scene for camera {camera.name}")
    bpy.ops.wm.save_mainfile()

    # Submit the job using the same logic as normal submission
    # Create a custom filename that includes the cleaned camera name for the job
    camera_filename = f"{filename}_{clean_camera_name}"
    write_job_info(scene, camera_filename)

    # Temporarily force submit_scene_file to True for camera jobs to ensure proper auxiliary file handling
    original_submit_scene_file = context.window_manager.submit_scene_file
    context.window_manager.submit_scene_file = True

    write_plugin_info(scene.name)

    # Build command with auxiliary file (same as normal submission when submit_scene_file is True)
    cmd_list = [get_deadline_path(), "-SubmitJob", JOB_INFO_PATH, PLUGIN_INFO_PATH]

    # Add scene file as auxiliary file (same logic as normal submission)
    if bpy.data.filepath:
        cmd_list.append(bpy.data.filepath)
        cmd_str = f"{get_deadline_path()} -SubmitJob {JOB_INFO_PATH} {PLUGIN_INFO_PATH} {bpy.data.filepath}"
    else:
        cmd_str = f"{get_deadline_path()} -SubmitJob {JOB_INFO_PATH} {PLUGIN_INFO_PATH}"

    print(f"DEBUG: Camera job command: {cmd_str}")

    # Execute the submission
    env = os.environ.copy()
    python_vars_to_remove = ['PYTHONPATH', 'PYTHONHOME', 'PYTHON', 'PYTHONSTARTUP', 'PYTHONIOENCODING']
    for var in python_vars_to_remove:
        env.pop(var, None)

    result = subprocess.run(
        cmd_list,
        shell=False,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        env=env
    )

    # Restore the original submit_scene_file setting
    context.window_manager.submit_scene_file = original_submit_scene_file

    print(f"Camera {camera.name} job - Return code: {result.returncode}")
    print(f"Camera {camera.name} job - Output: {result.stdout}")
    if result.stderr:
        print(f"Camera {camera.name} job - Errors: {result.stderr}")

    # Get the job ID from the output for potential MP4 creation
    job_id = None
    for line in result.stdout.splitlines():
        if "JobID=" in line:
            job_id = line.split("JobID=")[1].strip()
            break

    # If MP4 creation is enabled and we have a job ID, submit an FFmpeg job for this camera
    if context.window_manager.create_mp4 and job_id:
        print(f"DEBUG: Creating MP4 job for camera {camera.name}")
        ffmpeg_job_info, ffmpeg_plugin_info = write_ffmpeg_job_info(scene, camera_filename, job_id)

        # Create clean environment for FFmpeg job
        ffmpeg_env = os.environ.copy()
        python_vars_to_remove = ['PYTHONPATH', 'PYTHONHOME', 'PYTHON', 'PYTHONSTARTUP', 'PYTHONIOENCODING']
        for var in python_vars_to_remove:
            ffmpeg_env.pop(var, None)

        ffmpeg_cmd = f"{get_deadline_path()} -SubmitJob {ffmpeg_job_info} {ffmpeg_plugin_info}"
        ffmpeg_result = subprocess.run(
            ffmpeg_cmd,
            shell=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            env=ffmpeg_env
        )
        print(f"Camera {camera.name} FFmpeg job - Return code: {ffmpeg_result.returncode}")
        print(f"Camera {camera.name} FFmpeg job - Output: {ffmpeg_result.stdout}")
        if ffmpeg_result.stderr:
            print(f"Camera {camera.name} FFmpeg job - Errors: {ffmpeg_result.stderr}")

    # Restore original filepath
    scene.render.filepath = original_filepath

    return result.returncode == 0

DEADLINE_PATH = get_deadline_path()

# Generate a temporary directory to store job information
temp_dir = tempfile.mkdtemp()

filename = os.path.splitext(os.path.basename(bpy.data.filepath))[0]

JOB_INFO_PATH = os.path.join(temp_dir, "job_info.job")
PLUGIN_INFO_PATH = os.path.join(temp_dir, "plugin_info.plugin")

# Store the JSON files in Blender's config directory
config_dir = bpy.utils.user_resource('CONFIG')
FOLDER_HISTORY_PATH = os.path.join(config_dir, "blender_folder_history.json")
POOLS_CACHE_PATH = os.path.join(config_dir, "blender_deadline_pools.json")

bpy.types.Scene.is_selected_for_submission = bpy.props.BoolProperty(
    name="Selected for Submission",
    description="Whether the scene is selected for submission to Deadline",
    default=False
)

bpy.types.WindowManager.duplicate_files = bpy.props.CollectionProperty(type=bpy.types.PropertyGroup)

def get_filename():
    return os.path.splitext(os.path.basename(bpy.data.filepath))[0]


class GetFilesFromNetworkOperator(bpy.types.Operator):
    bl_idname = "scene.get_files_from_network"
    bl_label = "Copy Files from Network"
    
    def invoke(self, context, event):
        network_folder = context.scene.network_folder
        local_folder = context.scene.local_folder
        
        # Get the list of duplicates
        duplicates = sync_files(network_folder, local_folder)

        if duplicates:
            # Summarize duplicates by file extension
            duplicates_summary = {}
            for file_path in duplicates:
                ext = os.path.splitext(file_path)[1]
                duplicates_summary[ext] = duplicates_summary.get(ext, 0) + 1

            # Clear the existing list
            context.window_manager.duplicate_files.clear()
            
            # Populate the list with the summary
            for ext, count in duplicates_summary.items():
                item = context.window_manager.duplicate_files.add()
                item.name = f"{count} {ext} files"
            
            # Show the DuplicateFilesPopup
            bpy.ops.scene.duplicate_files_popup('INVOKE_DEFAULT')
            return {'CANCELLED'}
        
        # If no duplicates, proceed with the original invoke logic
        return context.window_manager.invoke_props_dialog(self, width=600)

class DuplicateFilesPopupOK(bpy.types.Operator):
    bl_idname = "scene.duplicate_files_popup_ok"
    bl_label = "Confirm Overwrite"

    def execute(self, context):
        local_folder = context.scene.local_folder
        network_folder = context.scene.network_folder

        for item in context.window_manager.duplicate_files:
            if item.overwrite:
                # Extract file extension from the item name
                ext = item.name.split(' ')[-2]  # Assumes format "3 .jpg files"
                # Iterate over files in the local folder
                for file_name in os.listdir(local_folder):
                    if file_name.endswith(ext):
                        local_file = os.path.join(local_folder, file_name)
                        network_file = os.path.join(network_folder, file_name)
                        shutil.copy2(local_file, network_file)

        context.window_manager.duplicate_files.clear()
        return {'FINISHED'}

class DuplicateFileItem(bpy.types.PropertyGroup):
    name: bpy.props.StringProperty()  # This will hold something like "3 .jpg files"
    overwrite: bpy.props.BoolProperty(name="Overwrite", default=True)

class DuplicateFilesPopupCancel(bpy.types.Operator):
    bl_idname = "scene.duplicate_files_popup_cancel"
    bl_label = "Cancel Overwrite"

    def execute(self, context):
        context.window_manager.duplicate_files.clear()
        return {'FINISHED'}

class DuplicateFilesPopup(bpy.types.Operator):
    bl_idname = "scene.duplicate_files_popup"
    bl_label = "Duplicate Files Found, Overwrite?"
    bl_options = {'REGISTER', 'INTERNAL'}

    @classmethod
    def poll(cls, context):
        return len(context.window_manager.duplicate_files) > 0

    def execute(self, context):
        # Clear the list after handling
        context.window_manager.duplicate_files.clear()
        return {'FINISHED'}

    def invoke(self, context, event):
        return context.window_manager.invoke_props_dialog(self, width=600)

    def draw(self, context):
        layout = self.layout
        layout.label(text=self.bl_label, icon='QUESTION')

        # Scrollable list of summarized duplicates
        scroll = layout.box()
        col = scroll.column()
        for item in context.window_manager.duplicate_files:
            row = col.row()
            row.prop(item, "overwrite", text="")
            row.label(text=item.name)

        # OK and Cancel buttons
        row = layout.row()
        row.operator("scene.duplicate_files_popup_ok", text="OK")
        row.operator("scene.duplicate_files_popup_cancel", text="Cancel")

def write_draft_job_info(scene, local_folder, network_folder, filename, render_job_id):
    # Generate a temporary path for the Draft job info
    draft_job_info_path = os.path.join(temp_dir, "draft_job_info.job")
    draft_plugin_info_path = os.path.join(temp_dir, "draft_plugin_info.plugin")
    
    # Get the output path from the render job - convert relative path first
    render_filepath = scene.render.filepath
    if render_filepath.startswith("//"):
        render_filepath = bpy.path.abspath(render_filepath)
        print(f"DEBUG: Converted relative render path to absolute: {render_filepath}")

    output_path = render_filepath.replace(local_folder, network_folder)
    output_directory = os.path.dirname(output_path)
    
    # Setup a pattern that matches the rendered frames
    if "#" in output_path:
        # Replace # with * for wildcard matching
        input_pattern = output_path.replace("#", "*")
    else:
        # Add frame pattern if not present
        directory = os.path.dirname(output_path)
        prefix = os.path.splitext(os.path.basename(output_path))[0]
        extension = os.path.splitext(output_path)[1]
        input_pattern = os.path.join(directory, prefix + "*" + extension)
    
    # Determine the output movie filename
    mp4_filename = f"{os.path.splitext(os.path.basename(bpy.data.filepath))[0]}_{scene.name}.mp4"
    mp4_output_path = os.path.join(output_directory, mp4_filename)
    
    # Write the job info file for Draft
    with open(draft_job_info_path, "w") as f:
        f.write("Plugin=DraftPlugin\n")
        f.write(f"Name={filename}_{scene.name}_MP4\n")
        f.write(f"Priority={bpy.context.window_manager.job_priority}\n")
        f.write("Pool=blendergpu\n")
        f.write(f"OutputDirectory0={output_directory}\n")
        f.write(f"OutputFilename0={mp4_output_path}\n")
        f.write(f"JobDependencies={render_job_id}\n")
    
    # Write the plugin info file for Draft
    with open(draft_plugin_info_path, "w") as f:
        f.write("InputFile0=%s\n" % input_pattern)
        f.write("OutputFile=%s\n" % mp4_output_path)
        f.write("Format=Quick Draft\n")
        f.write("Mode=Movie\n")
        f.write("Codec=H.264\n")
        f.write("Quality=High\n")
        f.write("FrameRate=24\n")  # Could be extended to get this from scene settings
        f.write("Resolution=Same As Input\n")
    
    return draft_job_info_path, draft_plugin_info_path

def write_ffmpeg_job_info(scene, filename, render_job_id):
    # Generate a temporary path for the FFmpeg job info
    ffmpeg_job_info_path = os.path.join(temp_dir, "ffmpeg_job_info.job")
    ffmpeg_plugin_info_path = os.path.join(temp_dir, "ffmpeg_plugin_info.plugin")

    # Get the output path from the render job - convert relative path to absolute
    render_filepath = scene.render.filepath
    if render_filepath.startswith("//"):
        render_filepath = bpy.path.abspath(render_filepath)
        print(f"DEBUG: Converted relative render path to absolute: {render_filepath}")

    # Use the absolute path directly - no need for local/network conversion
    output_path = os.path.normpath(render_filepath)
    output_directory = os.path.dirname(output_path)

    print(f"DEBUG: FFmpeg paths:")
    print(f"  Original render_filepath: {scene.render.filepath}")
    print(f"  Absolute render_filepath: {render_filepath}")
    print(f"  Output path: {output_path}")
    print(f"  Output directory: {output_directory}")
    
    # Get the file extension from render settings
    format_extension_map = {
        'BMP': '.bmp',
        'IRIS': '.rgb',
        'PNG': '.png',
        'JPEG': '.jpg',
        'JPEG2000': '.jp2',
        'TARGA': '.tga',
        'TARGA_RAW': '.tga',
        'CINEON': '.cin',
        'DPX': '.dpx',
        'OPEN_EXR_MULTILAYER': '.exr',
        'OPEN_EXR': '.exr',
        'HDR': '.hdr',
        'TIFF': '.tif',
        'WEBP': '.webp'
    }
    render_format = scene.render.image_settings.file_format
    extension = format_extension_map.get(render_format, '.png')  # Default to .png if format not found
    
    # Setup a pattern that matches the rendered frames
    if "#" in output_path:
        # Replace Blender's # padding with FFmpeg's %04d format
        input_pattern = output_path.replace("####", "%04d")
        print(f"DEBUG: Converted # padding to %04d: {input_pattern}")
    else:
        # Check if the path already ends with an underscore (indicating frame numbers will be appended)
        directory = os.path.dirname(output_path)
        basename = os.path.basename(output_path)

        if basename.endswith("_"):
            # Path already has underscore for frame numbers, just add the pattern
            input_pattern = output_path + "%04d" + extension
        else:
            # Blender appends frame numbers directly to the filename without underscore
            # So we need to match the pattern: filename + frame_number + extension
            prefix = os.path.splitext(basename)[0]
            input_pattern = os.path.join(directory, prefix + "%04d" + extension)

        print(f"DEBUG: Created FFmpeg input pattern: {input_pattern}")
    
    # Determine the output movie filename
    mp4_filename = f"{os.path.splitext(os.path.basename(bpy.data.filepath))[0]}_{scene.name}.mp4"
    mp4_output_path = os.path.join(output_directory, mp4_filename)
    
    # Get frame rate from scene or use default
    frame_rate = scene.render.fps if hasattr(scene.render, 'fps') else 24

    # Determine the starting frame number for FFmpeg
    start_frame = 1  # Default
    if bpy.context.window_manager.render_current_frame:
        start_frame = bpy.context.scene.frame_current
    elif scene.custom_frame_list_enabled and scene.custom_frame_list.strip():
        # For custom frame list, get the first frame number
        frame_list = scene.custom_frame_list.strip()
        first_frame_str = frame_list.split(',')[0].strip()
        # Handle ranges like "10-15"
        if '-' in first_frame_str:
            start_frame = int(first_frame_str.split('-')[0])
        else:
            start_frame = int(first_frame_str)
    elif scene.override_frame_range:
        start_frame = scene.override_frame_start
    else:
        start_frame = scene.frame_start

    print(f"DEBUG: FFmpeg start frame: {start_frame}")
    
    # Write the job info file for FFmpeg
    with open(ffmpeg_job_info_path, "w") as f:
        f.write("Plugin=FFmpeg\n")
        f.write(f"Name={filename}_{scene.name}_MP4\n")
        f.write(f"Priority={bpy.context.window_manager.job_priority}\n")
        f.write("Pool=blendergpu\n")
        f.write(f"OutputDirectory0={output_directory}\n")
        f.write(f"OutputFilename0={mp4_output_path}\n")
        f.write(f"JobDependencies={render_job_id}\n")
    
    # Write the plugin info file for FFmpeg
    with open(ffmpeg_plugin_info_path, "w") as f:
        # Input file and settings
        f.write(f"InputFile0={input_pattern}\n")
        f.write(f"InputArgs0=-framerate {frame_rate} -start_number {start_frame}\n")
        f.write("ReplacePadding0=False\n")  # We're using %04d format directly
        
        # Output file and settings
        f.write(f"OutputFile={mp4_output_path}\n")
        f.write(f"OutputArgs=-c:v libx264 -preset slow -crf 18 -pix_fmt yuv420p -r {frame_rate}\n")
        
        # Additional arguments if needed
        f.write("AdditionalArgs=\n")
        
        # Use same input args for all inputs (if we had multiple)
        f.write("UseSameInputArgs=True\n")
    
    return ffmpeg_job_info_path, ffmpeg_plugin_info_path

def convert_to_network_path(path, local_root, network_root):
    """
    Convert a local path to a corresponding network path.

    :param path: The local path to convert.
    :param local_root: The root of the local directory structure.
    :param network_root: The root of the network directory structure.
    :return: The converted network path.
    """
    # Normalize paths
    normalized_path = os.path.normpath(path)
    normalized_local_root = os.path.normpath(local_root)

    # Get the relative path from the local root
    relative_path = os.path.relpath(normalized_path, normalized_local_root)

    # Construct the new network path
    network_path = os.path.join(network_root, relative_path)

    return network_path

def convert_to_local_path(path, local_root, network_root):
    """
    Convert a network path to a corresponding local path.

    :param path: The network path to convert.
    :param local_root: The root of the local directory structure.
    :param network_root: The root of the network directory structure.
    :return: The converted local path.
    """
    # Normalize paths
    normalized_path = os.path.normpath(path)
    normalized_network_root = os.path.normpath(network_root)

    # Check if the path starts with the network root
    if normalized_path.startswith(normalized_network_root):
        # Get the relative path from the network root
        relative_path = os.path.relpath(normalized_path, normalized_network_root)

        # Construct the new local path
        local_path = os.path.join(local_root, relative_path)
        return local_path
    else:
        # If the path is not in the network directory, return it unchanged
        return path

def repath_external_references(local_root, network_root, to_network=True):
    paths_were_changed = False

    # Determine which repath function to use
    repath_function = convert_to_network_path if to_network else convert_to_local_path

    # Images
    for image in bpy.data.images:
        if is_local_path(image.filepath, local_root) == to_network:
            image.filepath = repath_function(image.filepath, local_root, network_root)
            paths_were_changed = True

    # Movie Clips
    for clip in bpy.data.movieclips:
        if is_local_path(clip.filepath, local_root) == to_network:
            clip.filepath = repath_function(clip.filepath, local_root, network_root)
            paths_were_changed = True

    # Sounds
    for sound in bpy.data.sounds:
        if is_local_path(sound.filepath, local_root) == to_network:
            sound.filepath = repath_function(sound.filepath, local_root, network_root)
            paths_were_changed = True

    # Fonts
    for font in bpy.data.fonts:
        if is_local_path(font.filepath, local_root) == to_network:
            font.filepath = repath_function(font.filepath, local_root, network_root)
            paths_were_changed = True

    # Linked Libraries
    for library in bpy.data.libraries:
        if is_local_path(library.filepath, local_root) == to_network:
            library.filepath = repath_function(library.filepath, local_root, network_root)
            paths_were_changed = True
            
    # Adjust scene output paths
    for scene in bpy.data.scenes:
        if is_local_path(scene.render.filepath, local_root) == to_network:
            scene.render.filepath = repath_function(scene.render.filepath, local_root, network_root)
            paths_were_changed = True

    # Save the Blender file if any paths were changed
    if paths_were_changed:
        bpy.ops.wm.save_mainfile()

class SubmitToDeadlineOperator(bpy.types.Operator):
    bl_idname = "scene.submit_to_deadline"
    bl_label = "Submit to Deadline"
    
    def execute(self, context):
        # Get the latest filename
        filename = get_filename()
        
        # Save the folders to history
        save_folder_history("local", context.scene.local_folder)
        save_folder_history("network", context.scene.network_folder)
        local_folder = context.scene.local_folder
        network_folder = context.scene.network_folder

        # Always run the repathing if both local and network paths are set
        if local_folder and network_folder:
            repath_external_references(local_folder, network_folder, to_network=True)

        # Filter only the scenes that are marked for submission
        scenes_to_submit = [scene for scene in bpy.data.scenes if scene.is_selected_for_submission]

        if not scenes_to_submit:
            self.report({'ERROR'}, "No scenes selected for submission.")
            return {'CANCELLED'}

        # Check if multi-camera rendering is enabled
        if context.window_manager.render_all_cameras:
            selected_cameras = get_selected_cameras()
            if not selected_cameras:
                self.report({'ERROR'}, "No cameras selected for multi-camera rendering. Please select one or more camera objects.")
                return {'CANCELLED'}

            print(f"DEBUG: Multi-camera rendering enabled. Found {len(selected_cameras)} selected cameras.")

            # Process each scene with multi-camera rendering
            for scene in scenes_to_submit:
                # Store original camera to restore later
                original_camera = scene.camera

                success_count = 0
                for camera in selected_cameras:
                    if submit_camera_job(scene, camera, filename, context):
                        success_count += 1
                    else:
                        print(f"WARNING: Failed to submit job for camera {camera.name}")

                # Restore original camera and save
                scene.camera = original_camera
                print(f"DEBUG: Restored original camera: {original_camera.name if original_camera else 'None'}")
                bpy.ops.wm.save_mainfile()

                print(f"DEBUG: Successfully submitted {success_count}/{len(selected_cameras)} camera jobs for scene {scene.name}")

            self.report({'INFO'}, f"Multi-camera rendering: Submitted jobs for {len(selected_cameras)} cameras across {len(scenes_to_submit)} scenes.")
            return {'FINISHED'}

        # Check if split still frame rendering is enabled
        if context.window_manager.split_still_frame:
            # Validate split frame requirements
            if len(scenes_to_submit) > 1:
                self.report({'ERROR'}, "Split Still Frame can only be used with a single scene. Please select only one scene.")
                return {'CANCELLED'}

            if not context.window_manager.render_current_frame:
                self.report({'ERROR'}, "Split Still Frame requires 'Render Current Frame Only' to be enabled.")
                return {'CANCELLED'}

            scene = scenes_to_submit[0]

            # Check if the scene uses Cycles
            if scene.render.engine != 'CYCLES':
                self.report({'ERROR'}, "Split Still Frame only works with Cycles render engine.")
                return {'CANCELLED'}

            print(f"DEBUG: Split frame rendering enabled for scene: {scene.name}")

            # Submit split frame jobs
            subset_job_ids = submit_split_frame_jobs(scene, filename, context)

            if subset_job_ids:
                # Submit merge job
                merge_job_id = submit_merge_job(scene, filename, context.window_manager.split_frame_jobs, subset_job_ids, context)

                # Save the scene to ensure it's in its original state
                print("DEBUG: Saving scene after split frame submission to preserve original state")
                bpy.ops.wm.save_mainfile()

                if merge_job_id:
                    self.report({'INFO'}, f"Split frame rendering: Submitted {len(subset_job_ids)} subset jobs and 1 merge job.")
                else:
                    self.report({'WARNING'}, f"Split frame rendering: Submitted {len(subset_job_ids)} subset jobs but merge job failed.")
            else:
                self.report({'ERROR'}, "Failed to submit split frame jobs.")
                return {'CANCELLED'}

            return {'FINISHED'}

        # Normal single-camera submission
        for scene in scenes_to_submit:
            write_job_info(scene, filename)
            write_plugin_info(scene.name)

            # Build command arguments - add scene file as auxiliary if enabled
            cmd_list = [get_deadline_path(), "-SubmitJob", JOB_INFO_PATH, PLUGIN_INFO_PATH]

            # Add scene file as auxiliary file if the option is enabled
            if context.window_manager.submit_scene_file and bpy.data.filepath:
                # Save the file first to ensure latest changes are included
                print("DEBUG: Saving Blender file before submission to include latest changes...")
                bpy.ops.wm.save_mainfile()

                cmd_list.append(bpy.data.filepath)
                cmd_str = f"{get_deadline_path()} -SubmitJob {JOB_INFO_PATH} {PLUGIN_INFO_PATH} {bpy.data.filepath}"
            else:
                cmd_str = f"{get_deadline_path()} -SubmitJob {JOB_INFO_PATH} {PLUGIN_INFO_PATH}"

            print(f"DEBUG: Command list: {cmd_list}")
            print(f"DEBUG: Command string: {cmd_str}")

            # Create clean environment
            env = os.environ.copy()
            python_vars_to_remove = ['PYTHONPATH', 'PYTHONHOME', 'PYTHON', 'PYTHONSTARTUP', 'PYTHONIOENCODING']
            for var in python_vars_to_remove:
                env.pop(var, None)

            # Execute using command list (more reliable than shell string)
            result = subprocess.run(
                cmd_list,
                shell=False,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                env=env
            )

            print(f"Command: {cmd_str}")
            print(f"Return code: {result.returncode}")
            print(f"Output: {result.stdout}")
            print(f"Errors: {result.stderr}")

            # Get the job ID from the output
            job_id = None
            for line in result.stdout.splitlines():
                if "JobID=" in line:
                    job_id = line.split("JobID=")[1].strip()
                    break

            # If MP4 creation is enabled and we have a job ID, submit an FFmpeg job
            if context.window_manager.create_mp4 and job_id:
                ffmpeg_job_info, ffmpeg_plugin_info = write_ffmpeg_job_info(scene, filename, job_id)
                ffmpeg_cmd = f"{get_deadline_path()} -SubmitJob {ffmpeg_job_info} {ffmpeg_plugin_info}"
                ffmpeg_result = subprocess.run(ffmpeg_cmd, shell=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
                print(f"FFmpeg Command: {ffmpeg_cmd}")
                print(f"FFmpeg Return code: {ffmpeg_result.returncode}")
                print(f"FFmpeg Output: {ffmpeg_result.stdout}")
                print(f"FFmpeg Errors: {ffmpeg_result.stderr}")

        return {'FINISHED'}

class SCENE_UL_ScenesList(bpy.types.UIList):
    def draw_item(self, context, layout, data, item, icon, active_data, active_propname, index):
        scene = item
        if self.layout_type in {'DEFAULT', 'COMPACT'}:
            split = layout.split(factor=0.1)
            split.prop(scene, "is_selected_for_submission", text="")
            split.label(text=scene.name, icon='SCENE_DATA')
        elif self.layout_type in {'GRID'}:
            layout.alignment = 'CENTER'
            layout.label(text="", icon='SCENE_DATA')

class BrowseLocalFolder(bpy.types.Operator):
    bl_idname = "scene.browse_local_folder"
    bl_label = "Browse Local Folder"
    bl_description = "Browse for a local folder"
    
    directory: bpy.props.StringProperty(subtype='DIR_PATH')

    def execute(self, context):
        if self.directory:
            context.scene.local_folder = self.directory
        return {'FINISHED'}

    def invoke(self, context, event):
        context.window_manager.fileselect_add(self)
        return {'RUNNING_MODAL'}

class BrowseNetworkFolder(bpy.types.Operator):
    bl_idname = "scene.browse_network_folder"
    bl_label = "Browse Network Folder"
    bl_description = "Browse for a network folder"
    
    directory: bpy.props.StringProperty(subtype='DIR_PATH')

    def execute(self, context):
        if self.directory:
            context.scene.network_folder = self.directory
        return {'FINISHED'}

    def invoke(self, context, event):
        context.window_manager.fileselect_add(self)
        return {'RUNNING_MODAL'}

class DeadlineSubmissionPanel(bpy.types.Panel):
    bl_label = "Deadline Submission"
    bl_idname = "SCENE_PT_deadline_submission"
    bl_space_type = 'PROPERTIES'
    bl_region_type = 'WINDOW'
    bl_context = "render"
    
    def draw(self, context):
        layout = self.layout

        # Get the active scene
        active_scene = context.scene
        
        # Check if active scene's output is video format
        is_video = is_video_output(active_scene)

        # Priority and Chunk Size
        layout.prop(context.window_manager, "job_priority", slider=True)

        # Chunk size row with conditional display
        row = layout.row()
        if is_video:
            row.enabled = False
            row.prop(context.window_manager, "chunk_size")
            layout.label(text="Chunk size unavailable - video output will be rendered by 1 machine only", icon='INFO')
        else:
            row.prop(context.window_manager, "chunk_size")



        # Pool selection (moved under checkboxes) with update button
        row = layout.row()
        row.prop(context.window_manager, "deadline_pool", text="Render Pool")
        row.operator("scene.update_deadline_pools", text="", icon='FILE_REFRESH')

        # Submit button
        layout.operator("scene.submit_to_deadline")

class PROPERTIES_PT_DeadlineScenesToRenderSubPanel(bpy.types.Panel):
    bl_label = "Scenes to Render"
    bl_parent_id = "SCENE_PT_deadline_submission"
    bl_space_type = 'PROPERTIES'
    bl_region_type = 'WINDOW'
    bl_context = "render"


    def draw(self, context):
        layout = self.layout
        # Display the custom multi-select UI list for scenes
        layout.template_list("SCENE_UL_ScenesList", "", bpy.data, "scenes", context.window_manager, "selected_scenes_index", rows=4, type='DEFAULT')

class PROPERTIES_PT_DeadlineSubmissionOptionsSubPanel(bpy.types.Panel):
    bl_label = "Submission Options"
    bl_parent_id = "SCENE_PT_deadline_submission"
    bl_space_type = 'PROPERTIES'
    bl_region_type = 'WINDOW'
    bl_context = "render"
    bl_options = {'DEFAULT_CLOSED'}

    def draw(self, context):
        layout = self.layout
        active_scene = context.scene

        # Render current frame option (under chunk size, above other checkboxes)
        layout.prop(context.window_manager, "render_current_frame")

        # Frame range override - put controls on same row
        row = layout.row()
        row.prop(active_scene, "override_frame_range")
        if active_scene.override_frame_range:
            row.prop(active_scene, "override_frame_start", text="Start")
            row.prop(active_scene, "override_frame_end", text="End")

        # Custom frame list option
        row = layout.row()
        row.prop(active_scene, "custom_frame_list_enabled")
        if active_scene.custom_frame_list_enabled:
            row.prop(active_scene, "custom_frame_list", text="")

        # MP4 creation option
        layout.prop(context.window_manager, "create_mp4")

        # Submit options
        layout.prop(context.window_manager, "submit_suspended")
        layout.prop(context.window_manager, "submit_scene_file")

        # Split Still Frame option
        row = layout.row()
        row.prop(context.window_manager, "split_still_frame")
        if context.window_manager.split_still_frame:
            row.prop(context.window_manager, "split_frame_jobs", text="Jobs")

            # Show sample distribution warning
            if context.scene.render.engine == 'CYCLES':
                total_samples = context.scene.cycles.samples
                job_count = context.window_manager.split_frame_jobs
                samples_per_job = total_samples // job_count if job_count > 0 else 0

                box = layout.box()
                box.label(text="Will force OpenEXR output and disable denoising!", icon='INFO')

                # Sample distribution info and warnings
                info_row = box.row()
                info_row.label(text=f"Samples per job: {samples_per_job} ({total_samples} total ÷ {job_count} jobs)")

                if job_count > total_samples:
                    warning_row = box.row()
                    warning_row.label(text=f"ERROR: Cannot have more jobs than samples!", icon='ERROR')
                    warning_row = box.row()
                    warning_row.label(text=f"Maximum: {total_samples} jobs")
                elif samples_per_job < 4:
                    warning_row = box.row()
                    warning_row.label(text=f"WARNING: Very low samples per job!", icon='ERROR')
                    warning_row = box.row()
                    warning_row.label(text=f"Recommended: {max(2, total_samples // 8)} jobs or fewer")
                elif samples_per_job < 8:
                    warning_row = box.row()
                    warning_row.label(text=f"WARNING: Low samples per job", icon='QUESTION')
                    warning_row = box.row()
                    warning_row.label(text=f"Consider: {max(2, total_samples // 16)} jobs for better distribution")
            else:
                box = layout.box()
                box.label(text="Will force OpenEXR output and disable denoising!", icon='INFO')
                box.label(text="Requires Cycles render engine", icon='ERROR')

        # Multi-camera rendering option
        layout.prop(context.window_manager, "render_all_cameras")
        if context.window_manager.render_all_cameras:
            box = layout.box()
            box.label(text="Scene will be saved when submitted!", icon='INFO')

class UpdatePoolsOperator(bpy.types.Operator):
    bl_idname = "scene.update_deadline_pools"
    bl_label = "Update Pools"
    bl_description = "Refresh the list of available Deadline pools from the server"

    def execute(self, context):
        # Clear the in-memory cache
        global _cached_pools
        _cached_pools = None

        # Get fresh pools from server and update cache
        print("DEBUG: Manually updating pools from server...")
        pools = get_deadline_pools_from_server()
        save_pools_to_cache(pools)

        # Update the in-memory cache
        _cached_pools = pools

        self.report({'INFO'}, f"Updated pools: {', '.join(pools)}")
        return {'FINISHED'}

class DeleteFolderHistory(bpy.types.Operator):
    bl_idname = "scene.delete_folder_history"
    bl_label = "Delete Folder from History"

    folder_type: bpy.props.StringProperty()
    folder_path: bpy.props.StringProperty()

    def execute(self, context):
        delete_folder_history(self.folder_type, self.folder_path)
        # Refresh the UI lists
        bpy.context.scene.LocalFolders.clear()
        bpy.context.scene.NetworkFolders.clear()
        for folder in load_folder_history("local"):
            item = bpy.context.scene.LocalFolders.add()
            item.name = folder
        for folder in load_folder_history("network"):
            item = bpy.context.scene.NetworkFolders.add()
            item.name = folder
        return {'FINISHED'}

class LocalizeReferencesOperator(bpy.types.Operator):
    bl_idname = "scene.localize_references"
    bl_label = "Localize References"

    def execute(self, context):
        local_folder = context.scene.local_folder
        network_folder = context.scene.network_folder

        # Only run if both paths are set
        if local_folder and network_folder:
            repath_external_references(local_folder, network_folder, to_network=False)

        return {'FINISHED'}
    
class SyncFilesOperator(bpy.types.Operator):
    bl_idname = "scene.sync_files"
    bl_label = "Copy Local Files to Network"

    def invoke(self, context, event):
        local_folder = context.scene.local_folder
        network_folder = context.scene.network_folder
        
        # Get the summary of duplicates
        duplicates_summary = sync_files(local_folder, network_folder)
                
        if duplicates_summary:
            # Clear the existing list
            context.window_manager.duplicate_files.clear()
            
            # Populate the list with the summary
            for ext, count in duplicates_summary.items():
                item = context.window_manager.duplicate_files.add()
                item.name = f"{count} {ext} files"
            
            # Show the DuplicateFilesPopup
            bpy.ops.scene.duplicate_files_popup('INVOKE_DEFAULT')
            return {'CANCELLED'}
        
        return context.window_manager.invoke_props_dialog(self, width=600)

    def execute(self, context):
        # Execution logic (if any)
        return {'FINISHED'}

def sync_files(source_folder, dest_folder):
    """
    Sync files and subfolders from local to network folder.
    Returns a list of duplicate files.
    """
    if not os.path.exists(dest_folder):
        os.makedirs(dest_folder)

    duplicates = []

    for root, dirs, files in os.walk(source_folder):
        relative_root = os.path.relpath(root, source_folder)
        for dir_name in dirs:
            network_dir_path = os.path.join(dest_folder, relative_root, dir_name)
            if not os.path.exists(network_dir_path):
                os.makedirs(network_dir_path)

        for file_name in files:
            local_file_path = os.path.join(root, file_name)
            network_file_path = os.path.join(dest_folder, relative_root, file_name)

            if os.path.exists(network_file_path):
                duplicates.append(os.path.join(relative_root, file_name))
            else:
                shutil.copy2(local_file_path, network_file_path)

    return duplicates

def is_local_path(path, local_root):
    """
    Check if the given path is a local path under the local_root directory.

    :param path: The path to check.
    :param local_root: The root of the local directory structure.
    :return: True if the path is local, False otherwise.
    """
    # Normalize paths for consistent comparison
    normalized_path = os.path.normpath(path)
    normalized_local_root = os.path.normpath(local_root)

    # Check if the normalized path starts with the local root path
    return normalized_path.startswith(normalized_local_root)

def save_folder_history(folder_type, new_folder):
    if not new_folder:  # Prevent saving empty strings
        return
    
    # Check if the file exists, if not, create an empty one
    if not os.path.exists(FOLDER_HISTORY_PATH):
        with open(FOLDER_HISTORY_PATH, 'w') as f:
            json.dump({"local": [], "network": []}, f)
    
    # Load existing folders
    with open(FOLDER_HISTORY_PATH, 'r') as f:
        data = json.load(f)

    # Add the new folder if it's not already in the list
    if new_folder not in data[folder_type]:
        data[folder_type].append(new_folder)

    # Save the updated folders
    with open(FOLDER_HISTORY_PATH, 'w') as f:
        json.dump(data, f)

def load_folder_history(folder_type):
    if os.path.exists(FOLDER_HISTORY_PATH):
        with open(FOLDER_HISTORY_PATH, 'r') as f:
            data = json.load(f)
            return data[folder_type]
    return []

def delete_folder_history(folder_type, folder_to_remove):
    if os.path.exists(FOLDER_HISTORY_PATH):
        with open(FOLDER_HISTORY_PATH, 'r') as f:
            data = json.load(f)
        
        if folder_to_remove in data[folder_type]:
            data[folder_type].remove(folder_to_remove)
        
        with open(FOLDER_HISTORY_PATH, 'w') as f:
            json.dump(data, f)

def is_video_output(scene):
    """Check if the output is a video format that requires single-machine rendering"""
    # Common video formats that should be processed on a single machine
    video_formats = ['FFMPEG', 'AVI_JPEG', 'AVI_RAW']
    
    # Check if the output format is a video format
    return scene.render.image_settings.file_format in video_formats

def write_job_info(scene, filename):
    with open(JOB_INFO_PATH, "w") as f:
        f.write("Plugin=Blender\n")
        f.write(f"Name={filename}_{scene.name}\n")
        
        # Handle frame range logic
        if bpy.context.window_manager.render_current_frame:
            # Render current frame only (takes priority over other settings)
            current_frame = bpy.context.scene.frame_current
            f.write(f"Frames={current_frame}-{current_frame}\n")
        elif scene.custom_frame_list_enabled and scene.custom_frame_list.strip():
            # Use custom frame list (comma-separated)
            f.write(f"Frames={scene.custom_frame_list.strip()}\n")
        elif scene.override_frame_range:
            # Use custom frame range
            f.write(f"Frames={scene.override_frame_start}-{scene.override_frame_end}\n")
        else:
            # Use scene's default frame range
            f.write(f"Frames={scene.frame_start}-{scene.frame_end}\n")
        
        # Calculate chunk size - determine if this is a video output that needs single-machine rendering
        if is_video_output(scene):
            # For video output, use frame count + 1 as chunk size to ensure it's rendered on one machine
            if bpy.context.window_manager.render_current_frame:
                chunk_size = 2  # 1 frame + 1
            elif scene.custom_frame_list_enabled and scene.custom_frame_list.strip():
                # For custom frame list, count the frames and add 1
                frame_list = scene.custom_frame_list.strip()
                # Simple count - count commas + 1 (rough estimate for video)
                frame_count = len(frame_list.split(','))
                chunk_size = frame_count + 1
            elif scene.override_frame_range:
                frame_count = scene.override_frame_end - scene.override_frame_start + 1
                chunk_size = frame_count + 1
            else:
                frame_count = scene.frame_end - scene.frame_start + 1
                chunk_size = frame_count + 1
        else:
            # For image sequence, use user-defined chunk size (unless rendering single frame or custom list)
            if bpy.context.window_manager.render_current_frame:
                chunk_size = 1  # Single frame
            elif scene.custom_frame_list_enabled and scene.custom_frame_list.strip():
                chunk_size = 1  # Let Deadline handle frame distribution for custom lists
            else:
                chunk_size = bpy.context.window_manager.chunk_size
        
        f.write(f"ChunkSize={chunk_size}\n")
        f.write(f"Priority={bpy.context.window_manager.job_priority}\n")

        # Use selected pool from dropdown
        selected_pool = bpy.context.window_manager.deadline_pool
        f.write(f"Pool={selected_pool}\n")

        # Add suspended state if selected
        if bpy.context.window_manager.submit_suspended:
            f.write("InitialStatus=Suspended\n")
        
        # Convert Blender relative path to absolute path
        render_filepath = scene.render.filepath
        if render_filepath.startswith("//"):
            render_filepath = bpy.path.abspath(render_filepath)
            print(f"DEBUG: Converted relative path {scene.render.filepath} to absolute: {render_filepath}")

        # Use the absolute path directly - no local/network conversion needed
        output_path = os.path.normpath(render_filepath)
        output_directory = os.path.dirname(output_path)

        # Create the output directory if it doesn't exist
        if not os.path.exists(output_directory):
            os.makedirs(output_directory)
            print(f"DEBUG: Created output directory: {output_directory}")

        f.write(f"OutputDirectory0={output_directory}\n")

        # Use the absolute path for output filename
        output_filename = output_path
        
        # Ensure padding is consistent
        if "#" not in output_filename:
            directory = os.path.dirname(output_filename)
            prefix = os.path.splitext(os.path.basename(output_filename))[0]
            extension = os.path.splitext(output_filename)[1]
            output_filename = os.path.join(directory, prefix + "####" + extension)
        
        f.write(f"OutputFilename0={output_filename}\n")

def write_plugin_info(scene_name):
    with open(PLUGIN_INFO_PATH, "w") as f:
        # Only write SceneFile if NOT submitting scene file as auxiliary
        # When submitting as auxiliary file, Deadline handles the scene file automatically
        if not bpy.context.window_manager.submit_scene_file:
            # Convert relative path to absolute path
            scene_filepath = bpy.data.filepath
            if scene_filepath.startswith("//"):
                scene_filepath = bpy.path.abspath(scene_filepath)
                print(f"DEBUG: Converted relative scene path to absolute: {scene_filepath}")

            # Use absolute path directly
            file_path = os.path.normpath(scene_filepath)
            f.write(f"SceneFile={file_path}\n")

        # Add the scene name
        f.write(f"Scene={scene_name}\n")

        # Output file path (similar to how we determined the output filename in write_job_info)
        render_filepath = bpy.data.scenes[scene_name].render.filepath
        if render_filepath.startswith("//"):
            render_filepath = bpy.path.abspath(render_filepath)
            print(f"DEBUG: Converted relative render path to absolute: {render_filepath}")

        # Use absolute path directly
        output_filename = os.path.normpath(render_filepath)

        if "#" not in output_filename:
            directory = os.path.dirname(output_filename)
            prefix = os.path.splitext(os.path.basename(output_filename))[0]
            extension = os.path.splitext(output_filename)[1]
            output_filename = os.path.join(directory, prefix + "####" + extension)
        
        f.write(f"OutputFile={output_filename}\n")
        # Specify the OutputFormat based on the render settings of the scene
        output_format = bpy.data.scenes[scene_name].render.image_settings.file_format
        f.write(f"OutputFormat={output_format}\n")

        f.write("Threads=0\n")

def register():
    bpy.utils.register_class(SubmitToDeadlineOperator)
    bpy.utils.register_class(DeadlineSubmissionPanel)  # Register main panel first
    bpy.utils.register_class(PROPERTIES_PT_DeadlineScenesToRenderSubPanel)
    bpy.utils.register_class(PROPERTIES_PT_DeadlineSubmissionOptionsSubPanel)
    bpy.utils.register_class(BrowseLocalFolder)
    bpy.utils.register_class(BrowseNetworkFolder)
    bpy.utils.register_class(SCENE_UL_ScenesList)
    bpy.utils.register_class(UpdatePoolsOperator)
    bpy.utils.register_class(DeleteFolderHistory)
    bpy.utils.register_class(LocalizeReferencesOperator)
    bpy.utils.register_class(SyncFilesOperator)
    bpy.utils.register_class(DuplicateFileItem)
    bpy.utils.register_class(DuplicateFilesPopupOK)
    bpy.utils.register_class(DuplicateFilesPopupCancel)
    bpy.utils.register_class(GetFilesFromNetworkOperator)
    bpy.types.WindowManager.duplicate_files = bpy.props.CollectionProperty(type=DuplicateFileItem)
    bpy.utils.register_class(DuplicateFilesPopup)
    bpy.types.Scene.duplicate_files_index = bpy.props.IntProperty()    
    bpy.types.WindowManager.selected_scenes_index = bpy.props.IntProperty(name="Selected Scene Index")
    bpy.types.Scene.local_folder = bpy.props.StringProperty(name="Local Folder", update=lambda s, c: save_folder_history("local", s.local_folder))
    bpy.types.Scene.network_folder = bpy.props.StringProperty(name="Network Folder", update=lambda s, c: save_folder_history("network", s.network_folder))
    bpy.types.Scene.LocalFolders = bpy.props.CollectionProperty(type=bpy.types.PropertyGroup)
    bpy.types.Scene.NetworkFolders = bpy.props.CollectionProperty(type=bpy.types.PropertyGroup)
    bpy.types.WindowManager.render_current_frame = bpy.props.BoolProperty(
        name="Render Current Frame Only",
        description="Only render the current frame from the active scene",
        default=False
    )
    
    bpy.types.WindowManager.create_mp4 = bpy.props.BoolProperty(
        name="Also Create MP4",
        description="Create an MP4 movie from rendered frames using Deadline Draft",
        default=False
    )
        
    bpy.types.WindowManager.job_priority = bpy.props.IntProperty(
        name="Job Priority",
        description="Priority of the job in Deadline",
        default=50,
        min=1,
        max=100
    )

    bpy.types.WindowManager.chunk_size = bpy.props.IntProperty(
        name="Chunk Size",
        description="Number of frames to render per task",
        default=25,
        min=1
    )

    bpy.types.Scene.override_frame_range = bpy.props.BoolProperty(
        name="Override Frame Range",
        description="Use the custom frame range instead of the scene's frame range",
        default=False
    )

    bpy.types.Scene.override_frame_start = bpy.props.IntProperty(
        name="Start Frame",
        description="Custom start frame",
        default=1
    )

    bpy.types.Scene.override_frame_end = bpy.props.IntProperty(
        name="End Frame",
        description="Custom end frame",
        default=250
    )

    bpy.types.Scene.custom_frame_list_enabled = bpy.props.BoolProperty(
        name="Custom Frame List",
        description="Use a custom comma-separated list of frames to render",
        default=False
    )

    bpy.types.Scene.custom_frame_list = bpy.props.StringProperty(
        name="Frame List",
        description="Comma-separated list of frames to render (e.g., 1,5,10-15,20)",
        default=""
    )

    # Create a function to get pool items dynamically with caching
    def get_pool_items(self, context):
        try:
            available_pools = get_cached_deadline_pools()
            if available_pools and available_pools != ["blendergpu"]:  # Don't use fallback as real pools
                return [(pool, pool, pool) for pool in available_pools]
            else:
                return [("blendergpu", "blendergpu", "Default pool")]
        except:
            return [("blendergpu", "blendergpu", "Default pool")]

    # Calculate default index - find first pool that's not "none", but only if cache exists
    def get_default_pool_index():
        try:
            # Only check cache, don't trigger server call during registration
            cached_pools = load_pools_from_cache()
            if cached_pools:
                for i, pool in enumerate(cached_pools):
                    if pool.lower() != 'none':
                        print(f"DEBUG: Setting default pool index to {i} (pool: {pool})")
                        return i
            return 0  # Fallback to first pool
        except:
            return 0

    try:
        bpy.types.WindowManager.deadline_pool = bpy.props.EnumProperty(
            name="Render Pool",
            description="Deadline pool to submit job to",
            items=get_pool_items,
            default=get_default_pool_index()  # Only uses cache, no server call
        )
        print("DEBUG: Successfully registered deadline_pool property")
    except Exception as e:
        print(f"DEBUG: Failed to register deadline_pool: {e}")

    try:
        bpy.types.WindowManager.submit_suspended = bpy.props.BoolProperty(
            name="Submit Job as Suspended",
            description="Submit the job in suspended state (won't start rendering until resumed)",
            default=False
        )
        print("DEBUG: Successfully registered submit_suspended property")
    except Exception as e:
        print(f"DEBUG: Failed to register submit_suspended: {e}")

    try:
        bpy.types.WindowManager.submit_scene_file = bpy.props.BoolProperty(
            name="Submit Blender Scene with Job",
            description="Copy the Blender scene file to the repository and submit it with the job",
            default=False
        )
        print("DEBUG: Successfully registered submit_scene_file property")
    except Exception as e:
        print(f"DEBUG: Failed to register submit_scene_file: {e}")

    try:
        bpy.types.WindowManager.render_all_cameras = bpy.props.BoolProperty(
            name="Render All Selected Cameras",
            description="Render from all selected cameras, creating separate jobs for each camera view",
            default=False
        )
        print("DEBUG: Successfully registered render_all_cameras property")
    except Exception as e:
        print(f"DEBUG: Failed to register render_all_cameras: {e}")

    try:
        bpy.types.WindowManager.split_still_frame = bpy.props.BoolProperty(
            name="Split Still Frame",
            description="Split a single frame render across multiple machines using sample subsets",
            default=False
        )
        print("DEBUG: Successfully registered split_still_frame property")
    except Exception as e:
        print(f"DEBUG: Failed to register split_still_frame: {e}")

    try:
        bpy.types.WindowManager.split_frame_jobs = bpy.props.IntProperty(
            name="Split Jobs",
            description="Number of jobs to split the frame rendering into",
            default=2,
            min=2,
            max=999  # Allow any reasonable number, with warnings for poor sample distribution
        )
        print("DEBUG: Successfully registered split_frame_jobs property")
    except Exception as e:
        print(f"DEBUG: Failed to register split_frame_jobs: {e}")
    
    # Clear any existing items
    bpy.context.scene.LocalFolders.clear()
    bpy.context.scene.NetworkFolders.clear()

    for folder in load_folder_history("local"):
        item = bpy.context.scene.LocalFolders.add()
        item.name = folder

    for folder in load_folder_history("network"):
        item = bpy.context.scene.NetworkFolders.add()
        item.name = folder

def unregister():
    bpy.utils.unregister_class(SubmitToDeadlineOperator)
    bpy.utils.unregister_class(PROPERTIES_PT_DeadlineScenesToRenderSubPanel)
    bpy.utils.unregister_class(PROPERTIES_PT_DeadlineSubmissionOptionsSubPanel)
    bpy.utils.unregister_class(DeadlineSubmissionPanel)
    bpy.utils.unregister_class(BrowseLocalFolder)
    bpy.utils.unregister_class(BrowseNetworkFolder)
    bpy.utils.unregister_class(SCENE_UL_ScenesList)
    bpy.utils.unregister_class(UpdatePoolsOperator)
    bpy.utils.unregister_class(DeleteFolderHistory)
    bpy.utils.unregister_class(SyncFilesOperator)
    bpy.utils.unregister_class(LocalizeReferencesOperator)
    bpy.utils.unregister_class(DuplicateFilesPopupOK)
    bpy.utils.unregister_class(DuplicateFilesPopupCancel)
    bpy.utils.unregister_class(DuplicateFilesPopup)

    bpy.utils.unregister_class(GetFilesFromNetworkOperator)
    
    del bpy.types.WindowManager.duplicate_files
    bpy.utils.unregister_class(DuplicateFileItem)
    
    del bpy.types.Scene.duplicate_files
    del bpy.types.Scene.duplicate_files_index    
    del bpy.types.WindowManager.render_current_frame
    del bpy.types.WindowManager.create_mp4
    del bpy.types.Scene.override_frame_range
    del bpy.types.Scene.override_frame_start
    del bpy.types.Scene.override_frame_end
    del bpy.types.Scene.custom_frame_list_enabled
    del bpy.types.Scene.custom_frame_list
    del bpy.types.WindowManager.chunk_size
    del bpy.types.WindowManager.job_priority
    del bpy.types.WindowManager.selected_scenes_index
    del bpy.types.WindowManager.deadline_pool
    del bpy.types.WindowManager.submit_suspended
    del bpy.types.WindowManager.submit_scene_file
    del bpy.types.WindowManager.render_all_cameras
    del bpy.types.Scene.local_folder
    del bpy.types.Scene.network_folder
    del bpy.types.Scene.LocalFolders
    del bpy.types.Scene.NetworkFolders
    del bpy.types.Scene.is_selected_for_submission

#if __name__ == "__main__":
register()