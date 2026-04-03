import bpy

def select_upstream_nodes(node, nodes):
    for input in node.inputs:
        for link in input.links:
            linked_node = link.from_node
            if linked_node not in nodes:
                nodes.add(linked_node)
                select_upstream_nodes(linked_node, nodes)

class SelectUpstreamOperator(bpy.types.Operator):
    """Select all upstream nodes"""
    bl_idname = "node.select_upstream"
    bl_label = "Select Upstream Nodes"

    def execute(self, context):
        nodes = set()
        for node in context.selected_nodes:
            select_upstream_nodes(node, nodes)

        for node in nodes:
            node.select = True

        return {'FINISHED'}

def menu_func(self, context):
    self.layout.operator(SelectUpstreamOperator.bl_idname)

def register():
    bpy.utils.register_class(SelectUpstreamOperator)
    bpy.types.NODE_MT_context_menu.append(menu_func)

def unregister():
    bpy.utils.unregister_class(SelectUpstreamOperator)
    bpy.types.NODE_MT_context_menu.remove(menu_func)


register()
