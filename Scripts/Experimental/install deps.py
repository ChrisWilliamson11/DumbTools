# Tooltip: Install required Python dependencies for DumbTools scripts using pip
import bpy
import subprocess
import sys
import os

def run_pip_install():
    # Get Python executable from sys.executable
    python_exe = sys.executable
    
    # Target path for our packages
    target_path = r"J:\DumbTools\DumbTools\Texturing\lib"
    
    # Packages to install
    packages = [
        "cffi",
        "cryptography",
        "pillow",
        "photoshop-connection"
    ]
    
    # Clear target directory
    if os.path.exists(target_path):
        for item in os.listdir(target_path):
            item_path = os.path.join(target_path, item)
            try:
                if os.path.isfile(item_path):
                    os.unlink(item_path)
                else:
                    import shutil
                    shutil.rmtree(item_path)
            except Exception as e:
                print(f'Failed to delete {item_path}. Reason: {e}')
    
    # Install packages
    for package in packages:
        print(f"Installing {package}...")
        try:
            subprocess.check_call([
                python_exe,
                "-m",
                "pip",
                "install",
                f"--target={target_path}",
                package
            ])
            print(f"Successfully installed {package}")
        except subprocess.CalledProcessError as e:
            print(f"Failed to install {package}: {e}")

class InstallDependencies(bpy.types.Operator):
    bl_idname = "script.install_dependencies"
    bl_label = "Install Dependencies"
    
    def execute(self, context):
        run_pip_install()
        return {'FINISHED'}

def register():
    bpy.utils.register_class(InstallDependencies)

def unregister():
    bpy.utils.unregister_class(InstallDependencies)

if __name__ == "__main__":
    register()
    # Run it immediately
    bpy.ops.script.install_dependencies()