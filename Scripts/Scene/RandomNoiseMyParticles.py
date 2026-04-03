# Tooltip: Randomize turbulence force seeds and bake particle systems for objects in 'Bases' collection

import bpy
import random
import os
from bpy.types import Operator
from bpy.props import BoolProperty

def get_turbulence_forces():
    """Get all selected turbulence force field objects"""
    turbulence_forces = []
    for obj in bpy.context.selected_objects:
        if obj.type == 'EMPTY' and obj.field and obj.field.type == 'TURBULENCE':
            turbulence_forces.append(obj)
    return turbulence_forces

def randomize_turbulence_seeds(turbulence_forces):
    """Randomize the seed values for all turbulence forces - each gets a unique seed"""
    used_seeds = set()

    for force in turbulence_forces:
        # Generate a unique random seed between 0 and 128
        new_seed = random.randint(0, 128)

        # Ensure each force gets a different seed
        while new_seed in used_seeds:
            new_seed = random.randint(0, 128)

        used_seeds.add(new_seed)
        force.field.seed = new_seed
        print(f"Set turbulence force '{force.name}' seed to: {new_seed}")

def get_bases_collection():
    """Get the 'Bases' collection"""
    bases_collection = bpy.data.collections.get('Bases')
    if not bases_collection:
        print("Error: Collection 'Bases' not found!")
        return None
    return bases_collection

def get_objects_with_particle_systems(collection):
    """Get all objects in the collection that have particle systems"""
    objects_with_particles = []
    for obj in collection.objects:
        if obj.particle_systems:
            objects_with_particles.append(obj)
    return objects_with_particles

def set_particle_cache_directories(obj):
    """Set relative cache directories for all particle systems on the object"""
    print(f"Setting cache directories for object: {obj.name}")

    for i, particle_system in enumerate(obj.particle_systems):
        # Create a relative cache path based on object name and particle system index
        cache_dir = f"//cache/{obj.name}_{particle_system.name}"

        # First ensure we're in the right cache mode for baking
        particle_system.point_cache.use_external = False  # Set to internal first
        particle_system.point_cache.filepath = cache_dir  # Set the path

        print(f"  Set cache directory for '{particle_system.name}': {cache_dir}")

        # Also set cache directory for any modifiers that have this particle system
        for modifier in obj.modifiers:
            if hasattr(modifier, 'particle_system') and modifier.particle_system == particle_system:
                if hasattr(modifier.particle_system, 'point_cache'):
                    modifier.particle_system.point_cache.use_external = False
                    modifier.particle_system.point_cache.filepath = cache_dir
                    print(f"    Updated modifier '{modifier.name}' cache path")

def bake_particle_system(obj):
    """Bake all particle systems for the given object"""
    # Set the object as active
    bpy.context.view_layer.objects.active = obj

    # Deselect all objects first
    bpy.ops.object.select_all(action='DESELECT')

    # Select only this object
    obj.select_set(True)

    print(f"Baking particle systems for object: {obj.name}")

    # Set cache directories before baking (this sets them to internal mode)
    set_particle_cache_directories(obj)

    # Force view layer update to ensure context is correct
    bpy.context.view_layer.update()

    # Bake each particle system
    for i, particle_system in enumerate(obj.particle_systems):
        print(f"  Baking particle system {i+1}/{len(obj.particle_systems)}: {particle_system.name}")

        # Set the particle system as active
        obj.particle_systems.active_index = i

        # Force another update after setting active index
        bpy.context.view_layer.update()

        try:
            # Try context override approach first
            with bpy.context.temp_override(active_object=obj, selected_objects=[obj]):
                if bpy.ops.ptcache.bake.poll():
                    # Bake the particle system (while in internal mode)
                    bpy.ops.ptcache.bake(bake=True)
                    print(f"    Successfully baked: {particle_system.name}")

                    # After successful baking, switch to external mode to use the custom path
                    particle_system.point_cache.use_external = True
                    print(f"    Switched to external cache: {particle_system.point_cache.filepath}")
                else:
                    raise Exception("Bake operator poll failed even with context override")

        except Exception as e:
            print(f"    Operator bake failed: {str(e)}")
            # Try frame simulation approach
            try:
                print(f"    Trying frame simulation approach...")
                current_frame = bpy.context.scene.frame_current
                start_frame = bpy.context.scene.frame_start
                end_frame = bpy.context.scene.frame_end

                # Set proper frame range for the cache
                particle_system.point_cache.frame_start = start_frame
                particle_system.point_cache.frame_end = end_frame

                # Step through ALL frames to force proper simulation
                for frame in range(start_frame, end_frame + 1):
                    bpy.context.scene.frame_set(frame)
                    bpy.context.view_layer.update()

                # Restore original frame
                bpy.context.scene.frame_set(current_frame)

                # Switch to external mode
                particle_system.point_cache.use_external = True
                print(f"    Frame simulation completed, switched to external cache")

            except Exception as e2:
                print(f"    All baking methods failed for {particle_system.name}: {str(e2)}")

