# Tooltip:  Lets you store an object selecttion, and sub object state (Pose, Edit etc) so that you can immediately switch between objects

import bpy

class OBJECT_OT_store_state(bpy.types.Operator):
    """Store the current object and mode"""
    bl_idname = "object.store_state"
    bl_label = "Store State"
    
    def execute(self, context):
        obj = context.active_object
        mode = obj.mode
        name = obj.name
        # Store the state
        context.scene.mode_switcher_states.add().set_props(name=name, mode=mode)
        return {'FINISHED'}

class ModeSwitcherItem(bpy.types.PropertyGroup):
    name: bpy.props.StringProperty(name="Object Name")
    mode: bpy.props.StringProperty(name="Mode")
    
    def set_props(self, name, mode):
        self.name = name
        self.mode = mode

bpy.utils.register_class(ModeSwitcherItem)
bpy.types.Scene.mode_switcher_states = bpy.props.CollectionProperty(type=ModeSwitcherItem)

class OBJECT_OT_switch_to_stored_state(bpy.types.Operator):
    """Switch to stored object and mode"""
    bl_idname = "object.switch_to_stored_state"
    bl_label = "Switch State"
    
    name: bpy.props.StringProperty()
    mode: bpy.props.StringProperty()
    
    def execute(self, context):
        # Deselect all objects using low-level API
        for obj in bpy.data.objects:
            obj.select_set(False)
        
        # Now select the desired object and set it as the active object
        obj = bpy.data.objects[self.name]
        obj.select_set(True)
        context.view_layer.objects.active = obj

        # Assuming 'self.mode' is a valid mode for the active object,
        # you can now safely switch modes.
        bpy.ops.object.mode_set(mode=self.mode)
        
        return {'FINISHED'}


class VIEW3D_PT_mode_switcher(bpy.types.Panel):
    bl_label = "Mode Switcher"
    bl_idname = "VIEW3D_PT_mode_switcher"
    bl_space_type = 'VIEW_3D'
    bl_region_type = 'UI'
    bl_category = 'Tool'
    
    def draw(self, context):
        layout = self.layout
        layout.operator(OBJECT_OT_store_state.bl_idname)
        
        for state in context.scene.mode_switcher_states:
            op = layout.operator(OBJECT_OT_switch_to_stored_state.bl_idname, text=f"{state.name}: {state.mode}")
            op.name = state.name
            op.mode = state.mode

classes = [OBJECT_OT_store_state, OBJECT_OT_switch_to_stored_state, VIEW3D_PT_mode_switcher, ModeSwitcherItem]

def register():
    for cls in classes:
        bpy.utils.register_class(cls)
    bpy.types.Scene.mode_switcher_states = bpy.props.CollectionProperty(type=ModeSwitcherItem)

def unregister():
    for cls in reversed(classes):
        bpy.utils.unregister_class(cls)
    del bpy.types.Scene.mode_switcher_states


register()
