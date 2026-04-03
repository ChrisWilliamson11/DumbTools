# Tooltip: Set the render samples for all scenes in the blend file
import bpy

class SetRenderSamples(bpy.types.Operator):
    bl_idname = "render.set_samples_popup"
    bl_label = "Set Render  Samples"
    
    

    samples: bpy.props.IntProperty(name="Render Samples", default=128, min=1)
    denoising: bpy.props.BoolProperty(name="Use Denoising", default=False)
    
    def execute(self, context):

        
        for scene in bpy.data.scenes:

            scene.cycles.samples = self.samples
            scene.cycles.use_denoising = self.denoising
            
        self.report({'INFO'}, f"Samples set to {self.samples} samples.")
        return {'FINISHED'}
    
    def invoke(self, context, event):
        return context.window_manager.invoke_props_dialog(self)

def register():
    bpy.utils.register_class(SetRenderSamples)
    
def unregister():
    bpy.utils.unregister_class(SetRenderSamples)

register()
# Immediately run the operator to show the popup
bpy.ops.render.set_samples_popup('INVOKE_DEFAULT')
