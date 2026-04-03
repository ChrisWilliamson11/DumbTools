# Tooltip: Add noise with falloff to selected animation channels in dopesheet/graph editor
import bpy
import bmesh
import random
import math
from bpy.props import FloatProperty, IntProperty, EnumProperty, BoolProperty, PointerProperty
from bpy.types import PropertyGroup

class NoiseAnimationSettings(PropertyGroup):
    """Property group to store noise animation settings"""
    noise_strength: FloatProperty(
        name="Noise Strength",
        description="Maximum amount of noise to add",
        default=1.0,
        min=0.0,
        max=100.0
    )



    start_falloff: IntProperty(
        name="Start Falloff (frames)",
        description="Number of frames to fade in the noise effect",
        default=6,
        min=0,
        max=100
    )

    end_falloff: IntProperty(
        name="End Falloff (frames)",
        description="Number of frames to fade out the noise effect",
        default=6,
        min=0,
        max=100
    )

    frequency: FloatProperty(
        name="Frequency",
        description="How often the noise changes (higher = more chaotic)",
        default=1.0,
        min=0.1,
        max=10.0
    )

    seed: IntProperty(
        name="Random Seed",
        description="Seed for random number generation",
        default=0,
        min=0,
        max=10000
    )

    falloff_type: EnumProperty(
        name="Falloff Type",
        description="Type of falloff curve",
        items=[
            ('LINEAR', "Linear", "Linear falloff"),
            ('SMOOTH', "Smooth", "Smooth falloff"),
            ('SHARP', "Sharp", "Sharp falloff"),
            ('SPHERE', "Sphere", "Spherical falloff"),
        ],
        default='SMOOTH'
    )