def main():
    """Main function to execute the randomization and baking process"""
    print("=== Random Noise My Particles ===")

    # Get selected turbulence forces
    turbulence_forces = get_turbulence_forces()
    if not turbulence_forces:
        print("Warning: No turbulence force fields selected!")
        print("Please select turbulence force field objects before running this script.")
        return

    print(f"Found {len(turbulence_forces)} turbulence force(s)")

    # Get the Bases collection
    bases_collection = get_bases_collection()
    if not bases_collection:
        return

    # Get objects with particle systems
    objects_with_particles = get_objects_with_particle_systems(bases_collection)
    if not objects_with_particles:
        print("Warning: No objects with particle systems found in 'Bases' collection!")
        return

    print(f"Found {len(objects_with_particles)} object(s) with particle systems in 'Bases' collection")

    # Process each object
    for i, obj in enumerate(objects_with_particles):
        print(f"\n--- Processing object {i+1}/{len(objects_with_particles)}: {obj.name} ---")

        # Randomize turbulence seeds
        print("Randomizing turbulence force seeds...")
        randomize_turbulence_seeds(turbulence_forces)

        # Force scene update to apply new seeds
        bpy.context.view_layer.update()

        # Bake particle systems for this object
        bake_particle_system(obj)

        print(f"Completed processing: {obj.name}")

    print("\n=== Process Complete ===")
    print(f"Processed {len(objects_with_particles)} objects with randomized turbulence seeds")

def bake_particle_system_internal(obj, context):
    """Bake all particle systems for the given object using internal cache only"""
    # Set the object as active
    context.view_layer.objects.active = obj

    # Deselect all objects first
    bpy.ops.object.select_all(action='DESELECT')

    # Select only this object
    obj.select_set(True)

    print(f"Baking particle systems for object (internal cache): {obj.name}")

    # Bake each particle system
    for i, particle_system in enumerate(obj.particle_systems):
        print(f"  Baking particle system {i+1}/{len(obj.particle_systems)}: {particle_system.name}")

        # Set the particle system as active
        obj.particle_systems.active_index = i

        # Ensure internal cache mode
        particle_system.point_cache.use_external = False

        # Force view layer update
        context.view_layer.update()

        try:
            # Try to bake using the operator with proper context override
            with context.temp_override(active_object=obj, selected_objects=[obj]):
                bpy.ops.ptcache.bake(bake=True)
            print(f"    Successfully baked (internal): {particle_system.name}")

        except Exception as e:
            print(f"    Operator bake failed: {str(e)}")
            # Fallback: Force simulation by stepping through frames
            try:
                print(f"    Trying simulation fallback...")
                current_frame = context.scene.frame_current
                start_frame = context.scene.frame_start
                end_frame = context.scene.frame_end

                # Set proper frame range for the cache
                particle_system.point_cache.frame_start = start_frame
                particle_system.point_cache.frame_end = end_frame

                # Step through ALL frames to force proper simulation
                for frame in range(start_frame, end_frame + 1):
                    context.scene.frame_set(frame)
                    context.view_layer.update()

                # Restore original frame
                context.scene.frame_set(current_frame)
                print(f"    Simulation fallback completed: {particle_system.name}")

            except Exception as e2:
                print(f"    All methods failed for {particle_system.name}: {str(e2)}")

