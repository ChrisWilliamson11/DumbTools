# Tooltip: Geometry Input modifier utilities — Copy Collections To Object, Add Collections to Object(s), Attach Selected to Active
import bpy
from bpy.props import BoolProperty


# ---------------------------------------------------------------------------
# Helpers — collection hierarchy
# ---------------------------------------------------------------------------

def build_parent_map(root_collection):
    parent_map = {}
    def recurse(col):
        for child in col.children:
            parent_map[child] = col
            recurse(child)
    recurse(root_collection)
    return parent_map


def get_ancestor_chain(col, parent_map, root):
    chain = [col]
    while col in parent_map:
        col = parent_map[col]
        chain.append(col)
    chain.reverse()
    return chain


def find_target_collection(selected_collections, scene):
    """Deepest common ancestor of selected collections, guaranteed not to be one of them."""
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


# ---------------------------------------------------------------------------
# Helpers — modifier management
# ---------------------------------------------------------------------------

def get_view3d_area(context):
    return next((a for a in context.screen.areas if a.type == 'VIEW_3D'), None)


def add_geometry_input_modifier(context, obj, view3d_area):
    """Add one Geometry Input (Essentials asset) modifier to obj. Returns it or None."""
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


def apply_socket_settings(mod, input_type_int, reference, relative_space, as_instance, replace_original):
    """Write the standard Geometry Input socket values onto a modifier."""
    mod["Socket_6"] = input_type_int   # 0=Object, 1=Collection
    if input_type_int == 1:
        mod["Socket_3"] = reference    # Collection reference
    else:
        mod["Socket_2"] = reference    # Object reference (Socket_2 assumed — report if wrong)
    mod["Socket_4"] = relative_space
    mod["Socket_5"] = as_instance
    mod["Socket_1"] = replace_original


# ---------------------------------------------------------------------------
# Helpers — emission override
# ---------------------------------------------------------------------------

def collect_materials_from_collections(collections):
    """All unique material data blocks used by objects inside the given collections."""
    materials = set()
    for col in collections:
        for obj in col.all_objects:
            for slot in obj.material_slots:
                if slot.material:
                    materials.add(slot.material)
    return materials


def collect_materials_from_objects(objects):
    """All unique material data blocks used by the given objects."""
    materials = set()
    for obj in objects:
        for slot in obj.material_slots:
            if slot.material:
                materials.add(slot.material)
    return materials


def material_has_emission(mat):
    """Return True if the material has any active emission contribution."""
    if not mat.use_nodes or not mat.node_tree:
        return False
    for node in mat.node_tree.nodes:
        if node.type == 'BSDF_PRINCIPLED':
            strength = node.inputs.get('Emission Strength')
            if strength and (strength.is_linked or strength.default_value > 0.0):
                return True
        elif node.type == 'EMISSION':
            strength = node.inputs.get('Strength')
            if strength and (strength.is_linked or strength.default_value > 0.0):
                return True
    return False


def get_or_create_no_emit_material(mat):
    """Return a persistent emission-free copy of mat, creating it if needed."""
    no_emit_name = mat.name + ".no_emit"
    existing = bpy.data.materials.get(no_emit_name)
    if existing:
        return existing

    no_emit = mat.copy()
    no_emit.name = no_emit_name

    if no_emit.node_tree:
        links = no_emit.node_tree.links
        for node in no_emit.node_tree.nodes:
            if node.type == 'BSDF_PRINCIPLED':
                for socket_name in ('Emission Strength', 'Emission Color'):
                    socket = node.inputs.get(socket_name)
                    if socket:
                        for link in [l for l in links if l.to_socket == socket]:
                            links.remove(link)
                strength = node.inputs.get('Emission Strength')
                if strength:
                    strength.default_value = 0.0
            elif node.type == 'EMISSION':
                strength = node.inputs.get('Strength')
                if strength:
                    for link in [l for l in links if l.to_socket == strength]:
                        links.remove(link)
                    strength.default_value = 0.0

    print(f"  → Created no-emit material: '{no_emit_name}'")
    return no_emit


