# Tooltip: Set the render resolution for all scenes in the blend file
import bpy

class SetRenderResolution(bpy.types.Operator):
    bl_idname = "render.set_resolution_popup"
    bl_label = "Set Render Resolution"
    
    mode: bpy.props.EnumProperty(
        name="Mode",
        description="Choose between setting resolution directly or by percentage",
        items=[
            ('DIRECT', "Set Resolution Direct", "Set resolution directly by entering dimensions"),
            ('PERCENT', "Percent Mode", "Alter existing resolution by a percentage")
        ],
        default='DIRECT'
    )
    
    x_res: bpy.props.IntProperty(name="X Resolution", default=0)
    y_res: bpy.props.IntProperty(name="Y Resolution", default=0)
    percent: bpy.props.FloatProperty(name="Percent", default=100.0, min=1.0, max=500.0, subtype='PERCENTAGE')
    scale: bpy.props.IntProperty(name="Render Scale", default=100, min=1, max=500)
    
    def execute(self, context):
        scene = context.scene
        
        if self.mode == 'DIRECT':
            final_x = self.x_res
            final_y = self.y_res
        elif self.mode == 'PERCENT':
            final_x = int(scene.render.resolution_x * (self.percent / 100.0))
            final_y = int(scene.render.resolution_y * (self.percent / 100.0))
            self.scale = 100  # Reset scale to 100% when using percent mode
        
        scene.render.resolution_x = final_x
        scene.render.resolution_y = final_y
        scene.render.resolution_percentage = self.scale
            
        self.report({'INFO'}, f"Resolution set to {final_x}x{final_y} with {self.scale}% scale.")
        return {'FINISHED'}
    
    def invoke(self, context, event):
        scene = context.scene
        
        # Populate with current scene settings
        self.x_res = scene.render.resolution_x
        self.y_res = scene.render.resolution_y
        self.scale = scene.render.resolution_percentage
        
        return context.window_manager.invoke_props_dialog(self)
    
    def draw(self, context):
        layout = self.layout
        layout.prop(self, "mode")
        
        if self.mode == 'DIRECT':
            layout.prop(self, "x_res")
            layout.prop(self, "y_res")
            layout.prop(self, "scale")
        elif self.mode == 'PERCENT':
            layout.prop(self, "percent")

def register():
    bpy.utils.register_class(SetRenderResolution)
    
def unregister():
    bpy.utils.unregister_class(SetRenderResolution)


register()
bpy.ops.render.set_resolution_popup('INVOKE_DEFAULT')
