# Tooltip: Force depsgraph updates on selected objects using a modal timer operator

import bpy
from bpy.props import CollectionProperty, StringProperty, FloatProperty, BoolProperty
from bpy.types import Panel, Operator, PropertyGroup
import time

# Property group to store object references
class ForceUpdateObjectItem(PropertyGroup):
    name: StringProperty(name="Object Name", default="")
    enabled: BoolProperty(name="Enabled", default=True)

# Modal operator that runs the timer-based updates
class OBJECT_OT_force_update_modal(Operator):
    """Modal operator to force depsgraph updates on objects"""
    bl_idname = "object.force_update_modal"
    bl_label = "Force Update Modal"
    bl_description = "Start/stop the modal timer for forcing object updates"
    
    _timer = None
    _last_update_time = 0
    
    def modal(self, context, event):
        if event.type == 'TIMER':
            current_time = time.time()
            update_interval = context.scene.force_update_props.update_interval / 1000.0  # Convert ms to seconds
            
            if current_time - self._last_update_time >= update_interval:
                self.force_object_updates(context)
                self._last_update_time = current_time
        
        # Check if we should stop the modal operator
        if not context.scene.force_update_props.is_running:
            return self.cancel(context)
            
        return {'PASS_THROUGH'}
    
    def execute(self, context):
        props = context.scene.force_update_props
        
        if props.is_running:
            # Stop the modal operator
            props.is_running = False
            return {'FINISHED'}
        else:
            # Start the modal operator
            props.is_running = True
            wm = context.window_manager
            self._timer = wm.event_timer_add(0.01, window=context.window)  # 10ms timer resolution
            self._last_update_time = time.time()
            wm.modal_handler_add(self)
            return {'RUNNING_MODAL'}
    
    def cancel(self, context):
        wm = context.window_manager
        if self._timer:
            wm.event_timer_remove(self._timer)
        context.scene.force_update_props.is_running = False
        return {'CANCELLED'}
    
    def force_object_updates(self, context):
        """Force depsgraph updates on the specified objects"""
        props = context.scene.force_update_props
        depsgraph = context.evaluated_depsgraph_get()
        
        updated_count = 0
        for item in props.object_list:
            if item.enabled and item.name in bpy.data.objects:
                obj = bpy.data.objects[item.name]
                # Force update by tagging the object for update
                obj.update_tag()
                updated_count += 1
        
        if updated_count > 0:
            # Force a depsgraph update
            depsgraph.update()
            # Alternative: Full scene update if object-specific doesn't work
            # bpy.context.view_layer.update()

# Operator to add selected objects to the update list
class OBJECT_OT_add_selected_to_update_list(Operator):
    """Add selected objects to the force update list"""
    bl_idname = "object.add_selected_to_update_list"
    bl_label = "Add Selected Objects"
    bl_description = "Add currently selected objects to the update list"
    
    def execute(self, context):
        props = context.scene.force_update_props
        selected_objects = context.selected_objects
        
        if not selected_objects:
            self.report({'WARNING'}, "No objects selected")
            return {'CANCELLED'}
        
        added_count = 0
        for obj in selected_objects:
            # Check if object is already in the list
            if not any(item.name == obj.name for item in props.object_list):
                item = props.object_list.add()
                item.name = obj.name
                item.enabled = True
                added_count += 1
        
        self.report({'INFO'}, f"Added {added_count} objects to update list")
        return {'FINISHED'}

# Operator to clear the update list
class OBJECT_OT_clear_update_list(Operator):
    """Clear all objects from the update list"""
    bl_idname = "object.clear_update_list"
    bl_label = "Clear List"
    bl_description = "Remove all objects from the update list"
    
    def execute(self, context):
        context.scene.force_update_props.object_list.clear()
        return {'FINISHED'}

# Operator to remove a specific object from the list
class OBJECT_OT_remove_from_update_list(Operator):
    """Remove an object from the update list"""
    bl_idname = "object.remove_from_update_list"
    bl_label = "Remove Object"
    bl_description = "Remove this object from the update list"
    
    index: bpy.props.IntProperty()
    
    def execute(self, context):
        props = context.scene.force_update_props
        if 0 <= self.index < len(props.object_list):
            props.object_list.remove(self.index)
        return {'FINISHED'}

# Property group to store all force update settings
class ForceUpdateProperties(PropertyGroup):
    object_list: CollectionProperty(type=ForceUpdateObjectItem)
    update_interval: FloatProperty(
        name="Update Interval (ms)",
        description="Time between forced updates in milliseconds",
        default=50.0,
        min=10.0,
        max=5000.0
    )
    is_running: BoolProperty(
        name="Is Running",
        description="Whether the modal operator is currently running",
        default=False
    )

# Panel in the 3D viewport sidebar
class VIEW3D_PT_force_object_update(Panel):
    """Force Object Update panel in 3D viewport sidebar"""
    bl_label = "Force Object Update"
    bl_idname = "VIEW3D_PT_force_object_update"
    bl_space_type = 'VIEW_3D'
    bl_region_type = 'UI'
    bl_category = "Tool"
    
    def draw(self, context):
        layout = self.layout
        props = context.scene.force_update_props
        
        # Update interval setting
        layout.prop(props, "update_interval")
        
        # Add selected objects button
        layout.operator("object.add_selected_to_update_list", icon='ADD')
        
        # Object list
        if props.object_list:
            box = layout.box()
            box.label(text=f"Objects to Update ({len(props.object_list)}):")
            
            for i, item in enumerate(props.object_list):
                row = box.row()
                row.prop(item, "enabled", text="")
                
                # Show object name, with warning if object doesn't exist
                if item.name in bpy.data.objects:
                    row.label(text=item.name, icon='OBJECT_DATA')
                else:
                    row.label(text=f"{item.name} (Missing!)", icon='ERROR')
                
                # Remove button
                op = row.operator("object.remove_from_update_list", text="", icon='X')
                op.index = i
            
            # Clear all button
            box.operator("object.clear_update_list", icon='TRASH')
        else:
            layout.label(text="No objects in update list", icon='INFO')
        
        # Run/Stop button
        if props.is_running:
            layout.operator("object.force_update_modal", text="Stop Updates", icon='PAUSE')
            layout.label(text="Updates running...", icon='TIME')
        else:
            layout.operator("object.force_update_modal", text="Start Updates", icon='PLAY')

# Registration
classes = [
    ForceUpdateObjectItem,
    ForceUpdateProperties,
    OBJECT_OT_force_update_modal,
    OBJECT_OT_add_selected_to_update_list,
    OBJECT_OT_clear_update_list,
    OBJECT_OT_remove_from_update_list,
    VIEW3D_PT_force_object_update,
]

def register():
    for cls in classes:
        bpy.utils.register_class(cls)
    
    bpy.types.Scene.force_update_props = bpy.props.PointerProperty(type=ForceUpdateProperties)

def unregister():
    for cls in reversed(classes):
        bpy.utils.unregister_class(cls)
    
    if hasattr(bpy.types.Scene, 'force_update_props'):
        del bpy.types.Scene.force_update_props

if __name__ == "__main__":
    register()