def build_no_emission_gn_modifier(obj, source_materials):
    """
    Add/replace a 'No Emission Override' GN modifier on obj that chains Replace Material
    nodes to swap every emitting material for its no-emit copy.
    """
    emitting_pairs = [
        (mat, get_or_create_no_emit_material(mat))
        for mat in source_materials
        if material_has_emission(mat)
    ]

    if not emitting_pairs:
        print("  → No emitting materials found — skipping No Emission Override.")
        return

    # Remove any pre-existing override modifier so we always rebuild fresh
    existing_mod = obj.modifiers.get("No Emission Override")
    if existing_mod:
        obj.modifiers.remove(existing_mod)

    # Remove and recreate the node group so it always reflects current materials
    ng_name = "No Emission Override"
    existing_ng = bpy.data.node_groups.get(ng_name)
    if existing_ng:
        bpy.data.node_groups.remove(existing_ng)

    ng = bpy.data.node_groups.new(ng_name, 'GeometryNodeTree')

    # Define group sockets (Blender 4.0+ interface API)
    ng.interface.new_socket("Geometry", in_out='INPUT',  socket_type='NodeSocketGeometry')
    ng.interface.new_socket("Geometry", in_out='OUTPUT', socket_type='NodeSocketGeometry')

    nodes = ng.nodes
    links = ng.links

    group_in  = nodes.new('NodeGroupInput')
    group_in.location  = (-300, 0)
    group_out = nodes.new('NodeGroupOutput')
    group_out.location = (200 + len(emitting_pairs) * 220, 0)

    prev_geo = group_in.outputs[0]
    for i, (orig_mat, no_emit_mat) in enumerate(emitting_pairs):
        rn = nodes.new('GeometryNodeReplaceMaterial')
        rn.location = (-100 + i * 220, 0)
        rn.inputs['Old'].default_value = orig_mat
        rn.inputs['New'].default_value = no_emit_mat
        links.new(prev_geo, rn.inputs['Geometry'])
        prev_geo = rn.outputs['Geometry']

    links.new(prev_geo, group_out.inputs[0])

    mod = obj.modifiers.new("No Emission Override", type='NODES')
    mod.node_group = ng
    print(f"  → Built No Emission Override ({len(emitting_pairs)} material(s) replaced)")


# ---------------------------------------------------------------------------
# Operator 1 — Copy Collections To Object
# ---------------------------------------------------------------------------

class DUMBTOOLS_OT_CopyCollectionsToObject(bpy.types.Operator):
    bl_idname = "outliner.copy_collections_to_object"
    bl_label = "Copy Collections To Object"
    bl_description = (
        "Creates a plane with a Geometry Input modifier for each selected collection. "
        "First modifier replaces plane geometry."
    )
    bl_options = {'REGISTER', 'UNDO'}

    relative_space:    BoolProperty(name="Relative Space",    default=True)
    as_instance:       BoolProperty(name="As Instance",       default=False)
    disable_emission:  BoolProperty(name="Disable Emission",  default=False,
                                    description="Add a GN Replace Material chain to zero emission on all source materials")

    @classmethod
    def poll(cls, context):
        return any(isinstance(item, bpy.types.Collection) for item in context.selected_ids)

    def invoke(self, context, event):
        return context.window_manager.invoke_props_dialog(self)

    def draw(self, context):
        layout = self.layout
        layout.prop(self, "relative_space")
        layout.prop(self, "as_instance")
        layout.prop(self, "disable_emission")
        layout.separator()
        row = layout.row()
        row.enabled = False
        row.label(text="Replace Original: always ON for first modifier", icon='INFO')

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
            apply_socket_settings(mod, 1, col, self.relative_space, self.as_instance, (i == 0))
            print(f"  → Geometry Input: '{col.name}'" + (" [Replace Original]" if i == 0 else ""))

        if self.disable_emission:
            mats = collect_materials_from_collections(selected_collections)
            build_no_emission_gn_modifier(obj, mats)

        self.report({'INFO'}, f"Created '{obj.name}' with {len(selected_collections)} Geometry Input modifier(s).")
        return {'FINISHED'}


# ---------------------------------------------------------------------------
# Operator 2 — Add Collections to Object(s)
# ---------------------------------------------------------------------------

