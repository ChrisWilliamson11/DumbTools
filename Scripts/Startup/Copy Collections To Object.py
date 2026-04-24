# Tooltip: Creates a plane with a Geometry Input modifier per collection selected in the Outliner
import bpy


def build_parent_map(root_collection):
    """Returns {child_collection: parent_collection} for the full hierarchy."""
    parent_map = {}
    def recurse(col):
        for child in col.children:
            parent_map[child] = col
            recurse(child)
    recurse(root_collection)
    return parent_map


def get_ancestor_chain(col, parent_map, root):
    """Returns the chain [root, ..., parent, col] for a given collection."""
    chain = [col]
    while col in parent_map:
        col = parent_map[col]
        chain.append(col)
    chain.reverse()
    return chain


def find_target_collection(selected_collections, scene):
    """
    Returns the deepest common ancestor of all selected collections,
    guaranteed not to be one of the selected collections themselves.
    Falls back to scene root if needed.
    """
    root = scene.collection
    parent_map = build_parent_map(root)

    chains = [get_ancestor_chain(col, parent_map, root) for col in selected_collections]

    # Walk chains in lock-step to find the deepest common node
    common = root
    for level in range(min(len(c) for c in chains)):
        node = chains[0][level]
        if all(c[level] == node for c in chains):
            common = node
        else:
            break

    # Make sure the common collection isn't one of the selected ones
    selected_set = set(selected_collections)
    while common in selected_set:
        common = parent_map.get(common, root)

    return common


class DUMBTOOLS_OT_CopyCollectionsToObject(bpy.types.Operator):
    bl_idname = "outliner.copy_collections_to_object"
    bl_label = "Copy Collections To Object"
    bl_description = "Creates a plane with a Geometry Input modifier for each selected collection. All set to Relative Space, no instances. First modifier replaces original geometry."
    bl_options = {'REGISTER', 'UNDO'}

    @classmethod
    def poll(cls, context):
        return any(isinstance(item, bpy.types.Collection) for item in context.selected_ids)

    def execute(self, context):
        selected_collections = [
            item for item in context.selected_ids
            if isinstance(item, bpy.types.Collection)
        ]

        if not selected_collections:
            self.report({'WARNING'}, "No collections selected in the Outliner.")
            return {'CANCELLED'}

        # Determine where to place the new object
        target_col = find_target_collection(selected_collections, context.scene)

        # Create the plane (lands in whatever the active collection is)
        bpy.ops.mesh.primitive_plane_add(size=1, enter_editmode=False, align='WORLD')
        obj = context.active_object
        obj.name = "Combined_Collections"

        # Move the object to the target collection
        for c in list(obj.users_collection):
            c.objects.unlink(obj)
        target_col.objects.link(obj)

        print(f"  → Object placed in collection: '{target_col.name}'")

        for i, col in enumerate(selected_collections):
            # Add the Geometry Input modifier from the bundled Essentials asset library
            bpy.ops.object.modifier_add_node_group(
                asset_library_type='ESSENTIALS',
                asset_library_identifier="",
                relative_asset_identifier="nodes\\geometry_nodes_essentials.blend\\NodeTree\\Geometry Input"
            )

            # Grab the modifier that was just appended
            mod = obj.modifiers[-1]

            mod["Socket_6"] = 1              # Input Type: 0=Object, 1=Collection
            mod["Socket_3"] = col            # Collection reference
            mod["Socket_4"] = True           # Relative Space — ON
            mod["Socket_5"] = False          # As Instance — OFF
            mod["Socket_1"] = (i == 0)       # Replace Original — ON for first only

            label = " [Replace Original]" if i == 0 else ""
            print(f"  → Added Geometry Input for '{col.name}'{label}")

        self.report({'INFO'}, f"Created '{obj.name}' with {len(selected_collections)} Geometry Input modifier(s).")
        return {'FINISHED'}


def draw_menu(self, context):
    self.layout.separator()
    self.layout.operator(DUMBTOOLS_OT_CopyCollectionsToObject.bl_idname)


def register():
    bpy.utils.register_class(DUMBTOOLS_OT_CopyCollectionsToObject)
    bpy.types.OUTLINER_MT_collection.append(draw_menu)


def unregister():
    bpy.types.OUTLINER_MT_collection.remove(draw_menu)
    if DUMBTOOLS_OT_CopyCollectionsToObject.is_registered:
        bpy.utils.unregister_class(DUMBTOOLS_OT_CopyCollectionsToObject)


register()
