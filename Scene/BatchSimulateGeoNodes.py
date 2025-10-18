# Tooltip: Batch simulate geometry nodes modifiers in Particles collection across multiple blend files

import bpy
import os
import glob
from bpy.types import Operator
from bpy.props import StringProperty, BoolProperty

def get_particles_collection():
    """Get the 'Particles' collection"""
    particles_collection = bpy.data.collections.get('Particles')
    if not particles_collection:
        print("Error: Collection 'Particles' not found!")
        return None
    return particles_collection

def get_objects_with_geo_nodes(collection):
    """Get all objects in the collection that have geometry nodes modifiers"""
    objects_with_geo_nodes = []
    for obj in collection.objects:
        for modifier in obj.modifiers:
            if modifier.type == 'NODES' and modifier.node_group:
                objects_with_geo_nodes.append(obj)
                break
    return objects_with_geo_nodes

def simulate_geometry_nodes(obj):
    """Bake geometry nodes simulation cache to disk"""
    print(f"  Baking geometry nodes for: {obj.name}")

    scene = bpy.context.scene
    # Use custom frame range 0-500
    start_frame = 0
    end_frame = 500

    # Find geometry nodes modifiers
    geo_modifiers = [mod for mod in obj.modifiers if mod.type == 'NODES' and mod.node_group]

    if not geo_modifiers:
        print(f"    No geometry nodes modifiers found on {obj.name}")
        return False

    print(f"    Found {len(geo_modifiers)} geometry nodes modifier(s)")

    # Create unique cache directory based on blend file name AND object name
    blend_filepath = bpy.data.filepath
    if blend_filepath:
        blend_name = os.path.splitext(os.path.basename(blend_filepath))[0]
        # Include object name to make it unique per object
        cache_dir = f"//cache_{blend_name}/{obj.name}"
    else:
        cache_dir = f"//cache/{obj.name}"

    print(f"    Cache directory: {cache_dir}")
    print(f"    Frame range: {start_frame}-{end_frame}")

    success_count = 0
    for mod in geo_modifiers:
        try:
            # Check if the modifier has bakes (simulation zones)
            if len(mod.bakes) == 0:
                print(f"    Modifier '{mod.name}' has no simulation zones to bake")
                continue

            # Set bake directory at modifier level
            mod.bake_directory = cache_dir
            mod.bake_target = 'DISK'  # Save to disk instead of packing in blend file

            # Configure each bake (simulation zone) - these are the actual simulation nodes
            for bake in mod.bakes:
                # Enable custom path for this bake
                bake.use_custom_path = True
                bake.directory = cache_dir

                # Set bake target to disk
                bake.bake_target = 'DISK'

                # Enable custom frame range
                bake.use_custom_simulation_frame_range = True
                bake.frame_start = start_frame
                bake.frame_end = end_frame

                # Set bake mode to animation
                bake.bake_mode = 'ANIMATION'

                print(f"      Configured bake ID {bake.bake_id}:")
                print(f"        - Directory: {cache_dir}")
                print(f"        - Target: DISK")
                print(f"        - Custom path: True")
                print(f"        - Frame range: {start_frame}-{end_frame}")

            # Make object active and selected for bake operator
            bpy.context.view_layer.objects.active = obj
            bpy.ops.object.select_all(action='DESELECT')
            obj.select_set(True)

            # Try to use the bake operator with context override
            print(f"      Attempting to bake modifier '{mod.name}' using operator...")
            try:
                # Create a context override for the operator
                with bpy.context.temp_override(object=obj, active_object=obj, selected_objects=[obj]):
                    bpy.ops.object.simulation_nodes_cache_bake(selected=False)
                print(f"      ✓ Successfully baked cache to disk!")
                success_count += 1
            except Exception as op_error:
                print(f"      ✗ FAILED TO BAKE CACHE: {str(op_error)}")
                print(f"      ERROR: Cannot create cache file - this object will not render correctly!")
                # Don't increment success_count - this is a failure

        except Exception as e:
            print(f"      ✗ ERROR configuring modifier '{mod.name}': {str(e)}")

    if success_count > 0:
        print(f"    Successfully baked {success_count}/{len(geo_modifiers)} modifier(s)")
        return True
    else:
        print(f"    Failed to bake any modifiers")
        return False

