# Tooltip: Add a stamp to your renders
import bpy
from bpy_extras.io_utils import ImportHelper
from bpy.props import StringProperty, CollectionProperty, PointerProperty

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
        # Find the 'DynamicText' collection in the appended scene
        stamp_scene = bpy.data.scenes["Stamp"]
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

class OpenFileBrowserOperator(bpy.types.Operator, ImportHelper):
    bl_idname = "import_scene.append_stamp_scene"
    bl_label = "Append Stamp Scene"
    filename_ext = ".blend"
    filter_glob: bpy.props.StringProperty(
        default="*.blend",
        options={'HIDDEN'},
        maxlen=255,
    )

    def execute(self, context):
        # Open the selected .blend file
        filepath = self.filepath
        
        # Append the "Stamp" scene
        with bpy.data.libraries.load(filepath, link=False) as (data_from, data_to):
            if "Stamp" in data_from.scenes:
                data_to.scenes = ["Stamp"]
            else:
                self.report({'ERROR'}, "Scene 'Stamp' not found in the selected file.")
                return {'CANCELLED'}
        
        # Get the current scene and the appended "Stamp" scene
        current_scene = context.scene
        stamp_scene = bpy.data.scenes["Stamp"]
        
        # Enable the compositor if it's not enabled
        if not current_scene.use_nodes:
            current_scene.use_nodes = True
        
        # Get the compositor nodes
        tree = current_scene.node_tree
        links = tree.links

        # Add render layer node for the appended "Stamp" scene
        rl_stamp = tree.nodes.new(type='CompositorNodeRLayers')
        rl_stamp.location = (0, -200)
        rl_stamp.scene = stamp_scene

        # Find the last node connected to the Composite node
        composite_node = next(node for node in tree.nodes if isinstance(node, bpy.types.CompositorNodeComposite))
        last_node = next((link.from_node for link in tree.links if link.to_node == composite_node), None)

        # Add a mix node to mix the scenes
        mix_node = tree.nodes.new(type='CompositorNodeMixRGB')
        mix_node.location = (last_node.location.x + 200, last_node.location.y if last_node else 0)

        # Connect the last node to the first input of the mix node
        if last_node:
            links.new(last_node.outputs[0], mix_node.inputs[1])

        # Connect the "Stamp" scene render layer node to the second input of the mix node
        links.new(rl_stamp.outputs[0], mix_node.inputs[2])
        
        # Connect the alpha output of the "Stamp" scene to the factor input of the mix node
        links.new(rl_stamp.outputs['Alpha'], mix_node.inputs[0])

        # Connect the output of the mix node to the Composite node
        links.new(mix_node.outputs[0], composite_node.inputs[0])

        # Show the popup window with text fields
        bpy.ops.wm.dynamic_text_popup('INVOKE_DEFAULT')
        
        self.report({'INFO'}, "Appended 'Stamp' scene and mixed it with the current scene.")
        return {'FINISHED'}

def register():
    bpy.utils.register_class(TextEntry)
    bpy.utils.register_class(DynamicTextPopupOperator)
    bpy.utils.register_class(OpenFileBrowserOperator)

def unregister():
    bpy.utils.unregister_class(TextEntry)
    bpy.utils.unregister_class(DynamicTextPopupOperator)
    bpy.utils.unregister_class(OpenFileBrowserOperator)

def main():
    register()
    # Invoke the operator
    bpy.ops.import_scene.append_stamp_scene('INVOKE_DEFAULT')

main()
