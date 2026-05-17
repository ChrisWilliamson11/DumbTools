# Tooltip: Outliner collection right-click operators to select Meshes, Volumes, or Alembic objects by name group
import bpy
import re


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

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


def collect_all_objects(collection):
    """Recursively collect all objects from a collection and its children."""
    return list(collection.all_objects)


def has_mesh_sequence_cache(obj):
    """Return True if obj has a MeshSequenceCache modifier."""
    for mod in obj.modifiers:
        if mod.type == 'MESH_SEQUENCE_CACHE':
            return True
    return False


def get_meshes(objects):
    """Return mesh objects that do NOT have a MeshSequenceCache modifier."""
    return [o for o in objects if o.type == 'MESH' and not has_mesh_sequence_cache(o)]


def get_alembic(objects):
    """Return objects that have a MeshSequenceCache modifier."""
    return [o for o in objects if hasattr(o, 'modifiers') and has_mesh_sequence_cache(o)]


def get_volumes(objects):
    """Return volume objects."""
    return [o for o in objects if o.type == 'VOLUME']


# Module-level stash for passing data from the popup-spawning operator
# to the popup's sub-operators (can't set arbitrary attrs on WindowManager RNA)
_selection_stash = {}

# Pattern to strip trailing numeric suffixes like .001, .002, _001, -001
_SUFFIX_RE = re.compile(r'[\._\-]\d+$')


def strip_numeric_suffix(name):
    """Strip trailing .NNN / _NNN / -NNN suffix from a name."""
    return _SUFFIX_RE.sub('', name)


def group_by_base_name(objects):
    """
    Group objects by their base name (with numeric suffix stripped).
    Returns a dict: {base_name: [obj, ...]}
    Only creates groups where at least 2 objects share a base name.
    Ungrouped objects (unique names) go into a special None key.
    """
    groups = {}
    for obj in objects:
        base = strip_numeric_suffix(obj.name)
        groups.setdefault(base, []).append(obj)

    return groups


def select_objects(context, objects):
    """Select the given objects and deselect everything else."""
    # Deselect all first
    for obj in context.view_layer.objects:
        obj.select_set(False)
    for obj in objects:
        try:
            obj.select_set(True)
        except RuntimeError:
            pass  # Object may not be in view layer
    if objects:
        try:
            context.view_layer.objects.active = objects[0]
        except RuntimeError:
            pass


# ---------------------------------------------------------------------------
# Operator to select a specific named group (called from popup)
# ---------------------------------------------------------------------------

class DUMBTOOLS_OT_SelectNameGroup(bpy.types.Operator):
    """Select objects belonging to a specific name group"""
    bl_idname = "outliner.select_name_group"
    bl_label = "Select Name Group"
    bl_options = {'REGISTER', 'UNDO', 'INTERNAL'}

    group_name: bpy.props.StringProperty(name="Group Name")

    def execute(self, context):
        obj_names = _selection_stash.get(self.group_name, [])
        if not obj_names:
            self.report({'WARNING'}, f"No objects found for group '{self.group_name}'")
            return {'CANCELLED'}

        objects = [bpy.data.objects.get(n) for n in obj_names]
        objects = [o for o in objects if o is not None]
        select_objects(context, objects)
        self.report({'INFO'}, f"Selected {len(objects)} object(s) in group '{self.group_name}'")
        return {'FINISHED'}


# ---------------------------------------------------------------------------
# Operator to select ALL matched objects (no grouping)
# ---------------------------------------------------------------------------

class DUMBTOOLS_OT_SelectAllFiltered(bpy.types.Operator):
    """Select all objects of the filtered type"""
    bl_idname = "outliner.select_all_filtered"
    bl_label = "Select All"
    bl_options = {'REGISTER', 'UNDO', 'INTERNAL'}

    def execute(self, context):
        obj_names = _selection_stash.get('__all__', [])
        if not obj_names:
            self.report({'WARNING'}, "No objects found")
            return {'CANCELLED'}

        objects = [bpy.data.objects.get(n) for n in obj_names]
        objects = [o for o in objects if o is not None]
        select_objects(context, objects)
        self.report({'INFO'}, f"Selected {len(objects)} object(s)")
        return {'FINISHED'}


# ---------------------------------------------------------------------------
# Core selection logic shared by all three operators
# ---------------------------------------------------------------------------