def process_blend_file(filepath):
    """Process a single blend file - open, simulate, save"""
    print(f"\n=== Processing: {os.path.basename(filepath)} ===")
    
    try:
        # Open the blend file
        bpy.ops.wm.open_mainfile(filepath=filepath)
        print(f"Opened: {filepath}")
        
        # Get the Particles collection
        particles_collection = get_particles_collection()
        if not particles_collection:
            print("No 'Particles' collection found, skipping file")
            return False
        
        # Get objects with geometry nodes
        particle_objects = get_objects_with_geo_nodes(particles_collection)
        if not particle_objects:
            print("No objects with geometry nodes found in 'Particles' collection, skipping file")
            return False
        
        print(f"Found {len(particle_objects)} objects with geometry nodes to simulate")
        
        # Simulate each object
        success_count = 0
        for i, obj in enumerate(particle_objects):
            print(f"Processing object {i+1}/{len(particle_objects)}: {obj.name}")
            if simulate_geometry_nodes(obj):
                success_count += 1
        
        print(f"Successfully simulated {success_count}/{len(particle_objects)} objects")
        
        # Save the file
        bpy.ops.wm.save_mainfile()
        print(f"Saved: {filepath}")
        
        return True
        
    except Exception as e:
        print(f"Error processing {filepath}: {str(e)}")
        return False

class SCENE_OT_BatchSimulateGeoNodes(Operator):
    """Batch simulate geometry nodes modifiers across multiple blend files"""
    bl_idname = "scene.batch_simulate_geo_nodes"
    bl_label = "Batch Simulate Geo Nodes"
    bl_options = {'REGISTER', 'UNDO'}
    
    directory: StringProperty(
        name="Directory",
        description="Directory containing blend files to process",
        default="",
        subtype='DIR_PATH'
    )
    
    file_pattern: StringProperty(
        name="File Pattern",
        description="Pattern to match blend files (e.g., '*_seed_*.blend')",
        default="*.blend"
    )
    
    backup_files: BoolProperty(
        name="Create Backups",
        description="Create backup copies before processing",
        default=True
    )

    def execute(self, context):
        print("=== Batch Simulate Geometry Nodes ===")
        
        if not self.directory:
            self.report({'ERROR'}, "Please select a directory!")
            return {'CANCELLED'}
        
        if not os.path.exists(self.directory):
            self.report({'ERROR'}, f"Directory does not exist: {self.directory}")
            return {'CANCELLED'}
        
        # Find blend files matching the pattern
        search_pattern = os.path.join(self.directory, self.file_pattern)
        blend_files = glob.glob(search_pattern)
        
        if not blend_files:
            self.report({'WARNING'}, f"No blend files found matching pattern: {self.file_pattern}")
            return {'CANCELLED'}
        
        print(f"Found {len(blend_files)} blend files to process")
        print(f"Directory: {self.directory}")
        print(f"Pattern: {self.file_pattern}")
        
        # Store current file to restore later
        current_file = bpy.data.filepath
        
        # Process each file
        processed_count = 0
        failed_files = []
        
        for i, filepath in enumerate(blend_files):
            print(f"\n--- File {i+1}/{len(blend_files)} ---")
            
            # Create backup if requested
            if self.backup_files:
                backup_path = filepath + ".backup"
                try:
                    import shutil
                    shutil.copy2(filepath, backup_path)
                    print(f"Created backup: {backup_path}")
                except Exception as e:
                    print(f"Warning: Could not create backup for {filepath}: {e}")
            
            # Process the file
            if process_blend_file(filepath):
                processed_count += 1
            else:
                failed_files.append(os.path.basename(filepath))
        
        # Restore original file if it existed
        if current_file:
            try:
                bpy.ops.wm.open_mainfile(filepath=current_file)
                print(f"\nRestored original file: {current_file}")
            except:
                print(f"\nCould not restore original file: {current_file}")
        
        # Report results
        print(f"\n=== Batch Processing Complete ===")
        print(f"Processed: {processed_count}/{len(blend_files)} files")
        
        if failed_files:
            print(f"Failed files: {', '.join(failed_files)}")
            self.report({'WARNING'}, f"Processed {processed_count}/{len(blend_files)} files. {len(failed_files)} failed.")
        else:
            self.report({'INFO'}, f"Successfully processed all {processed_count} files!")
        
        return {'FINISHED'}

    def invoke(self, context, event):
        # Set default directory to current blend file's directory
        if bpy.data.filepath:
            self.directory = os.path.dirname(bpy.data.filepath)
        
        context.window_manager.fileselect_add(self)
        return {'RUNNING_MODAL'}

def register():
    bpy.utils.register_class(SCENE_OT_BatchSimulateGeoNodes)

def unregister():
    bpy.utils.unregister_class(SCENE_OT_BatchSimulateGeoNodes)


register()
# Show the file browser
try:
    if bpy.context.window_manager:
        bpy.ops.scene.batch_simulate_geo_nodes('INVOKE_DEFAULT')
    else:
        print("No UI context available. Use F3 search menu and type 'Batch Simulate Geo Nodes' to run the operator.")
except Exception as e:
    print(f"Could not invoke operator: {e}")
    print("Alternative ways to run:")
    print("1. Press F3 and search for 'Batch Simulate Geo Nodes'")
    print("2. Run: bpy.ops.scene.batch_simulate_geo_nodes('INVOKE_DEFAULT')")