class AddNoiseToAnimationChannels(bpy.types.Operator):
    """Add noise with falloff to selected animation channels"""
    bl_idname = "anim.add_noise_to_channels"
    bl_label = "Add Noise to Animation Channels"
    bl_options = {'REGISTER', 'UNDO'}

    # Operator properties (these will be used for the dialog)
    noise_strength: FloatProperty(
        name="Noise Strength",
        description="Maximum amount of noise to add",
        default=1.0,
        min=0.0,
        max=100.0
    )



    start_falloff: IntProperty(
        name="Start Falloff (frames)",
        description="Number of frames to fade in the noise effect",
        default=6,
        min=0,
        max=100
    )

    end_falloff: IntProperty(
        name="End Falloff (frames)",
        description="Number of frames to fade out the noise effect",
        default=6,
        min=0,
        max=100
    )

    frequency: FloatProperty(
        name="Frequency",
        description="How often the noise changes (higher = more chaotic)",
        default=1.0,
        min=0.1,
        max=10.0
    )

    seed: IntProperty(
        name="Random Seed",
        description="Seed for random number generation",
        default=0,
        min=0,
        max=10000
    )

    falloff_type: EnumProperty(
        name="Falloff Type",
        description="Type of falloff curve",
        items=[
            ('LINEAR', "Linear", "Linear falloff"),
            ('SMOOTH', "Smooth", "Smooth falloff"),
            ('SHARP', "Sharp", "Sharp falloff"),
            ('SPHERE', "Sphere", "Spherical falloff"),
        ],
        default='SMOOTH'
    )

    def load_settings(self, context):
        """Load settings from scene properties"""
        # Check if the property exists (it might not on first run)
        if hasattr(context.scene, 'noise_animation_settings'):
            settings = context.scene.noise_animation_settings
            self.noise_strength = settings.noise_strength
            self.start_falloff = settings.start_falloff
            self.end_falloff = settings.end_falloff
            self.frequency = settings.frequency
            self.seed = settings.seed
            self.falloff_type = settings.falloff_type

    def save_settings(self, context):
        """Save settings to scene properties"""
        settings = context.scene.noise_animation_settings
        settings.noise_strength = self.noise_strength
        settings.start_falloff = self.start_falloff
        settings.end_falloff = self.end_falloff
        settings.frequency = self.frequency
        settings.seed = self.seed
        settings.falloff_type = self.falloff_type
    
    def get_selected_fcurves_with_ranges(self, context):
        """Get f-curves that have selected keyframes and their frame ranges"""
        fcurve_data = []

        # Get f-curves from all selected objects with animation data
        objs = [o for o in context.selected_objects if o.animation_data and o.animation_data.action]

        # If no selected objects have animation, try the active object
        if not objs and context.active_object and context.active_object.animation_data and context.active_object.animation_data.action:
            objs = [context.active_object]

        for obj in objs:
            action = obj.animation_data.action
            for fcurve in action.fcurves:
                # Get selected keyframes for this f-curve
                selected_keyframes = [kp for kp in fcurve.keyframe_points if kp.select_control_point]

                if selected_keyframes:
                    # Find the frame range of selected keyframes
                    frames = [kp.co.x for kp in selected_keyframes]
                    start_frame = int(min(frames))
                    end_frame = int(max(frames))

                    fcurve_data.append({
                        'fcurve': fcurve,
                        'start_frame': start_frame,
                        'end_frame': end_frame,
                        'selected_keyframes': selected_keyframes
                    })

                    print(f"Found selected keyframes in: {fcurve.data_path}[{fcurve.array_index}] from frame {start_frame} to {end_frame}")

        return fcurve_data
    
    def calculate_falloff(self, frame, start_frame, end_frame, start_falloff, end_falloff):
        """Calculate falloff multiplier for given frame"""
        total_duration = end_frame - start_frame
        
        # No falloff if duration is too short
        if total_duration <= 0:
            return 1.0
            
        # Calculate position within the effect duration (0.0 to 1.0)
        relative_frame = frame - start_frame
        
        # Start falloff
        if relative_frame < start_falloff:
            if start_falloff == 0:
                falloff_factor = 1.0
            else:
                falloff_factor = relative_frame / start_falloff
        # End falloff
        elif relative_frame > (total_duration - end_falloff):
            if end_falloff == 0:
                falloff_factor = 1.0
            else:
                frames_from_end = total_duration - relative_frame
                falloff_factor = frames_from_end / end_falloff
        # Full strength in the middle
        else:
            falloff_factor = 1.0
        
        # Clamp to 0-1 range
        falloff_factor = max(0.0, min(1.0, falloff_factor))
        
        # Apply falloff curve type
        if self.falloff_type == 'LINEAR':
            return falloff_factor
        elif self.falloff_type == 'SMOOTH':
            return falloff_factor * falloff_factor * (3.0 - 2.0 * falloff_factor)  # Smoothstep
        elif self.falloff_type == 'SHARP':
            return falloff_factor * falloff_factor
        elif self.falloff_type == 'SPHERE':
            return math.sqrt(falloff_factor)
        
        return falloff_factor
    
    def generate_noise(self, frame, frequency, seed):
        """Generate smooth noise value for given frame using interpolated random values"""
        # Create a smooth noise function by interpolating between random values at integer intervals

        # Scale the frame by frequency to control how often the noise changes
        scaled_frame = frame * frequency

        # Get the integer part and fractional part
        base_frame = int(scaled_frame)
        fraction = scaled_frame - base_frame

        # Generate random values at the two nearest integer points
        random.seed(base_frame + seed)
        value1 = random.uniform(-1.0, 1.0)

        random.seed(base_frame + 1 + seed)
        value2 = random.uniform(-1.0, 1.0)

        # Smooth interpolation between the two values (smoothstep)
        smooth_fraction = fraction * fraction * (3.0 - 2.0 * fraction)

        # Linear interpolation would be: value1 + (value2 - value1) * fraction
        # Smooth interpolation for better noise:
        return value1 + (value2 - value1) * smooth_fraction
    
    def execute(self, context):
        # Save settings for next time
        self.save_settings(context)

        fcurve_data = self.get_selected_fcurves_with_ranges(context)

        if not fcurve_data:
            self.report({'WARNING'}, "No keyframes selected in animation channels")
            return {'CANCELLED'}

        total_channels = 0

        # Store original selection state for all keyframes
        original_selection = {}
        for data in fcurve_data:
            fcurve = data['fcurve']
            original_selection[fcurve] = {}
            for kp in fcurve.keyframe_points:
                original_selection[fcurve][kp.co.x] = kp.select_control_point

        # Process each f-curve with its specific frame range
        for data in fcurve_data:
            fcurve = data['fcurve']
            start_frame = data['start_frame']
            end_frame = data['end_frame']

            # Create unique seed for this channel based on its data path and array index
            channel_seed = self.seed + hash(fcurve.data_path + str(fcurve.array_index)) % 10000

            # Step 1: Bake the animation by adding keyframes for every frame in the range
            print(f"Baking {fcurve.data_path}[{fcurve.array_index}] from {start_frame} to {end_frame}")
            for frame in range(start_frame, end_frame + 1):
                # Get the current animated value at this frame
                base_value = fcurve.evaluate(frame)
                # Insert keyframe with the current value (baking the animation)
                fcurve.keyframe_points.insert(frame, base_value)

            # Step 2: Add noise to the baked keyframes (skip first and last frame)
            for frame in range(start_frame + 1, end_frame):
                # Calculate falloff multiplier
                falloff_mult = self.calculate_falloff(
                    frame, start_frame, end_frame,
                    self.start_falloff, self.end_falloff
                )

                # Generate noise for this frame using channel-specific seed
                noise_value = self.generate_noise(frame, self.frequency, channel_seed)

                # Find the keyframe we just created and modify its value
                for kp in fcurve.keyframe_points:
                    if abs(kp.co.x - frame) < 0.001:  # Float comparison tolerance
                        # Apply noise with falloff to the existing value
                        final_noise = noise_value * self.noise_strength * falloff_mult
                        kp.co.y += final_noise
                        break

            # Step 3: Set all keyframes to Auto Clamped (do this last after noise is applied)
            for kp in fcurve.keyframe_points:
                if start_frame <= kp.co.x <= end_frame:
                    kp.interpolation = 'BEZIER'
                    kp.handle_left_type = 'AUTO_CLAMPED'
                    kp.handle_right_type = 'AUTO_CLAMPED'

            total_channels += 1

        # Restore original selection state
        for data in fcurve_data:
            fcurve = data['fcurve']
            for kp in fcurve.keyframe_points:
                frame = kp.co.x
                if fcurve in original_selection and frame in original_selection[fcurve]:
                    kp.select_control_point = original_selection[fcurve][frame]
                else:
                    # New keyframes should not be selected
                    kp.select_control_point = False

        # Update the scene
        context.scene.frame_set(context.scene.frame_current)

        self.report({'INFO'}, f"Added noise to {total_channels} animation channels")
        return {'FINISHED'}
    
    def invoke(self, context, event):
        # Load previous settings
        self.load_settings(context)
        return context.window_manager.invoke_props_dialog(self, width=400)

def register():
    bpy.utils.register_class(NoiseAnimationSettings)
    bpy.utils.register_class(AddNoiseToAnimationChannels)
    bpy.types.Scene.noise_animation_settings = PointerProperty(type=NoiseAnimationSettings)

def unregister():
    bpy.utils.unregister_class(AddNoiseToAnimationChannels)
    bpy.utils.unregister_class(NoiseAnimationSettings)
    del bpy.types.Scene.noise_animation_settings


register()
bpy.ops.anim.add_noise_to_channels('INVOKE_DEFAULT')
