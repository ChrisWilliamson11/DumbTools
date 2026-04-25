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

def is_editable_collection(col):
    """True if objects can be linked into this collection (local, not linked or overridden)."""
    return col.library is None and col.override_library is None

def find_target_collection(selected_collections, scene):
    """
    Deepest common ancestor of selected_collections that is:
    - not one of the selected collections itself
    - editable (not linked / not a library override)
    Falls back to scene root, which is always local.
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
    # Walk up until we find a collection we can actually write into
    while common != root and (common in selected_set or not is_editable_collection(common)):
        common = parent_map.get(common, root)

    # Root is always editable; if even that fails something is very wrong
    if not is_editable_collection(common):
        common = root
    return common


# ---------------------------------------------------------------------------
# Helpers — modifier management
# ---------------------------------------------------------------------------

def get_view3d_area(context):
    return next((a for a in context.screen.areas if a.type == 'VIEW_3D'), None)

def get_outliner_area(context):
    return next((a for a in context.screen.areas if a.type == 'OUTLINER'), None)

def get_outliner_collections(context):
    """Read collection selection from the Outliner regardless of current context area."""
    outliner = get_outliner_area(context)
    if outliner is None:
        return []
    window_region = next((r for r in outliner.regions if r.type == 'WINDOW'), None)
    if window_region is None:
        return []
    with context.temp_override(area=outliner, region=window_region):
        return [item for item in context.selected_ids if isinstance(item, bpy.types.Collection)]

def add_geometry_input_modifier(context, obj, view3d_area, max_retries=3):
    """Add one Geometry Input modifier, retrying up to max_retries times if the asset isn't ready."""
    for attempt in range(max_retries):
        mod_count_before = len(obj.modifiers)
        try:
            with context.temp_override(area=view3d_area, active_object=obj, object=obj, selected_objects=[obj]):
                bpy.ops.object.modifier_add_node_group(
                    asset_library_type='ESSENTIALS',
                    asset_library_identifier="",
                    relative_asset_identifier="nodes\\geometry_nodes_essentials.blend\\NodeTree\\Geometry Input"
                )
        except Exception as e:
            print(f"  [!] modifier_add_node_group exception (attempt {attempt+1}): {e}")
        if len(obj.modifiers) > mod_count_before:
            return obj.modifiers[-1]
        print(f"  [!] Modifier not added (attempt {attempt+1}/{max_retries}) — asset may still be loading.")
    return None

def apply_socket_settings(mod, input_type_int, reference, relative_space, as_instance, replace_original):
    mod["Socket_6"] = input_type_int
    if input_type_int == 1:
        mod["Socket_3"] = reference
    else:
        mod["Socket_2"] = reference  # Socket_2 assumed for object — report if wrong
    mod["Socket_4"] = relative_space
    mod["Socket_5"] = as_instance
    mod["Socket_1"] = replace_original


# ---------------------------------------------------------------------------
# Helpers — emission override
# ---------------------------------------------------------------------------

def collect_materials_from_collections(collections):
    materials = set()
    for col in collections:
        for obj in col.all_objects:
            for slot in obj.material_slots:
                if slot.material:
                    materials.add(slot.material)
    return materials

def collect_materials_from_objects(objects):
    materials = set()
    for obj in objects:
        for slot in obj.material_slots:
            if slot.material:
                materials.add(slot.material)
    return materials

def material_has_emission(mat):
    try:
        if not mat.use_nodes or not mat.node_tree:
            return False
        for node in mat.node_tree.nodes:
            if node.type == 'BSDF_PRINCIPLED':
                s = node.inputs.get('Emission Strength')
                if s and (s.is_linked or s.default_value > 0.0):
                    return True
            elif node.type == 'EMISSION':
                s = node.inputs.get('Strength')
                if s and (s.is_linked or s.default_value > 0.0):
                    return True
        return False
    except Exception as e:
        print(f"  [!] Error checking emission on '{getattr(mat, 'name', '?')}': {e}")
        return False

