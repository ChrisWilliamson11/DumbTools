#adds a menu entry to the compositor to auto fit the image. when it is enabled, it tracks the size of the compositing window, any changes and it runs the fit to availabel space operation.

import bpy
from bpy.app.handlers import persistent

# Store addon state globally since operators don't maintain state between calls
class AutoFitProperties(bpy.types.PropertyGroup):
    is_enabled: bpy.props.BoolProperty(default=False)
    debug_mode: bpy.props.BoolProperty(default=True, description="Print debug messages to console")

# Module-level variables to store references
auto_fit_timer = None
area_dimensions = {}

# This is a modal operator that will run and monitor area resizing
class COMPOSITOR_OT_auto_fit_modal(bpy.types.Operator):
    """Modal operator to monitor and auto-fit the compositor view"""
    bl_idname = "node.auto_fit_view_modal"
    bl_label = "Auto Fit View Monitor"
    
    _timer = None
    
    def modal(self, context, event):
        props = context.scene.auto_fit_props
        
        # Exit if disabled
        if not props.is_enabled:
            self.cancel(context)
            return {'CANCELLED'}
            
        # Process timer events
        if event.type == 'TIMER':
            # Check for resize events
            self.check_area_resize(context)
            
        return {'PASS_THROUGH'}
    
    def check_area_resize(self, context):
        """Check if any node editor area has been resized and fit the view if needed"""
        global area_dimensions
        debug = context.scene.auto_fit_props.debug_mode
        
        if debug:
            pass
            #   print("Checking for area resizes...")
            
        # Check all node editor areas for size changes
        for window in context.window_manager.windows:
            for area in window.screen.areas:
                if area.type == 'NODE_EDITOR' and hasattr(area.spaces.active, 'tree_type') and area.spaces.active.tree_type == 'CompositorNodeTree':
                    # Get current dimensions
                    current_dims = (area.width, area.height)
                    area_key = f"{window.as_pointer()}_{area.as_pointer()}"
                    
                    # Check if we have stored dimensions for this area
                    if area_key in area_dimensions:
                        # If dimensions changed, fit the view
                        if current_dims != area_dimensions[area_key]:
                            if debug:
                                print(f"Area {area_key} RESIZED from {area_dimensions[area_key]} to {current_dims}")
                            
                            # Use a direct approach to fit view with proper context
                            self.fit_view_directly(context, window, area)
                    else:
                        if debug:
                            print(f"New area discovered: {area_key} with dimensions {current_dims}")
                            self.fit_view_directly(context, window, area)
                    
                    # Update stored dimensions
                    area_dimensions[area_key] = current_dims
    
    def fit_view_directly(self, context, window, area):
        """Directly fit view with proper context by calling the operator at the right time"""
        debug = context.scene.auto_fit_props.debug_mode
        
        if debug:
            print(f"Fitting view for area {area.as_pointer()}")
        
        # Create a temporary context override
        temp_context = context.copy()
        temp_context['window'] = window
        temp_context['screen'] = window.screen
        temp_context['area'] = area
        temp_context['region'] = area.regions[0]  # Use the first region
        temp_context['space_data'] = area.spaces.active
        
        # Execute correct operator to fit the background image
        with context.temp_override(**temp_context):
            try:
                # Use the backimage_fit operator which is the correct one for fitting compositor images
                bpy.ops.node.backimage_fit()
                
                if debug:
                    print("View fit completed!")
                
                # Force a redraw of the area
                area.tag_redraw()
            except Exception as e:
                print(f"Error fitting view: {e}")
    
    def execute(self, context):
        props = context.scene.auto_fit_props
        props.is_enabled = True
        
        # Initialize area dimensions dictionary
        global area_dimensions
        area_dimensions = {}
        for window in context.window_manager.windows:
            for area in window.screen.areas:
                if area.type == 'NODE_EDITOR' and hasattr(area.spaces.active, 'tree_type') and area.spaces.active.tree_type == 'CompositorNodeTree':
                    area_key = f"{window.as_pointer()}_{area.as_pointer()}"
                    area_dimensions[area_key] = (area.width, area.height)
                    print(f"Initialized area {area_key} with dimensions {area_dimensions[area_key]}")
                    
                    # Fit view on startup
                    self.fit_view_directly(context, window, area)
        
        # Add the timer
        wm = context.window_manager
        self._timer = wm.event_timer_add(0.1, window=context.window)
        wm.modal_handler_add(self)
        
        print("Auto Fit View Modal Operator STARTED")
        return {'RUNNING_MODAL'}
    
    def cancel(self, context):
        # Remove the timer
        wm = context.window_manager
        if self._timer is not None:
            wm.event_timer_remove(self._timer)
            
        props = context.scene.auto_fit_props
        props.is_enabled = False
        print("Auto Fit View Modal Operator STOPPED")
        return {'CANCELLED'}

class COMPOSITOR_OT_auto_fit(bpy.types.Operator):
    """Auto fit the image to the available space"""
    bl_idname = "node.auto_fit_view_toggle"   
    bl_label = "Auto Fit View"
    bl_options = {'REGISTER'}
    
    @classmethod
    def poll(cls, context):
        return context.space_data.type == 'NODE_EDITOR' and context.space_data.tree_type == 'CompositorNodeTree'
    
    def execute(self, context):
        # Toggle the enabled state
        props = context.scene.auto_fit_props
        current_state = props.is_enabled
        
        print(f"Auto Fit View {'DISABLING' if current_state else 'ENABLING'}")
        
        # Start or stop the modal operator
        if not current_state:
            # Start the modal operator
            bpy.ops.node.auto_fit_view_modal()
        else:
            # Modal operator will detect the props change and cancel itself
            props.is_enabled = False
            
        return {'FINISHED'}

def menu_func(self, context):
    props = context.scene.auto_fit_props
    icon = 'CHECKBOX_HLT' if props.is_enabled else 'CHECKBOX_DEHLT'
    self.layout.operator(COMPOSITOR_OT_auto_fit.bl_idname, icon=icon, text="Auto Fit View")
    # Add debug mode toggle
    self.layout.prop(props, "debug_mode", text="Debug Mode")

def register():
    bpy.utils.register_class(AutoFitProperties)
    bpy.types.Scene.auto_fit_props = bpy.props.PointerProperty(type=AutoFitProperties)
    
    bpy.utils.register_class(COMPOSITOR_OT_auto_fit_modal)
    bpy.utils.register_class(COMPOSITOR_OT_auto_fit)
    
    # Add to the Node Editor's View menu
    bpy.types.NODE_MT_view.append(menu_func)

def unregister():
    # Clean up
    if hasattr(bpy.types, 'NODE_MT_view'):
        bpy.types.NODE_MT_view.remove(menu_func)
    
    try:
        bpy.utils.unregister_class(COMPOSITOR_OT_auto_fit)
        bpy.utils.unregister_class(COMPOSITOR_OT_auto_fit_modal)
    except:
        pass
    
    # Clean up properties
    if hasattr(bpy.types.Scene, 'auto_fit_props'):
        del bpy.types.Scene.auto_fit_props
        try:
            bpy.utils.unregister_class(AutoFitProperties)
        except:
            pass

# Don't use if __name__ == "__main__": here since this might be loaded as an addon
register()

