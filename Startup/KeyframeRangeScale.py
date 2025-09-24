import bpy
from bpy.props import FloatProperty
import math

class ANIM_OT_keyframe_range_scaler(bpy.types.Operator):
    """Scale keyframe ranges from first or last selected keyframe"""
    bl_idname = "anim.keyframe_range_scaler"
    bl_label = "Keyframe Range Scaler"
    bl_options = {'REGISTER', 'UNDO'}

    initial_mouse_x: FloatProperty()
    scale_factor: FloatProperty(default=1.0)
    first_frame: FloatProperty()
    last_frame: FloatProperty()
    keyframes: dict = {}
    use_first_as_pivot: bool = True
    has_started: bool = False
    pivot_frame: FloatProperty()
    initial_pivot_distance: FloatProperty()
    handle_frame: FloatProperty()
    initial_relative_pos: FloatProperty()
    original_positions: dict = {}
    original_handles: dict = {}

    @classmethod
    def poll(cls, context):
        return context.area.type in {'DOPESHEET_EDITOR', 'GRAPH_EDITOR', 'TIMELINE'}

    def get_selected_keyframes(self, context):
        keyframes = {}

        # Get the active action based on context
        active_action = None

        if context.area.type == 'DOPESHEET_EDITOR':
            # Handle different modes in dopesheet
            dopesheet = context.space_data
            if dopesheet.mode == 'ACTION':
                # Action Editor mode
                active_action = dopesheet.action
            elif dopesheet.mode == 'DOPESHEET':
                # Standard dopesheet mode
                if context.object and context.object.animation_data:
                    active_action = context.object.animation_data.action
        elif context.area.type == 'GRAPH_EDITOR':
            active_action = context.space_data.action
        elif context.area.type == 'TIMELINE':
            if context.object and context.object.animation_data:
                active_action = context.object.animation_data.action

        # Only process keyframes from the active action
        if active_action:
            for fcurve in active_action.fcurves:
                for keyframe in fcurve.keyframe_points:
                    if keyframe.select_control_point:
                        if fcurve not in keyframes:
                            keyframes[fcurve] = []
                        keyframes[fcurve].append(keyframe)

        return keyframes

    def modal(self, context, event):
        if not self.has_started:  # Wait for initial click
            if event.type == 'LEFTMOUSE' and event.value == 'PRESS':
                # Get the correct region for coordinate conversion
                region = context.region
                view = region.view2d

                # Convert mouse position to frame value, accounting for region size
                mouse_x_frame, _ = view.region_to_view(
                    event.mouse_region_x,  # Use region_x instead of mouse_x
                    event.mouse_region_y   # Use region_y instead of mouse_y
                )

                # Calculate distances to first and last keyframes
                dist_to_first = abs(self.first_frame - mouse_x_frame)
                dist_to_last = abs(self.last_frame - mouse_x_frame)

                # Use the further keyframe as pivot (origin)
                self.use_first_as_pivot = dist_to_last < dist_to_first
                self.pivot_frame = self.first_frame if self.use_first_as_pivot else self.last_frame
                self.handle_frame = self.last_frame if self.use_first_as_pivot else self.first_frame

                # Store the initial relative position
                pivot_to_handle = self.handle_frame - self.pivot_frame
                pivot_to_mouse = mouse_x_frame - self.pivot_frame

                if event.alt and pivot_to_handle != 0:
                    # In alt mode, directly calculate scale to snap handle to mouse
                    self.scale_factor = pivot_to_mouse / pivot_to_handle
                else:
                    # Store relative position for normal mode
                    self.initial_relative_pos = pivot_to_mouse / pivot_to_handle if pivot_to_handle != 0 else 0.0
                    self.scale_factor = 1.0

                self.initial_mouse_x = event.mouse_x
                self.has_started = True

                # Apply initial scaling
                self.apply_scale(context, event)

            elif event.type == 'RIGHTMOUSE':
                self.restore_original_positions(context)
                return {'CANCELLED'}

            return {'RUNNING_MODAL'}

        if event.type == 'MOUSEMOVE':
            # Get the correct region for coordinate conversion
            region = context.region
            view = region.view2d

            # Convert mouse position to frame value, accounting for region size
            current_frame, _ = view.region_to_view(
                event.mouse_region_x,  # Use region_x instead of mouse_x
                event.mouse_region_y   # Use region_y instead of mouse_y
            )

            # Apply shift precision mode
            sensitivity = 0.2 if event.shift else 1.0

            if event.alt:
                # Handle snapping mode
                pivot_to_handle = self.handle_frame - self.pivot_frame
                pivot_to_mouse = current_frame - self.pivot_frame
                if pivot_to_handle != 0:
                    self.scale_factor = pivot_to_mouse / pivot_to_handle
            else:
                # Default: Maintain relative position mode
                pivot_to_handle = self.handle_frame - self.pivot_frame

                # Calculate where the mouse is relative to the pivot
                current_relative_pos = (current_frame - self.pivot_frame) / pivot_to_handle

                # Scale factor is the ratio of current position to initial position
                if self.initial_relative_pos != 0:
                    self.scale_factor = current_relative_pos / self.initial_relative_pos
                    # Apply sensitivity in default mode
                    if sensitivity != 1.0:
                        # Adjust scale factor based on sensitivity
                        delta = (self.scale_factor - 1.0) * sensitivity
                        self.scale_factor = 1.0 + delta

            # Apply scaling to keyframes
            self.apply_scale(context, event)

        elif event.type == 'LEFTMOUSE' and event.value == 'RELEASE':
            context.area.header_text_set(None)
            return {'FINISHED'}

        elif event.type in {'ESC'} or (event.type == 'RIGHTMOUSE' and event.value == 'PRESS'):
            self.restore_original_positions(context)
            context.area.header_text_set(None)
            return {'CANCELLED'}

        return {'RUNNING_MODAL'}

    def invoke(self, context, event):
        if context.area.type not in {'DOPESHEET_EDITOR', 'GRAPH_EDITOR', 'TIMELINE'}:
            return {'CANCELLED'}

        self.keyframes = self.get_selected_keyframes(context)
        if not self.keyframes:
            self.report({'WARNING'}, "No keyframes selected")
            return {'CANCELLED'}

        # Store original positions and determine first/last frames
        self.original_positions = {}
        self.original_handles = {}  # Store original handle positions
        min_frame = float('inf')
        max_frame = float('-inf')

        for fcurve, keyframes in self.keyframes.items():
            for keyframe in keyframes:
                frame = keyframe.co.x
                self.original_positions[keyframe] = frame
                # Store both handle positions
                self.original_handles[keyframe] = (keyframe.handle_left[0], keyframe.handle_right[0])
                min_frame = min(min_frame, frame)
                max_frame = max(max_frame, frame)

        self.first_frame = min_frame
        self.last_frame = max_frame

        # Initialize variables
        self.initial_mouse_x = event.mouse_x
        self.scale_factor = 1.0
        self.has_started = False

        context.window_manager.modal_handler_add(self)
        return {'RUNNING_MODAL'}

    def apply_scale(self, context, event):
        for fcurve, keyframes in self.keyframes.items():
            for keyframe in keyframes:
                original_frame = self.original_positions[keyframe]
                offset = original_frame - self.pivot_frame
                new_frame = self.pivot_frame + (offset * self.scale_factor)

                # Snap to nearest frame if ctrl is held
                if event.ctrl:
                    new_frame = round(new_frame)

                # Get original handle positions
                original_left, original_right = self.original_handles[keyframe]

                # Calculate the distances of handles from their original keyframe
                left_handle_distance = original_left - original_frame
                right_handle_distance = original_right - original_frame

                # Scale these distances by the scale factor
                scaled_left_distance = left_handle_distance * self.scale_factor
                scaled_right_distance = right_handle_distance * self.scale_factor

                # Update keyframe position
                keyframe.co.x = new_frame

                # Apply the scaled distances to the new keyframe position
                keyframe.handle_left[0] = new_frame + scaled_left_distance
                keyframe.handle_right[0] = new_frame + scaled_right_distance

        context.area.header_text_set(f"Scale: {self.scale_factor:.2f}")
        context.scene.frame_current = context.scene.frame_current  # Force update

    def restore_original_positions(self, context):
        for fcurve, keyframes in self.keyframes.items():
            for keyframe in keyframes:
                # Restore keyframe position
                keyframe.co.x = self.original_positions[keyframe]
                # Restore handle positions
                original_left, original_right = self.original_handles[keyframe]
                keyframe.handle_left[0] = original_left
                keyframe.handle_right[0] = original_right
            # Update the FCurve after modifying its keyframes
            fcurve.update()

        context.area.header_text_set(None)
        context.scene.frame_current = context.scene.frame_current  # Force update

def menu_func(self, context):
    self.layout.operator(ANIM_OT_keyframe_range_scaler.bl_idname)

def register():
    # Preemptively unregister to avoid Blender 'registered before' info
    try:
        bpy.utils.unregister_class(ANIM_OT_keyframe_range_scaler)
    except Exception:
        pass

    bpy.utils.register_class(ANIM_OT_keyframe_range_scaler)
    bpy.types.DOPESHEET_MT_key.append(menu_func)
    bpy.types.GRAPH_MT_key.append(menu_func)

def unregister():
    bpy.utils.unregister_class(ANIM_OT_keyframe_range_scaler)
    bpy.types.DOPESHEET_MT_key.remove(menu_func)
    bpy.types.GRAPH_MT_key.remove(menu_func)
register()