def get_or_create_no_emit_material(mat):
    try:
        no_emit_name = mat.name + ".no_emit"
        existing = bpy.data.materials.get(no_emit_name)
        if existing:
            return existing
        no_emit = mat.copy()
        no_emit.name = no_emit_name
        if no_emit.node_tree:
            links = no_emit.node_tree.links
            for node in no_emit.node_tree.nodes:
                try:
                    if node.type == 'BSDF_PRINCIPLED':
                        for sname in ('Emission Strength', 'Emission Color'):
                            sock = node.inputs.get(sname)
                            if sock:
                                for lnk in [l for l in links if l.to_socket == sock]:
                                    links.remove(lnk)
                        s = node.inputs.get('Emission Strength')
                        if s:
                            s.default_value = 0.0
                    elif node.type == 'EMISSION':
                        s = node.inputs.get('Strength')
                        if s:
                            for lnk in [l for l in links if l.to_socket == s]:
                                links.remove(lnk)
                            s.default_value = 0.0
                except Exception as node_err:
                    print(f"  [!] Skipping node '{node.name}' in '{mat.name}': {node_err}")
        print(f"  → Created no-emit material: '{no_emit_name}'")
        return no_emit
    except Exception as e:
        print(f"  [!] Could not create no-emit copy of '{getattr(mat, 'name', '?')}': {e} — skipping.")
        return None

def build_no_emission_gn_modifier(obj, source_materials):
    pairs = []
    for m in source_materials:
        if not material_has_emission(m):
            continue
        no_emit = get_or_create_no_emit_material(m)
        if no_emit is not None:
            pairs.append((m, no_emit))
        else:
            print(f"  [!] Skipped '{m.name}' — no-emit copy could not be created.")
    if not pairs:
        print("  → No emitting materials found.")
        return
    existing = obj.modifiers.get("No Emission Override")
    if existing:
        obj.modifiers.remove(existing)
    ng_name = "No Emission Override"
    old_ng = bpy.data.node_groups.get(ng_name)
    if old_ng:
        bpy.data.node_groups.remove(old_ng)
    ng = bpy.data.node_groups.new(ng_name, 'GeometryNodeTree')
    ng.interface.new_socket("Geometry", in_out='INPUT',  socket_type='NodeSocketGeometry')
    ng.interface.new_socket("Geometry", in_out='OUTPUT', socket_type='NodeSocketGeometry')
    nodes, links = ng.nodes, ng.links
    gi = nodes.new('NodeGroupInput');  gi.location = (-300, 0)
    go = nodes.new('NodeGroupOutput'); go.location = (200 + len(pairs) * 220, 0)
    prev = gi.outputs[0]
    for i, (orig, no_emit) in enumerate(pairs):
        rn = nodes.new('GeometryNodeReplaceMaterial')
        rn.location = (-100 + i * 220, 0)
        rn.inputs['Old'].default_value = orig
        rn.inputs['New'].default_value = no_emit
        links.new(prev, rn.inputs['Geometry'])
        prev = rn.outputs['Geometry']
    links.new(prev, go.inputs[0])
    mod = obj.modifiers.new("No Emission Override", type='NODES')
    mod.node_group = ng
    print(f"  → Built No Emission Override ({len(pairs)} material(s))")


# ---------------------------------------------------------------------------
# Shared draw helper (NOT a mixin with annotations — __annotations__ is not
# inherited in Python, so BoolProps must be declared on each class directly)
# ---------------------------------------------------------------------------

class GeoInputSettings:
    def draw_base(self, layout):
        layout.prop(self, "relative_space")
        layout.prop(self, "as_instance")
        layout.prop(self, "disable_emission")


# ---------------------------------------------------------------------------
# Operator 1 — Copy Collections To Object  (Outliner right-click)
# ---------------------------------------------------------------------------

