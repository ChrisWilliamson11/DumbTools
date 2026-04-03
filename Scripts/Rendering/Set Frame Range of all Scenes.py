# Tooltip: Set the frame range of all scenes in the blend file
import bpy
from bpy.props import IntProperty
from bpy.types import Operator

class SetFrameRangeOperator(Operator):
    bl_idname = "wm.set_frame_range"
    bl_label = "Set Frame Range"
# Tooltip: Set the frame range of all scenes in the blend file
    start_frame: IntProperty(name="Start Frame", default=1)
    end_frame: IntProperty(name="End Frame", default=250)
    
    def execute(self, context):
        for scene in bpy.data.scenes:
            scene.frame_start = self.start_frame
            scene.frame_end = self.end_frame
        self.report({'INFO'}, f"Frame range set to {self.start_frame} - {self.end_frame}")
        return {'FINISHED'}
    
    def invoke(self, context, event):
        wm = context.window_manager
        return wm.invoke_props_dialog(self)
        
def register():
    bpy.utils.register_class(SetFrameRangeOperator)

def unregister():
    bpy.utils.unregister_class(SetFrameRangeOperator)

register()
bpy.ops.wm.set_frame_range('INVOKE_DEFAULT')
