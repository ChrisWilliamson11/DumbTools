# Tooltip: Remove specific modifiers from all selected objects
import bpy

class DUMBTOOLS_PG_ModifierItem(bpy.types.PropertyGroup):
    mod_name: bpy.props.StringProperty()
    mod_type: bpy.props.StringProperty()
    remove: bpy.props.BoolProperty(
        name="",
        description="Remove this modifier",
        default=False
    )

class DUMBTOOLS_OT_remove_modifiers(bpy.types.Operator):
    bl_idname = "scene.remove_modifiers_dialog"
    bl_label = "Delete Modifiers"
    bl_options = {'REGISTER', 'UNDO'}

    modifier_list: bpy.props.CollectionProperty(type=DUMBTOOLS_PG_ModifierItem)

    def invoke(self, context, event):
        self.modifier_list.clear()

        # Collect unique modifiers from selected objects
        mod_dict = {}
        for obj in context.selected_objects:
            if hasattr(obj, "modifiers"):
                for mod in obj.modifiers:
                    key = (mod.name, mod.type)
                    if key not in mod_dict:
                        mod_dict[key] = True

        if not mod_dict:
            self.report({'WARNING'}, "No modifiers found on selected objects")
            return {'CANCELLED'}

        for (name, mtype) in sorted(mod_dict.keys(), key=lambda x: x[0].lower()):
            item = self.modifier_list.add()
            item.mod_name = name
            item.mod_type = mtype
            item.remove = False

        return context.window_manager.invoke_props_dialog(self, width=400)

    def draw(self, context):
        layout = self.layout
        layout.label(text="Select modifiers to remove:")
        
        box = layout.box()
        if not self.modifier_list:
            box.label(text="No modifiers found.")
        
        for item in self.modifier_list:
            row = box.row()
            # To make it look nice, display Name (Type)
            display_text = f"{item.mod_name} ({item.mod_type.title().replace('_', ' ')})"
            row.prop(item, "remove", text=display_text)

    def execute(self, context):
        mods_to_remove = set()
        for item in self.modifier_list:
            if item.remove:
                mods_to_remove.add((item.mod_name, item.mod_type))

        if not mods_to_remove:
            self.report({'INFO'}, "No modifiers selected to remove")
            return {'CANCELLED'}

        count = 0
        for obj in context.selected_objects:
            if hasattr(obj, "modifiers"):
                for mod in list(obj.modifiers):
                    if (mod.name, mod.type) in mods_to_remove:
                        obj.modifiers.remove(mod)
                        count += 1

        self.report({'INFO'}, f"Removed {count} modifiers")
        return {'FINISHED'}

classes = (
    DUMBTOOLS_PG_ModifierItem,
    DUMBTOOLS_OT_remove_modifiers,
)

def register():
    for cls in classes:
        try:
            bpy.utils.register_class(cls)
        except ValueError:
            bpy.utils.unregister_class(cls)
            bpy.utils.register_class(cls)

def unregister():
    for cls in reversed(classes):
        try:
            bpy.utils.unregister_class(cls)
        except RuntimeError:
            pass

register()
bpy.ops.scene.remove_modifiers_dialog('INVOKE_DEFAULT')
