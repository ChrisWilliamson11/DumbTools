import bpy
import os
import tempfile
import subprocess
from bpy_extras.io_utils import ImportHelper
from bpy.props import CollectionProperty, StringProperty
from bpy.types import Operator, OperatorFileListElement

class SubmitMultipleBlendFilesOperator(Operator, ImportHelper):
    bl_idname = "scene.submit_multiple_blend_files"
    bl_label = "Submit Multiple Blend Files to Deadline"
    bl_description = "Select multiple blend files and submit all their scenes to Deadline"
    
    # File browser properties
    files: CollectionProperty(
        name="File Path",
        type=OperatorFileListElement,
    )
    
    directory: StringProperty(
        subtype='DIR_PATH',
    )
    
    filter_glob: StringProperty(
        default="*.blend",
        options={'HIDDEN'},
    )
    
    def get_deadline_path(self):
        """Get deadline path from preferences or use default"""
        try:
            prefs = bpy.context.preferences.addons["DumbTools"].preferences
            return getattr(prefs, 'deadline_path', "\\\\wlgsrvrnd\\DeadlineRepository10\\bin\\Windows\\64bit\\deadlinecommand.exe")
        except:
            return "\\\\wlgsrvrnd\\DeadlineRepository10\\bin\\Windows\\64bit\\deadlinecommand.exe"
    
    def submit_blend_file_to_deadline(self, blend_file_path):
        """Submit a single blend file with all its scenes to Deadline"""
        print(f"Processing blend file: {blend_file_path}")
        
        # Create temporary directory for job files
        temp_dir = tempfile.mkdtemp()
        filename = os.path.splitext(os.path.basename(blend_file_path))[0]
        
        # Load the blend file to get scene information
        with bpy.data.libraries.load(blend_file_path) as (data_from, data_to):
            scene_names = data_from.scenes
        
        print(f"Found scenes: {scene_names}")
        
        submitted_jobs = []
        
        for scene_name in scene_names:
            job_info_path = os.path.join(temp_dir, f"job_info_{scene_name}.job")
            plugin_info_path = os.path.join(temp_dir, f"plugin_info_{scene_name}.plugin")
            
            # Write job info
            with open(job_info_path, "w") as f:
                f.write("Plugin=Blender\n")
                f.write(f"Name={filename}_{scene_name}\n")
                f.write("Frames=1-250\n")  # Default frame range - adjust as needed
                f.write("ChunkSize=10\n")
                f.write("Priority=50\n")
                f.write("Pool=blendergpu\n")
            
            # Write plugin info
            with open(plugin_info_path, "w") as f:
                f.write(f"SceneFile={os.path.normpath(blend_file_path)}\n")
                f.write(f"Scene={scene_name}\n")
                f.write("Threads=0\n")
            
            # Submit the job (without sending blend file as auxiliary - assumes network accessible)
            cmd_list = [self.get_deadline_path(), "-SubmitJob", job_info_path, plugin_info_path]
            
            try:
                result = subprocess.run(
                    cmd_list,
                    shell=False,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.PIPE,
                    text=True,
                    timeout=30
                )
                
                if result.returncode == 0:
                    # Extract job ID from output
                    job_id = None
                    for line in result.stdout.splitlines():
                        if "JobID=" in line:
                            job_id = line.split("JobID=")[1].strip()
                            break
                    
                    submitted_jobs.append(f"{filename}_{scene_name} (ID: {job_id})")
                    print(f"Successfully submitted: {filename}_{scene_name}")
                else:
                    print(f"Failed to submit {filename}_{scene_name}: {result.stderr}")
                    
            except Exception as e:
                print(f"Error submitting {filename}_{scene_name}: {e}")
        
        return submitted_jobs
    
    def execute(self, context):
        if not self.files:
            self.report({'ERROR'}, "No files selected")
            return {'CANCELLED'}
        
        all_submitted_jobs = []
        
        # Process each selected blend file
        for file_elem in self.files:
            blend_file_path = os.path.join(self.directory, file_elem.name)
            
            if not os.path.exists(blend_file_path):
                print(f"File not found: {blend_file_path}")
                continue
            
            submitted_jobs = self.submit_blend_file_to_deadline(blend_file_path)
            all_submitted_jobs.extend(submitted_jobs)
        
        if all_submitted_jobs:
            self.report({'INFO'}, f"Successfully submitted {len(all_submitted_jobs)} jobs to Deadline")
            print(f"All submitted jobs: {all_submitted_jobs}")
        else:
            self.report({'ERROR'}, "No jobs were submitted successfully")
        
        return {'FINISHED'}

def register():
    bpy.utils.register_class(SubmitMultipleBlendFilesOperator)

def unregister():
    bpy.utils.unregister_class(SubmitMultipleBlendFilesOperator)


register()
bpy.ops.scene.submit_multiple_blend_files('INVOKE_DEFAULT')