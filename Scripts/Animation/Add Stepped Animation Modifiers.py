# Tooltip: Add stepped animation modifiers to selected animation channels
import bpy
from bpy.props import IntProperty
from bpy.types import Operator

class AddSteppedModifierOperator(Operator):
    """Add stepped interpolation modifier to selected animation channels"""
    bl_idname = "anim.add_stepped_modifiers"
    bl_label = "Add Stepped Modifiers"
    bl_options = {'REGISTER', 'UNDO'}

    step_size: IntProperty(
        name="Step Size",
        description="Number of frames to hold each frame",
        default=2,
        min=1,
        max=100
    )

    @classmethod
    def poll(cls, context):
        return True

    def get_selected_fcurves(self, context):
        """Get selected f-curves"""
        # Try context first (works in Graph Editor and Dopesheet)
        if hasattr(context, "selected_editable_fcurves") and context.selected_editable_fcurves:
            return list(context.selected_editable_fcurves)
            
        if hasattr(context, "selected_visible_fcurves") and context.selected_visible_fcurves:
            return [fc for fc in context.selected_visible_fcurves if fc.select]
            
        # Fallback to finding them manually from objects
        fcurves = []
        objs = [o for o in context.selected_objects if o.animation_data and o.animation_data.action]
        if not objs and context.active_object and context.active_object.animation_data and context.active_object.animation_data.action:
            objs = [context.active_object]

        for obj in objs:
            anim_data = obj.animation_data
            action = anim_data.action
            
            # Legacy Blender (< 4.3)
            if hasattr(action, "fcurves"):
                for fcurve in action.fcurves:
                    if fcurve.select:
                        fcurves.append(fcurve)
            # Modern Blender (4.3+) with Project Baklava
            else:
                try:
                    import bpy_extras
                    slot = getattr(anim_data, "action_slot", None)
                    if slot is not None and hasattr(bpy_extras, "anim_utils") and hasattr(bpy_extras.anim_utils, "action_get_channelbag_for_slot"):
                        channelbag = bpy_extras.anim_utils.action_get_channelbag_for_slot(action, slot)
                        if channelbag and hasattr(channelbag, "fcurves"):
                            for fcurve in channelbag.fcurves:
                                if fcurve.select:
                                    fcurves.append(fcurve)
                except Exception as e:
                    print(f"Error accessing slotted action fcurves: {e}")
                    
        return fcurves

    def execute(self, context):
        fcurves = self.get_selected_fcurves(context)

        if not fcurves:
            self.report({'WARNING'}, "No animation channels selected")
            return {'CANCELLED'}

        added_count = 0
        for fcurve in fcurves:
            # Check if there's already a STEPPED modifier to avoid duplicates?
            # Or just add a new one? The user asked to "add a stepped interpolation modifier"
            # We'll just add it.
            mod = fcurve.modifiers.new(type='STEPPED')
            mod.step_size = self.step_size
            added_count += 1

        # Update the scene
        context.scene.frame_set(context.scene.frame_current)

        self.report({'INFO'}, f"Added stepped modifier to {added_count} animation channels")
        return {'FINISHED'}

    def invoke(self, context, event):
        return context.window_manager.invoke_props_dialog(self, width=300)


def register():
    try:
        bpy.utils.unregister_class(AddSteppedModifierOperator)
    except Exception:
        pass
    bpy.utils.register_class(AddSteppedModifierOperator)


def unregister():
    bpy.utils.unregister_class(AddSteppedModifierOperator)



register()
bpy.ops.anim.add_stepped_modifiers('INVOKE_DEFAULT')