class DUMBTOOLS_OT_AddCollectionsToObjects(bpy.types.Operator):
    bl_idname = "outliner.add_collections_to_objects"
    bl_label = "Add Collections to Object(s)"
    bl_description = (
        "Adds a Geometry Input modifier (Collection) for each selected collection "
        "onto every currently selected viewport object."
    )
    bl_options = {'REGISTER', 'UNDO'}

    relative_space:    BoolProperty(name="Relative Space",    default=True)
    as_instance:       BoolProperty(name="As Instance",       default=False)
    replace_original:  BoolProperty(name="Replace Original",  default=False)
    disable_emission:  BoolProperty(name="Disable Emission",  default=False,
                                    description="Add a GN Replace Material chain to zero emission on all source materials")

    @classmethod
    def poll(cls, context):
        return any(isinstance(item, bpy.types.Collection) for item in context.selected_ids)

    def invoke(self, context, event):
        return context.window_manager.invoke_props_dialog(self)

    def draw(self, context):
        layout = self.layout
        layout.prop(self, "relative_space")
        layout.prop(self, "as_instance")
        layout.prop(self, "replace_original")
        layout.prop(self, "disable_emission")

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

        target_objects = list(context.selected_objects)
        if not target_objects:
            self.report({'WARNING'}, "No objects selected in the 3D Viewport.")
            return {'CANCELLED'}

        source_mats = collect_materials_from_collections(selected_collections) if self.disable_emission else set()

        total_added = 0
        for obj in target_objects:
            for col in selected_collections:
                mod = add_geometry_input_modifier(context, obj, view3d_area)
                if mod is None:
                    self.report({'ERROR'}, "Failed to add modifier — asset library may not be loaded yet. Try again.")
                    return {'CANCELLED'}
                apply_socket_settings(mod, 1, col, self.relative_space, self.as_instance, self.replace_original)
                print(f"  → Geometry Input: '{col.name}' → '{obj.name}'")
                total_added += 1

            if self.disable_emission:
                build_no_emission_gn_modifier(obj, source_mats)

        self.report({'INFO'}, f"Added {total_added} Geometry Input modifier(s) across {len(target_objects)} object(s).")
        return {'FINISHED'}


# ---------------------------------------------------------------------------
# Operator 3 — Attach Selected to Active
# ---------------------------------------------------------------------------

class DUMBTOOLS_OT_AttachSelectedToActive(bpy.types.Operator):
    bl_idname = "object.attach_selected_to_active_geo_input"
    bl_label = "Attach Selected to Active"
    bl_description = (
        "Adds a Geometry Input modifier (Object mode) to the active object "
        "for each other selected object."
    )
    bl_options = {'REGISTER', 'UNDO'}

    relative_space:    BoolProperty(name="Relative Space",    default=True)
    as_instance:       BoolProperty(name="As Instance",       default=False)
    replace_original:  BoolProperty(name="Replace Original",  default=False)
    disable_emission:  BoolProperty(name="Disable Emission",  default=False,
                                    description="Add a GN Replace Material chain to zero emission on all source materials")

    @classmethod
    def poll(cls, context):
        return context.active_object is not None and len(context.selected_objects) > 1

    def invoke(self, context, event):
        return context.window_manager.invoke_props_dialog(self)

    def draw(self, context):
        layout = self.layout
        layout.prop(self, "relative_space")
        layout.prop(self, "as_instance")
        layout.prop(self, "replace_original")
        layout.prop(self, "disable_emission")

    def execute(self, context):
        active  = context.active_object
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
            apply_socket_settings(mod, 0, src, self.relative_space, self.as_instance, self.replace_original)
            print(f"  → Geometry Input: object '{src.name}' → '{active.name}'")

        if self.disable_emission:
            mats = collect_materials_from_objects(sources)
            build_no_emission_gn_modifier(active, mats)

        self.report({'INFO'}, f"Attached {len(sources)} object(s) to '{active.name}' via Geometry Input.")
        return {'FINISHED'}


# ---------------------------------------------------------------------------
# Menu hooks
# ---------------------------------------------------------------------------

def draw_outliner_menu(self, context):
    self.layout.separator()
    self.layout.operator(DUMBTOOLS_OT_CopyCollectionsToObject.bl_idname,  icon='OUTLINER_COLLECTION')
    self.layout.operator(DUMBTOOLS_OT_AddCollectionsToObjects.bl_idname,  icon='MODIFIER')


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
