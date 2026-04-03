import bpy

def is_local_view(space):
    # This function checks if the 3D view is in local view
    return space.local_view is not None

class TOGGLE_OT_isolate_with_lights(bpy.types.Operator):
    """Toggle Isolation Mode With Lights"""
    bl_idname = "view3d.toggle_isolate_with_lights"
    bl_label = ""
    bl_description = "Toggle Isolation Mode With Lights"

    def execute(self, context):
        # Check if we are in local view (isolate mode)
        if is_local_view(context.space_data):
            # If in local view, return to global view
            bpy.ops.view3d.localview(frame_selected=False)
        else:
            # Make sure all lights are visible before entering local view
            for obj in context.visible_objects:
                if obj.type == "LIGHT":
                    obj.select_set(True)  # Select all lights to keep them visible
            # If in global view, enter local view
            bpy.ops.view3d.localview(frame_selected=False)
            # Deselect lights after entering local view
            for obj in context.visible_objects:
                if obj.type == "LIGHT":
                    obj.select_set(False)
        return {'FINISHED'}


# Function to draw the button in the UI
def draw_button(self, context):
    # Check the local view state and set the icon accordingly
    icon = 'RADIOBUT_ON' if is_local_view(context.space_data) else 'RADIOBUT_OFF'
    self.layout.operator(
        TOGGLE_OT_isolate_with_lights.bl_idname,
        text="",
        icon=icon)

# Registration
def register():
    bpy.utils.register_class(TOGGLE_OT_isolate_with_lights)
    bpy.types.VIEW3D_HT_header.append(draw_button)

def unregister():
    if TOGGLE_OT_isolate_with_lights.is_registered:
        bpy.utils.unregister_class(TOGGLE_OT_isolate_with_lights)
    bpy.types.VIEW3D_HT_header.remove(draw_button)

register()
