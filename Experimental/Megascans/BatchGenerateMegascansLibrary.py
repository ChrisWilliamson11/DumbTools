import subprocess
import time
import os
import psutil

def is_process_running(process):
    """Check if process is still running"""
    try:
        return process.poll() is None
    except:
        return False

def kill_blender_processes():
    """Kill any existing Blender processes"""
    for proc in psutil.process_iter():
        try:
            if "blender" in proc.name().lower():
                proc.kill()
        except (psutil.NoSuchProcess, psutil.AccessDenied, psutil.ZombieProcess):
            pass

def run_blender_script():
    """Run Blender in headless mode with our script"""
    blender_path = r"C:\Program Files (x86)\Steam\steamapps\common\Blender\blender.exe"
    script_path = r"J:\DumbTools\DumbTools\Texturing\CreateMegascansLibrary.py"
    
    # Command to run Blender in background mode with our script
    cmd = [
        blender_path,
        "--background",  # Run in headless mode
        "--factory-startup",  # Don't load user preferences
        "--python-exit-code", "1",  # Exit code 1 if Python script fails
        "--disable-autoexec",  # Disable auto-execution of Python scripts
        "--python", script_path
    ]
    
    # Set environment variables to disable GPU
    env = os.environ.copy()
    env["BLENDER_DISABLE_GPU"] = "1"
    
    while True:
        try:
            # Kill any existing Blender processes
            kill_blender_processes()
            time.sleep(2)  # Give it time to clean up
            
            print("\nStarting Blender process...")
            process = subprocess.Popen(
                cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                universal_newlines=True,
                env=env
            )
            
            # Monitor the process
            while is_process_running(process):
                output = process.stdout.readline()
                if output:
                    print(output.strip())
                error = process.stderr.readline()
                if error:
                    print(f"Error: {error.strip()}")
                time.sleep(0.1)
            
            return_code = process.wait()
            print(f"\nBlender process ended with return code: {return_code}")
            
            if return_code == 0:
                print("Script completed successfully!")
                break
            elif return_code == 11:  # Access violation
                print("Memory access violation. Cleaning up and restarting...")
                kill_blender_processes()
                time.sleep(10)  # Give more time for cleanup
            else:
                print(f"Blender exited with code {return_code}. Restarting in 5 seconds...")
                time.sleep(5)
            
        except KeyboardInterrupt:
            print("\nUser interrupted the process. Cleaning up...")
            kill_blender_processes()
            break
        except Exception as e:
            print(f"\nError occurred: {e}")
            print("Restarting in 5 seconds...")
            time.sleep(5)

if __name__ == "__main__":
    run_blender_script()