class DUMBTOOLS_OT_CopyCollectionsToObject(GeoInputSettings, bpy.types.Operator):
    bl_idname  = "outliner.copy_collections_to_object"
    bl_label   = "Copy Collections To Object"
    bl_description = "Creates a plane with one Geometry Input modifier per selected collection"
    bl_options = {'REGISTER', 'UNDO'}

    relative_space:   BoolProperty(name="Relative Space",   default=True)
    as_instance:      BoolProperty(name="As Instance",      default=False)
    disable_emission: BoolProperty(name="Disable Emission", default=False)

    @classmethod
    def poll(cls, context):
        return any(a.type == 'OUTLINER' for a in context.screen.areas)

    def invoke(self, context, event):
        return context.window_manager.invoke_props_dialog(self)

    def draw(self, context):
        layout = self.layout
        self.draw_base(layout)
        layout.separator()
        row = layout.row(); row.enabled = False
        row.label(text="Replace Original: always ON for first modifier", icon='INFO')

    def execute(self, context):
        cols = get_outliner_collections(context)
        if not cols:
            self.report({'WARNING'}, "No collections selected in the Outliner.")
            return {'CANCELLED'}
        view3d = get_view3d_area(context)
        if not view3d:
            self.report({'ERROR'}, "No 3D Viewport found on screen.")
            return {'CANCELLED'}
        target_col = find_target_collection(cols, context.scene)
        bpy.ops.mesh.primitive_plane_add(size=1, enter_editmode=False, align='WORLD')
        obj = context.active_object
        obj.name = "Combined_Collections"
        for c in list(obj.users_collection):
            c.objects.unlink(obj)
        target_col.objects.link(obj)
        print(f"  → Placed in: '{target_col.name}'")
        for i, col in enumerate(cols):
            mod = add_geometry_input_modifier(context, obj, view3d)
            if mod is None:
                self.report({'ERROR'}, "Failed to add modifier — try again.")
                return {'CANCELLED'}
            apply_socket_settings(mod, 1, col, self.relative_space, self.as_instance, (i == 0))
            print(f"  → Geometry Input: '{col.name}'" + (" [Replace]" if i == 0 else ""))
        if self.disable_emission:
            build_no_emission_gn_modifier(obj, collect_materials_from_collections(cols))
        self.report({'INFO'}, f"Created '{obj.name}' with {len(cols)} modifier(s).")
        return {'FINISHED'}


# ---------------------------------------------------------------------------
# Operator 2 — Add Collections to Object(s)
# Outliner right-click AND viewport right-click (reads Outliner selection via override)
# ---------------------------------------------------------------------------

class DUMBTOOLS_OT_AddCollectionsToObjects(GeoInputSettings, bpy.types.Operator):
    bl_idname  = "outliner.add_collections_to_objects"
    bl_label   = "Add Collections to Object(s)"
    bl_description = "Adds a Geometry Input modifier per selected collection onto each selected viewport object"
    bl_options = {'REGISTER', 'UNDO'}

    relative_space:   BoolProperty(name="Relative Space",   default=True)
    as_instance:      BoolProperty(name="As Instance",      default=False)
    disable_emission: BoolProperty(name="Disable Emission", default=False)
    replace_original: BoolProperty(name="Replace Original", default=False)

    @classmethod
    def poll(cls, context):
        return any(a.type == 'OUTLINER' for a in context.screen.areas)

    def invoke(self, context, event):
        return context.window_manager.invoke_props_dialog(self)

    def draw(self, context):
        layout = self.layout
        self.draw_base(layout)
        layout.prop(self, "replace_original")

    def execute(self, context):
        cols = get_outliner_collections(context)
        if not cols:
            self.report({'WARNING'}, "No collections selected in the Outliner.")
            return {'CANCELLED'}
        view3d = get_view3d_area(context)
        if not view3d:
            self.report({'ERROR'}, "No 3D Viewport found on screen.")
            return {'CANCELLED'}
        targets = list(context.selected_objects)
        if not targets:
            self.report({'WARNING'}, "No objects selected in the 3D Viewport.")
            return {'CANCELLED'}
        src_mats = collect_materials_from_collections(cols) if self.disable_emission else set()
        total = 0
        for obj in targets:
            for col in cols:
                mod = add_geometry_input_modifier(context, obj, view3d)
                if mod is None:
                    self.report({'ERROR'}, "Failed to add modifier — try again.")
                    return {'CANCELLED'}
                apply_socket_settings(mod, 1, col, self.relative_space, self.as_instance, self.replace_original)
                print(f"  → Geometry Input: '{col.name}' → '{obj.name}'")
                total += 1
            if self.disable_emission:
                build_no_emission_gn_modifier(obj, src_mats)
        self.report({'INFO'}, f"Added {total} modifier(s) across {len(targets)} object(s).")
        return {'FINISHED'}


