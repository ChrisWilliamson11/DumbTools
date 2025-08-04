# Tooltip: Edit the text in an imported 'Stamp' scene
import bpy
from bpy.props import StringProperty, CollectionProperty

class TextEntry(bpy.types.PropertyGroup):
    name: StringProperty(name="Name")
    text: StringProperty(name="Text")

class DynamicTextPopupOperator(bpy.types.Operator):
    bl_idname = "wm.dynamic_text_popup"
    bl_label = "Enter Text for Dynamic Fields"
    
    text_entries: CollectionProperty(type=TextEntry)
    
    def execute(self, context):
        # Update text objects with the entered text
        for entry in self.text_entries:
            obj = bpy.data.objects.get(entry.name)
            if obj and obj.type == 'FONT':
                obj.data.body = entry.text
        return {'FINISHED'}
    
    def draw(self, context):
        layout = self.layout
        for entry in self.text_entries:
            row = layout.row()
            row.label(text=entry.name)
            row.prop(entry, "text", text="")
    
    def invoke(self, context, event):
        # Find the 'DynamicText' collection in the 'Stamp' scene
        stamp_scene = bpy.data.scenes.get("Stamp")
        
        if not stamp_scene:
            self.report({'ERROR'}, "Scene 'Stamp' not found.")
            return {'CANCELLED'}
        
        dynamic_text_collection = find_dynamic_text_collection(stamp_scene.collection)
        
        if not dynamic_text_collection:
            self.report({'ERROR'}, "Collection 'DynamicText' not found in the 'Stamp' scene.")
            return {'CANCELLED'}
        
        # Populate the popup with the objects from 'DynamicText' collection
        create_text_entries(self, dynamic_text_collection)
        
        return context.window_manager.invoke_props_dialog(self)

def create_text_entries(operator, dynamic_text_collection):
    for obj in dynamic_text_collection.objects:
        if obj.type == 'FONT':
            entry = operator.text_entries.add()
            entry.name = obj.name
            entry.text = obj.data.body

def find_dynamic_text_collection(collection):
    for coll in collection.children:
        if "DynamicText" in coll.name:
            return coll
        found = find_dynamic_text_collection(coll)
        if found:
            return found
    return None

def register():
    bpy.utils.register_class(TextEntry)
    bpy.utils.register_class(DynamicTextPopupOperator)

def unregister():
    bpy.utils.unregister_class(TextEntry)
    bpy.utils.unregister_class(DynamicTextPopupOperator)

def main():
    register()
    # Invoke the operator
    bpy.ops.wm.dynamic_text_popup('INVOKE_DEFAULT')

main()
