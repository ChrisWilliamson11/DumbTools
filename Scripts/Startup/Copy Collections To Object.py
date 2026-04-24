# Tooltip: Geometry Input modifier utilities — Copy Collections To Object, Add Collections to Object(s), Attach Selected to Active
import bpy


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

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

    common = root
    for level in range(min(len(c) for c in chains)):
        node = chains[0][level]
        if all(c[level] == node for c in chains):
            common = node
        else:
            break

    selected_set = set(selected_collections)
    while common in selected_set:
        common = parent_map.get(common, root)

    return common


def get_view3d_area(context):
    return next((a for a in context.screen.areas if a.type == 'VIEW_3D'), None)


def add_geometry_input_modifier(context, obj, view3d_area):
    """
    Adds one Geometry Input modifier to obj using the Essentials asset.
    Returns the new modifier, or None if the add failed.
    """
    mod_count_before = len(obj.modifiers)
    with context.temp_override(
        area=view3d_area,
        active_object=obj,
        object=obj,
        selected_objects=[obj],
    ):
        bpy.ops.object.modifier_add_node_group(
            asset_library_type='ESSENTIALS',
            asset_library_identifier="",
            relative_asset_identifier="nodes\\geometry_nodes_essentials.blend\\NodeTree\\Geometry Input"
        )
    if len(obj.modifiers) == mod_count_before:
        return None
    return obj.modifiers[-1]


# ---------------------------------------------------------------------------
# Operator 1 — Copy Collections To Object
# Creates a new plane; one modifier per selected collection.
# First modifier has Replace Original ON to discard the plane geometry.
# ---------------------------------------------------------------------------

class DUMBTOOLS_OT_CopyCollectionsToObject(bpy.types.Operator):
    bl_idname = "outliner.copy_collections_to_object"
    bl_label = "Copy Collections To Object"
    bl_description = (
        "Creates a plane with a Geometry Input modifier for each selected collection. "
        "All set to Relative Space, no instances. First modifier replaces original plane geometry."
    )
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

        view3d_area = get_view3d_area(context)
        if view3d_area is None:
            self.report({'ERROR'}, "No 3D Viewport found on screen.")
            return {'CANCELLED'}

        target_col = find_target_collection(selected_collections, context.scene)

        bpy.ops.mesh.primitive_plane_add(size=1, enter_editmode=False, align='WORLD')
        obj = context.active_object
        obj.name = "Combined_Collections"

        for c in list(obj.users_collection):
            c.objects.unlink(obj)
        target_col.objects.link(obj)
        print(f"  → Object placed in: '{target_col.name}'")

        for i, col in enumerate(selected_collections):
            mod = add_geometry_input_modifier(context, obj, view3d_area)
            if mod is None:
                self.report({'ERROR'}, "Failed to add modifier — asset library may not be loaded yet. Try again.")
                return {'CANCELLED'}

            mod["Socket_6"] = 1          # Input Type: 1=Collection
            mod["Socket_3"] = col        # Collection reference
            mod["Socket_4"] = True       # Relative Space — ON
            mod["Socket_5"] = False      # As Instance — OFF
            mod["Socket_1"] = (i == 0)  # Replace Original — ON for first only

            label = " [Replace Original]" if i == 0 else ""
            print(f"  → Geometry Input for '{col.name}'{label}")

        self.report({'INFO'}, f"Created '{obj.name}' with {len(selected_collections)} Geometry Input modifier(s).")
        return {'FINISHED'}


# ---------------------------------------------------------------------------
# Operator 2 — Add Collections to Object(s)
# Appends Geometry Input modifiers (Collection mode) to all currently
# selected 3D viewport objects. Replace Original is OFF — just adds geo.
# ---------------------------------------------------------------------------

