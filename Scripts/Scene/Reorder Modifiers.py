# Tooltip: Reorder modifiers across all selected objects using a unified list
import bpy

class DUMBTOOLS_PG_ModifierItem(bpy.types.PropertyGroup):
    mod_name: bpy.props.StringProperty()
    mod_type: bpy.props.StringProperty()

class DUMBTOOLS_UL_modifier_list(bpy.types.UIList):
    def draw_item(self, context, layout, data, item, icon, active_data, active_propname, index):
        display_text = f"{item.mod_name} ({item.mod_type.title().replace('_', ' ')})"
        layout.label(text=display_text, icon='MODIFIER')

class DUMBTOOLS_OT_reorder_modifier_item(bpy.types.Operator):
    bl_idname = "scene.reorder_modifier_item"
    bl_label = "Move Modifier Item"
    bl_options = {'REGISTER', 'UNDO'}
    
    direction: bpy.props.EnumProperty(
        items=(
            ('UP', "Up", ""),
            ('DOWN', "Down", ""),
        )
    )
    
    def execute(self, context):
        sc = context.scene
        idx = sc.dumbtools_modifier_list_idx
        list_len = len(sc.dumbtools_modifier_list)
        
        if self.direction == 'UP' and idx > 0:
            sc.dumbtools_modifier_list.move(idx, idx - 1)
            sc.dumbtools_modifier_list_idx -= 1
        elif self.direction == 'DOWN' and idx < list_len - 1:
            sc.dumbtools_modifier_list.move(idx, idx + 1)
            sc.dumbtools_modifier_list_idx += 1
            
        return {'FINISHED'}

class DUMBTOOLS_OT_reorder_modifiers_dialog(bpy.types.Operator):
    bl_idname = "scene.reorder_modifiers_dialog"
    bl_label = "Apply Order"
    bl_options = {'REGISTER', 'UNDO'}

    def invoke(self, context, event):
        sc = context.scene
        sc.dumbtools_modifier_list.clear()
        sc.dumbtools_modifier_list_idx = 0

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

        for (name, mtype) in mod_dict.keys():
            item = sc.dumbtools_modifier_list.add()
            item.mod_name = name
            item.mod_type = mtype

        return context.window_manager.invoke_props_dialog(self, width=400)

    def draw(self, context):
        layout = self.layout
        sc = context.scene
        layout.label(text="Reorder modifiers (applies to all selected objects):")
        
        row = layout.row()
        row.template_list(
            "DUMBTOOLS_UL_modifier_list", "",
            sc, "dumbtools_modifier_list",
            sc, "dumbtools_modifier_list_idx"
        )
        
        col = row.column(align=True)
        op = col.operator("scene.reorder_modifier_item", icon='TRIA_UP', text="")
        op.direction = 'UP'
        op = col.operator("scene.reorder_modifier_item", icon='TRIA_DOWN', text="")
        op.direction = 'DOWN'

    def execute(self, context):
        sc = context.scene
        unified_order = [(item.mod_name, item.mod_type) for item in sc.dumbtools_modifier_list]
        
        if not unified_order:
            return {'CANCELLED'}
            
        count = 0
        original_active = context.view_layer.objects.active
        original_mode = context.mode
        
        if original_active and original_mode != 'OBJECT':
            try:
                bpy.ops.object.mode_set(mode='OBJECT')
            except:
                pass

        # Apply the order intelligently
        for obj in context.selected_objects:
            if not hasattr(obj, "modifiers"):
                continue
                
            # 1. Identify which modifiers correspond to the unified list items
            current_indices = []
            mods_in_unified = []
            
            for i, mod in enumerate(obj.modifiers):
                key = (mod.name, mod.type)
                if key in unified_order:
                    current_indices.append(i)
                    mods_in_unified.append(key)
                    
            if not current_indices:
                continue
                
            # 2. current_indices are inherently ascending. 
            # Filter unified_order to only include keys present in this object
            target_keys = [key for key in unified_order if key in mods_in_unified]
            
            # 3. Move each target key to the corresponding current_index
            context.view_layer.objects.active = obj
            for target_index, key in zip(current_indices, target_keys):
                try:
                    bpy.ops.object.modifier_move_to_index(modifier=key[0], index=target_index)
                except Exception as e:
                    print(f"Failed to move modifier {key[0]} on {obj.name}: {e}")
            count += 1

        context.view_layer.objects.active = original_active
        if original_active and original_mode != 'OBJECT':
            try:
                bpy.ops.object.mode_set(mode=original_mode)
            except:
                pass
                
        self.report({'INFO'}, f"Reordered modifiers on {count} objects")
        
        # Cleanup
        sc.dumbtools_modifier_list.clear()
        return {'FINISHED'}

    def cancel(self, context):
        context.scene.dumbtools_modifier_list.clear()

classes = (
    DUMBTOOLS_PG_ModifierItem,
    DUMBTOOLS_UL_modifier_list,
    DUMBTOOLS_OT_reorder_modifier_item,
    DUMBTOOLS_OT_reorder_modifiers_dialog,
)

def register():
    for cls in classes:
        try:
            bpy.utils.register_class(cls)
        except ValueError:
            bpy.utils.unregister_class(cls)
            bpy.utils.register_class(cls)
            
    bpy.types.Scene.dumbtools_modifier_list = bpy.props.CollectionProperty(type=DUMBTOOLS_PG_ModifierItem)
    bpy.types.Scene.dumbtools_modifier_list_idx = bpy.props.IntProperty()

def unregister():
    for cls in reversed(classes):
        try:
            bpy.utils.unregister_class(cls)
        except RuntimeError:
            pass
            
    if hasattr(bpy.types.Scene, "dumbtools_modifier_list"):
        del bpy.types.Scene.dumbtools_modifier_list
    if hasattr(bpy.types.Scene, "dumbtools_modifier_list_idx"):
        del bpy.types.Scene.dumbtools_modifier_list_idx

register()
bpy.ops.scene.reorder_modifiers_dialog('INVOKE_DEFAULT')
