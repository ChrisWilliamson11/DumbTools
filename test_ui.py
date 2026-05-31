import bpy
class TestPanel(bpy.types.Panel):
    bl_label = 'Test Progress'
    bl_space_type = 'VIEW_3D'
    bl_region_type = 'UI'
    bl_category = 'Item'
    def draw(self, context):
        layout = self.layout
        layout.prop(context.scene, 'test_prog', slider=True)
        layout.prop(context.scene, 'test_prog_pct', slider=True)

def register():
    bpy.types.Scene.test_prog = bpy.props.FloatProperty(name='Prog', min=0.0, max=100.0, default=50.0)
    bpy.types.Scene.test_prog_pct = bpy.props.FloatProperty(name='Prog Pct', min=0.0, max=100.0, subtype='PERCENTAGE', default=50.0)
    bpy.utils.register_class(TestPanel)

try: register()
except: pass