class DUMBTOOLS_OT_AddCollectionsToObjects(bpy.types.Operator):
    bl_idname = "outliner.add_collections_to_objects"
    bl_label = "Add Collections to Object(s)"
    bl_description = (
        "Adds a Geometry Input modifier (Collection) for each selected collection "
        "onto every currently selected object. Relative Space, no instances, no replace."
    )
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

        view3d_area = get_view3d_area(context)
        if view3d_area is None:
            self.report({'ERROR'}, "No 3D Viewport found on screen.")
            return {'CANCELLED'}

        # Grab 3D viewport object selection (persists even when Outliner is active)
        target_objects = list(context.selected_objects)
        if not target_objects:
            self.report({'WARNING'}, "No objects selected in the 3D Viewport.")
            return {'CANCELLED'}

        total_added = 0
        for obj in target_objects:
            for col in selected_collections:
                mod = add_geometry_input_modifier(context, obj, view3d_area)
                if mod is None:
                    self.report({'ERROR'}, "Failed to add modifier — asset library may not be loaded yet. Try again.")
                    return {'CANCELLED'}

                mod["Socket_6"] = 1      # Input Type: 1=Collection
                mod["Socket_3"] = col    # Collection reference
                mod["Socket_4"] = True   # Relative Space — ON
                mod["Socket_5"] = False  # As Instance — OFF
                mod["Socket_1"] = False  # Replace Original — OFF

                print(f"  → Geometry Input for '{col.name}' → '{obj.name}'")
                total_added += 1

        self.report({'INFO'}, f"Added {total_added} Geometry Input modifier(s) across {len(target_objects)} object(s).")
        return {'FINISHED'}


# ---------------------------------------------------------------------------
# Operator 3 — Attach Selected to Active
# 3D Viewport right-click. Adds one Geometry Input modifier (Object mode)
# to the active object for each other selected object.
# Replace Original is OFF — just adds geo.
# ---------------------------------------------------------------------------

class DUMBTOOLS_OT_AttachSelectedToActive(bpy.types.Operator):
    bl_idname = "object.attach_selected_to_active_geo_input"
    bl_label = "Attach Selected to Active"
    bl_description = (
        "Adds a Geometry Input modifier (Object mode) to the active object "
        "for each other selected object. Relative Space, no instances, no replace."
    )
    bl_options = {'REGISTER', 'UNDO'}

    @classmethod
    def poll(cls, context):
        return (
            context.active_object is not None
            and len(context.selected_objects) > 1
        )

    def execute(self, context):
        active = context.active_object
        sources = [o for o in context.selected_objects if o is not active]

        if not sources:
            self.report({'WARNING'}, "Select at least one other object alongside the active object.")
            return {'CANCELLED'}

        view3d_area = get_view3d_area(context)
        if view3d_area is None:
            self.report({'ERROR'}, "No 3D Viewport found on screen.")
            return {'CANCELLED'}

        for src in sources:
            mod = add_geometry_input_modifier(context, active, view3d_area)
            if mod is None:
                self.report({'ERROR'}, "Failed to add modifier — asset library may not be loaded yet. Try again.")
                return {'CANCELLED'}

            mod["Socket_6"] = 0      # Input Type: 0=Object
            mod["Socket_2"] = src    # Object reference  ← Socket_2 assumed; report if wrong
            mod["Socket_4"] = True   # Relative Space — ON
            mod["Socket_5"] = False  # As Instance — OFF
            mod["Socket_1"] = False  # Replace Original — OFF

            print(f"  → Geometry Input for object '{src.name}' → '{active.name}'")

        self.report({'INFO'}, f"Attached {len(sources)} object(s) to '{active.name}' via Geometry Input.")
        return {'FINISHED'}


# ---------------------------------------------------------------------------
# Menu hooks
# ---------------------------------------------------------------------------

def draw_outliner_menu(self, context):
    self.layout.separator()
    self.layout.operator(DUMBTOOLS_OT_CopyCollectionsToObject.bl_idname, icon='OUTLINER_COLLECTION')
    self.layout.operator(DUMBTOOLS_OT_AddCollectionsToObjects.bl_idname, icon='MODIFIER')


def draw_viewport_menu(self, context):
    self.layout.separator()
    self.layout.operator(DUMBTOOLS_OT_AttachSelectedToActive.bl_idname, icon='MODIFIER')


# ---------------------------------------------------------------------------
# Registration
# ---------------------------------------------------------------------------

classes = (
    DUMBTOOLS_OT_CopyCollectionsToObject,
    DUMBTOOLS_OT_AddCollectionsToObjects,
    DUMBTOOLS_OT_AttachSelectedToActive,
)

def register():
    for cls in classes:
        bpy.utils.register_class(cls)
    bpy.types.OUTLINER_MT_collection.append(draw_outliner_menu)
    bpy.types.VIEW3D_MT_object_context_menu.append(draw_viewport_menu)


def unregister():
    bpy.types.OUTLINER_MT_collection.remove(draw_outliner_menu)
    bpy.types.VIEW3D_MT_object_context_menu.remove(draw_viewport_menu)
    for cls in reversed(classes):
        if cls.is_registered:
            bpy.utils.unregister_class(cls)


register()