# ---------------------------------------------------------------------------
# Operator 3 — Attach Selected to Active  (viewport right-click)
# ---------------------------------------------------------------------------

class DUMBTOOLS_OT_AttachSelectedToActive(GeoInputSettings, bpy.types.Operator):
    bl_idname  = "object.attach_selected_to_active_geo_input"
    bl_label   = "Attach Selected to Active"
    bl_description = "Adds a Geometry Input modifier (Object mode) to the active object for each other selected object"
    bl_options = {'REGISTER', 'UNDO'}

    relative_space:   BoolProperty(name="Relative Space",   default=True)
    as_instance:      BoolProperty(name="As Instance",      default=False)
    disable_emission: BoolProperty(name="Disable Emission", default=False)
    replace_original: BoolProperty(name="Replace Original", default=False)

    @classmethod
    def poll(cls, context):
        return context.active_object is not None and len(context.selected_objects) > 1

    def invoke(self, context, event):
        return context.window_manager.invoke_props_dialog(self)

    def draw(self, context):
        layout = self.layout
        self.draw_base(layout)
        layout.prop(self, "replace_original")

    def execute(self, context):
        active  = context.active_object
        sources = [o for o in context.selected_objects if o is not active]
        if not sources:
            self.report({'WARNING'}, "Select at least one other object alongside the active object.")
            return {'CANCELLED'}
        view3d = get_view3d_area(context)
        if not view3d:
            self.report({'ERROR'}, "No 3D Viewport found on screen.")
            return {'CANCELLED'}
        for src in sources:
            mod = add_geometry_input_modifier(context, active, view3d)
            if mod is None:
                self.report({'ERROR'}, "Failed to add modifier — try again.")
                return {'CANCELLED'}
            apply_socket_settings(mod, 0, src, self.relative_space, self.as_instance, self.replace_original)
            print(f"  → Geometry Input: '{src.name}' → '{active.name}'")
        if self.disable_emission:
            build_no_emission_gn_modifier(active, collect_materials_from_objects(sources))
        self.report({'INFO'}, f"Attached {len(sources)} object(s) to '{active.name}'.")
        return {'FINISHED'}


# ---------------------------------------------------------------------------
# Menu hooks
# ---------------------------------------------------------------------------

def draw_outliner_menu(self, context):
    self.layout.separator()
    self.layout.operator(DUMBTOOLS_OT_CopyCollectionsToObject.bl_idname, icon='OUTLINER_COLLECTION')
    self.layout.operator(DUMBTOOLS_OT_AddCollectionsToObjects.bl_idname,  icon='MODIFIER')

def draw_viewport_menu(self, context):
    self.layout.separator()
    self.layout.operator(DUMBTOOLS_OT_AddCollectionsToObjects.bl_idname,  icon='OUTLINER_COLLECTION')
    self.layout.operator(DUMBTOOLS_OT_AttachSelectedToActive.bl_idname,   icon='MODIFIER')


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
