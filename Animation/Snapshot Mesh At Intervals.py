# Tooltip: Create mesh snapshots of the active object at specified frame intervals throughout the animation
import bpy

class OBJECT_OT_snapshot_mesh_at_intervals(bpy.types.Operator):
    bl_idname = "object.snapshot_mesh_at_intervals"
    bl_label = "Snapshot Mesh at Intervals"
    bl_options = {'REGISTER', 'UNDO'}

    interval: bpy.props.IntProperty(
        name="Interval",
        description="Interval between snapshots",
        default=10,
        min=1
    )

    def execute(self, context):
        scene = context.scene
        obj = context.object
        start_frame = scene.frame_start
        end_frame = scene.frame_end
        current_frame = start_frame

        while current_frame <= end_frame:
            # Set the frame and update the context
            scene.frame_set(current_frame)
            bpy.context.view_layer.update()

            # Duplicate the object
            bpy.ops.object.duplicate_move(OBJECT_OT_duplicate={"linked":False, "mode":'TRANSLATION'}, 
                                          TRANSFORM_OT_translate={"value":(0, 0, 0)})
            duplicate = context.selected_objects[-1]  # Get the last selected object, which is the duplicate
            context.view_layer.objects.active = duplicate
            bpy.context.view_layer.update()  # Ensure the context is updated after duplication

            # Apply all modifiers
            for modifier in duplicate.modifiers:
                bpy.ops.object.modifier_apply(modifier=modifier.name)

            # Increment the frame
            current_frame += self.interval

        return {'FINISHED'}

    def invoke(self, context, event):
        return context.window_manager.invoke_props_dialog(self)

def menu_func(self, context):
    self.layout.operator(OBJECT_OT_snapshot_mesh_at_intervals.bl_idname)

def register():
    bpy.utils.register_class(OBJECT_OT_snapshot_mesh_at_intervals)
    bpy.types.VIEW3D_MT_object.append(menu_func)

def unregister():
    bpy.utils.unregister_class(OBJECT_OT_snapshot_mesh_at_intervals)
    bpy.types.VIEW3D_MT_object.remove(menu_func)

register()
bpy.ops.object.snapshot_mesh_at_intervals('INVOKE_DEFAULT')