class PARTICLE_OT_RandomNoiseMyParticles(Operator):
    """Randomize turbulence force seeds and bake particle systems for objects in 'Bases' collection"""
    bl_idname = "particle.random_noise_my_particles"
    bl_label = "Random Noise My Particles"
    bl_options = {'REGISTER', 'UNDO'}

    use_internal_cache: BoolProperty(
        name="Use Internal Cache",
        description="Use internal cache instead of external cache directories",
        default=False
    )

    def execute(self, context):
        print("=== OPERATOR EXECUTE CALLED ===")
        print("=== Random Noise My Particles ===")

        # Get selected turbulence forces
        turbulence_forces = get_turbulence_forces()
        print(f"DEBUG: Found {len(turbulence_forces)} turbulence forces")
        if not turbulence_forces:
            print("DEBUG: No turbulence forces found")
            self.report({'WARNING'}, "No turbulence force fields selected! Please select turbulence force field objects.")
            return {'CANCELLED'}

        print(f"Found {len(turbulence_forces)} turbulence force(s)")

        # Get the Bases collection
        bases_collection = get_bases_collection()
        print(f"DEBUG: Bases collection: {bases_collection}")
        if not bases_collection:
            print("DEBUG: Bases collection not found")
            self.report({'ERROR'}, "Collection 'Bases' not found!")
            return {'CANCELLED'}

        # Get objects with particle systems
        objects_with_particles = get_objects_with_particle_systems(bases_collection)
        print(f"DEBUG: Found {len(objects_with_particles)} objects with particles")
        if not objects_with_particles:
            print("DEBUG: No objects with particle systems found")
            self.report({'WARNING'}, "No objects with particle systems found in 'Bases' collection!")
            return {'CANCELLED'}

        print(f"Found {len(objects_with_particles)} object(s) with particle systems in 'Bases' collection")

        # Process each object
        for i, obj in enumerate(objects_with_particles):
            print(f"\n--- Processing object {i+1}/{len(objects_with_particles)}: {obj.name} ---")

            # Randomize turbulence seeds
            print("Randomizing turbulence force seeds...")
            randomize_turbulence_seeds(turbulence_forces)

            # Force scene update to apply new seeds
            context.view_layer.update()

            # Bake particle systems for this object
            if self.use_internal_cache:
                print("DEBUG: Using internal cache")
                bake_particle_system_internal(obj, context)
            else:
                print("DEBUG: Using external cache")
                bake_particle_system(obj)

            print(f"Completed processing: {obj.name}")

        print("\n=== Process Complete ===")
        print(f"Processed {len(objects_with_particles)} objects with randomized turbulence seeds")

        self.report({'INFO'}, f"Processed {len(objects_with_particles)} objects with randomized turbulence seeds")
        return {'FINISHED'}

    def invoke(self, context, event):
        return context.window_manager.invoke_props_dialog(self)

def register():
    bpy.utils.register_class(PARTICLE_OT_RandomNoiseMyParticles)

def unregister():
    bpy.utils.unregister_class(PARTICLE_OT_RandomNoiseMyParticles)


def run_directly():
    """Run the main logic directly without operator (for testing)"""
    main()

register()

# Try to show the operator dialog, but handle context issues gracefully
try:
    # Check if we have a proper UI context
    if bpy.context.window_manager:
        print("Running operator with dialog...")
        bpy.ops.particle.random_noise_my_particles('INVOKE_DEFAULT')
    else:
        print("No UI context available. Running directly...")
        run_directly()
except Exception as e:
    print(f"Could not invoke operator dialog: {e}")
    print("Running directly instead...")
    run_directly()
    print("\nAlternative ways to run:")
    print("1. Press F3 and search for 'Random Noise My Particles'")
    print("2. Run: bpy.ops.particle.random_noise_my_particles('INVOKE_DEFAULT')")
    print("3. Run directly: bpy.ops.particle.random_noise_my_particles(use_internal_cache=True)")