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
        # --- DEBUG: what did selected_ids give us? ---
        print(f"[DBG] selected_ids count: {len(context.selected_ids)}")
        for item in context.selected_ids:
            lib = getattr(item, 'library', None)
            override = getattr(item, 'override_library', None)
            print(f"  [DBG] item: {item!r}  type={type(item).__name__}  library={lib}  override={override is not None}")

        selected_collections = [
            item for item in context.selected_ids
            if isinstance(item, bpy.types.Collection)
        ]
        print(f"[DBG] collections found: {[c.name for c in selected_collections]}")

        if not selected_collections:
            self.report({'WARNING'}, "No collections selected in the Outliner.")
            return {'CANCELLED'}

        # Determine where to place the new object
        target_col = find_target_collection(selected_collections, context.scene)
        print(f"[DBG] target collection: '{target_col.name}'  library={getattr(target_col, 'library', None)}")

        # Create the plane (lands in whatever the active collection is)
        bpy.ops.mesh.primitive_plane_add(size=1, enter_editmode=False, align='WORLD')
        obj = context.active_object
        obj.name = "Combined_Collections"
        print(f"[DBG] created object: '{obj.name}'  initially in: {[c.name for c in obj.users_collection]}")

        # Move the object to the target collection
        for c in list(obj.users_collection):
            c.objects.unlink(obj)
        target_col.objects.link(obj)
        print(f"  → Object placed in collection: '{target_col.name}'")

        # modifier_add_node_group requires a VIEW_3D context — find one on screen
        view3d_area = next((a for a in context.screen.areas if a.type == 'VIEW_3D'), None)
        print(f"[DBG] VIEW_3D area found: {view3d_area is not None}")
        if view3d_area is None:
            self.report({'ERROR'}, "No 3D Viewport found on screen. Please have a 3D Viewport visible.")
            return {'CANCELLED'}

        for i, col in enumerate(selected_collections):
            mod_count_before = len(obj.modifiers)
            print(f"[DBG] iteration {i}: col='{col.name}'  modifiers before={mod_count_before}")

            # Run the asset-based modifier add inside the 3D Viewport context
            with context.temp_override(
                area=view3d_area,
                active_object=obj,
                object=obj,
                selected_objects=[obj],
            ):
                result = bpy.ops.object.modifier_add_node_group(
                    asset_library_type='ESSENTIALS',
                    asset_library_identifier="",
                    relative_asset_identifier="nodes\\geometry_nodes_essentials.blend\\NodeTree\\Geometry Input"
                )
                print(f"[DBG] modifier_add_node_group result: {result}")

            mod_count_after = len(obj.modifiers)
            print(f"[DBG] modifiers after: {mod_count_after}  (added {mod_count_after - mod_count_before})")

            if mod_count_after == mod_count_before:
                self.report({'ERROR'}, "Failed to add Geometry Input modifier — asset library may not be fully loaded. Try again.")
                return {'CANCELLED'}

            # Grab the modifier that was just appended
            mod = obj.modifiers[-1]
            print(f"[DBG] modifier name: '{mod.name}'  type: {mod.type}")
            print(f"[DBG] modifier keys: {list(mod.keys())}")

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