def do_filtered_select(operator, context, filter_func, type_label):
    """
    Core logic:
    1. Collect objects from selected collections
    2. Filter by type
    3. Group by base name
    4. If multiple groups with >1 member exist, show popup
    5. Otherwise select all
    """
    cols = get_outliner_collections(context)
    if not cols:
        operator.report({'WARNING'}, "No collections selected in the Outliner.")
        return {'CANCELLED'}

    # Gather all objects from all selected collections
    all_objects = []
    seen = set()
    for col in cols:
        for obj in collect_all_objects(col):
            if obj.name not in seen:
                seen.add(obj.name)
                all_objects.append(obj)

    # Apply type filter
    filtered = filter_func(all_objects)
    if not filtered:
        operator.report({'WARNING'}, f"No {type_label} objects found in selected collection(s).")
        return {'CANCELLED'}

    # Group by base name
    groups = group_by_base_name(filtered)

    # Identify groups that have more than one member (actual "sets")
    multi_groups = {k: v for k, v in groups.items() if len(v) > 1}

    if len(multi_groups) <= 1:
        # Zero or one group — just select everything
        select_objects(context, filtered)
        operator.report({'INFO'}, f"Selected {len(filtered)} {type_label} object(s).")
        return {'FINISHED'}

    # Multiple name groups exist — show popup to choose
    # Stash data on window manager so the popup operators can read it
    _selection_stash.clear()
    _selection_stash['__all__'] = [o.name for o in filtered]
    for base_name, objs in multi_groups.items():
        _selection_stash[base_name] = [o.name for o in objs]

    def draw_popup(self_menu, context):
        layout = self_menu.layout
        layout.label(text="Multiple name groups found:")
        layout.separator()

        # "Select All" option
        op = layout.operator(
            DUMBTOOLS_OT_SelectAllFiltered.bl_idname,
            text=f"All ({len(filtered)})",
            icon='CHECKBOX_HLT',
        )

        layout.separator()

        # One entry per named group, sorted alphabetically
        for base_name in sorted(multi_groups.keys()):
            objs = multi_groups[base_name]
            op = layout.operator(
                DUMBTOOLS_OT_SelectNameGroup.bl_idname,
                text=f"{base_name}  ({len(objs)})",
                icon='OBJECT_DATA',
            )
            op.group_name = base_name

    context.window_manager.popup_menu(
        draw_popup,
        title=f"Select {type_label}",
        icon='RESTRICT_SELECT_OFF',
    )
    return {'FINISHED'}


# ---------------------------------------------------------------------------
# Operators — Select Meshes / Select Alembic / Select Volumes
# ---------------------------------------------------------------------------

class DUMBTOOLS_OT_SelectMeshes(bpy.types.Operator):
    """Select mesh objects in this collection (excludes Alembic/MeshSequenceCache)"""
    bl_idname = "outliner.select_meshes"
    bl_label = "Select Meshes"
    bl_options = {'REGISTER', 'UNDO'}

    @classmethod
    def poll(cls, context):
        return any(a.type == 'OUTLINER' for a in context.screen.areas)

    def execute(self, context):
        return do_filtered_select(self, context, get_meshes, "Mesh")


class DUMBTOOLS_OT_SelectAlembic(bpy.types.Operator):
    """Select objects with a MeshSequenceCache modifier (Alembic)"""
    bl_idname = "outliner.select_alembic"
    bl_label = "Select Alembic"
    bl_options = {'REGISTER', 'UNDO'}

    @classmethod
    def poll(cls, context):
        return any(a.type == 'OUTLINER' for a in context.screen.areas)

    def execute(self, context):
        return do_filtered_select(self, context, get_alembic, "Alembic")


class DUMBTOOLS_OT_SelectVolumes(bpy.types.Operator):
    """Select volume objects in this collection"""
    bl_idname = "outliner.select_volumes"
    bl_label = "Select Volumes"
    bl_options = {'REGISTER', 'UNDO'}

    @classmethod
    def poll(cls, context):
        return any(a.type == 'OUTLINER' for a in context.screen.areas)

    def execute(self, context):
        return do_filtered_select(self, context, get_volumes, "Volume")


# ---------------------------------------------------------------------------
# Menu hook
# ---------------------------------------------------------------------------

def draw_outliner_collection_menu(self, context):
    self.layout.separator()
    self.layout.operator(DUMBTOOLS_OT_SelectMeshes.bl_idname, icon='MESH_DATA')
    self.layout.operator(DUMBTOOLS_OT_SelectVolumes.bl_idname, icon='VOLUME_DATA')
    self.layout.operator(DUMBTOOLS_OT_SelectAlembic.bl_idname, icon='FILE_CACHE')


# ---------------------------------------------------------------------------
# Registration
# ---------------------------------------------------------------------------

_classes = (
    DUMBTOOLS_OT_SelectNameGroup,
    DUMBTOOLS_OT_SelectAllFiltered,
    DUMBTOOLS_OT_SelectMeshes,
    DUMBTOOLS_OT_SelectAlembic,
    DUMBTOOLS_OT_SelectVolumes,
)


def register():
    for cls in _classes:
        try:
            bpy.utils.unregister_class(cls)
        except Exception:
            pass
    for cls in _classes:
        bpy.utils.register_class(cls)
    bpy.types.OUTLINER_MT_collection.append(draw_outliner_collection_menu)


def unregister():
    bpy.types.OUTLINER_MT_collection.remove(draw_outliner_collection_menu)
    for cls in reversed(_classes):
        if cls.is_registered:
            bpy.utils.unregister_class(cls)


register()
