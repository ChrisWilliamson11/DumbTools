# Tooltip: Generate Bullet Hit effects based on Geometry Nodes instance data
import bpy
import random
import mathutils
import math

def get_or_create_collection(name):
    if name in bpy.data.collections:
        return bpy.data.collections[name]
    else:
        new_col = bpy.data.collections.new(name)
        bpy.context.scene.collection.children.link(new_col)
        return new_col

def iter_fcurves(action):
    if not action: return
    if hasattr(action, "fcurves") and action.fcurves:
        for fc in action.fcurves: yield fc
    if hasattr(action, "layers"):
        for layer in action.layers:
            if hasattr(layer, "strips"):
                for strip in layer.strips:
                    if hasattr(strip, "channelbags"):
                        for bag in strip.channelbags:
                            if hasattr(bag, "fcurves"):
                                for fc in bag.fcurves: yield fc
                    if hasattr(strip, "fcurves"):
                        for fc in strip.fcurves: yield fc
                    elif hasattr(strip, "channels"):
                         for fc in strip.channels: yield fc

def frame_at_visible(action):
    for fc in iter_fcurves(action):
        if fc.data_path.endswith("hide_viewport") or fc.data_path.endswith("hide_render"):
            for kp in fc.keyframe_points:
                if kp.co[1] < 0.5: return kp.co[0]
    return 0.0

def shift_action(action, delta):
    if not action: return
    for fc in iter_fcurves(action):
        for kp in fc.keyframe_points: kp.co[0] += delta
        fc.update()


# ─────────────────────────────────────────────────────────────
#  Template discovery
# ─────────────────────────────────────────────────────────────

def collect_descendants(root, obj_set):
    """Recursively collect root + all descendants that are within obj_set."""
    result = [root]
    for child in root.children:
        if child in obj_set:
            result.extend(collect_descendants(child, obj_set))
    return result


def find_templates(source_col_name):
    """Discover templates inside the chosen source collection.

    Three discovery modes (checked in priority order):

    1. **Sub-collections** – each child collection is a template.
       The root is its Empty (preferred) or first parentless object.

    2. **Parented hierarchies** – no sub-collections, but objects have
       parent relationships inside the collection.  Each root object
       (+ its descendants) is a template.

    3. **Flat objects** – no sub-collections, no hierarchy.
       Every individual object is its own simple template.

    Returns a list of dicts:
        {
            'root':    <object to position at the hit>,
            'objects': [<all objects to duplicate, incl. root>],
            'mode':    'collection' | 'hierarchy' | 'flat',
        }
    """
    if source_col_name not in bpy.data.collections:
        return []

    source_col = bpy.data.collections[source_col_name]

    # ── Mode 1: sub-collections ──────────────────────────────
    if len(source_col.children) > 0:
        templates = []
        for child_col in source_col.children:
            objs = list(child_col.objects)
            if not objs:
                continue
            obj_set = set(objs)
            roots = [o for o in objs if o.parent is None or o.parent not in obj_set]
            if not roots:
                continue
            # Prefer an Empty as the root (most common setup)
            root = next((r for r in roots if r.type == 'EMPTY'), roots[0])
            templates.append({
                'root': root,
                'objects': objs,
                'mode': 'collection',
            })
        return templates

    # ── Modes 2 & 3: direct objects ──────────────────────────
    objs = list(source_col.objects)
    if not objs:
        return []

    obj_set = set(objs)
    has_hierarchy = any(o.parent is not None and o.parent in obj_set for o in objs)

    if has_hierarchy:
        # Mode 2: each root + descendants = one template
        roots = [o for o in objs if o.parent is None or o.parent not in obj_set]
        templates = []
        for root in roots:
            group = collect_descendants(root, obj_set)
            templates.append({
                'root': root,
                'objects': group,
                'mode': 'hierarchy',
            })
        return templates

    # Mode 3: every object is its own template
    return [{'root': o, 'objects': [o], 'mode': 'flat'} for o in objs]


# ─────────────────────────────────────────────────────────────
#  Spawning (unified)
# ─────────────────────────────────────────────────────────────

def spawn_template(template, matrix_world, birth_frame, gen_col):
    """Duplicate a template's objects and place/animate them at the bullet hit.

    - *collection* / *hierarchy* modes: duplicate the whole hierarchy,
      position the root, and shift timing on any VDB / cached-Alembic children.
    - *flat* mode: duplicate the single object and animate its location
      from its current position to the hit over 1 frame.
    """
    root      = template['root']
    objects   = template['objects']
    is_flat   = template['mode'] == 'flat'

    # ── 1. Duplicate all objects ─────────────────────────────
    old_to_new = {}
    for src_obj in objects:
        new_obj = src_obj.copy()
        # Deep-copy VDB data so frame_start is independent
        if src_obj.type == 'VOLUME' and src_obj.data:
            new_obj.data = src_obj.data.copy()
        gen_col.objects.link(new_obj)
        old_to_new[src_obj] = new_obj

    # ── 2. Restore parent relationships ──────────────────────
    for src_obj in objects:
        new_obj = old_to_new[src_obj]
        if src_obj.parent and src_obj.parent in old_to_new:
            new_obj.parent = old_to_new[src_obj.parent]
            new_obj.matrix_parent_inverse = src_obj.matrix_parent_inverse.copy()

    bpy.context.view_layer.update()

    new_root = old_to_new[root]

    # ── 3. Position the root ─────────────────────────────────
    if is_flat:
        # Animate: source position at birth-1, hit position at birth
        src_origin = root.matrix_world.translation.copy()
        hit_pos    = matrix_world.translation.copy()
        hit_rot    = matrix_world.to_euler()

        new_root.parent = None
        new_root.rotation_euler = hit_rot

        # Key source position one frame before
        new_root.location = src_origin
        new_root.keyframe_insert(data_path="location", frame=int(birth_frame) - 1)

        # Key hit position at birth frame
        new_root.location = hit_pos
        new_root.keyframe_insert(data_path="location", frame=int(birth_frame))

        # CONSTANT interpolation so it snaps
        if new_root.animation_data and new_root.animation_data.action:
            for fc in iter_fcurves(new_root.animation_data.action):
                if fc.data_path == "location":
                    for kp in fc.keyframe_points:
                        kp.interpolation = 'CONSTANT'

        print(f"  Spawned flat object '{new_root.name}' at frame {int(birth_frame)} "
              f"({src_origin} -> {hit_pos})")
    else:
        # Hierarchical: just place the root
        new_root.matrix_world = matrix_world

    # ── 4. Handle timing for VDB / cached-Alembic children ───
    for src_obj in objects:
        new_obj = old_to_new[src_obj]

        # --- VDB timing ---
        if src_obj.type == 'VOLUME' and new_obj.data:
            try:
                new_obj.data.frame_start = int(birth_frame - 1)
            except Exception:
                pass

            # Visibility animation shift
            vis_frame = 0.0
            if new_obj.animation_data and new_obj.animation_data.action:
                new_obj.animation_data.action = new_obj.animation_data.action.copy()
                vis_frame = frame_at_visible(new_obj.animation_data.action)

            delta = birth_frame - vis_frame
            if new_obj.animation_data and new_obj.animation_data.action:
                shift_action(new_obj.animation_data.action, delta)
            if (new_obj.data and new_obj.data.animation_data
                    and new_obj.data.animation_data.action):
                new_obj.data.animation_data.action = (
                    new_obj.data.animation_data.action.copy())
                shift_action(new_obj.data.animation_data.action, delta)

        # --- Alembic cache timing ---
        elif src_obj.type in ('MESH', 'POINTCLOUD'):
            abc_mod = next(
                (m for m in new_obj.modifiers if m.type == 'MESH_SEQUENCE_CACHE'),
                None,
            )
            if abc_mod and abc_mod.cache_file:
                abc_mod.cache_file = abc_mod.cache_file.copy()
                new_cache = abc_mod.cache_file

                shifted = False
                if new_cache.animation_data and new_cache.animation_data.action:
                    new_cache.animation_data.action = (
                        new_cache.animation_data.action.copy())
                    act = new_cache.animation_data.action

                    for fc in iter_fcurves(act):
                        dp = fc.data_path
                        if dp == "frame" or dp.endswith(".frame"):
                            if len(fc.keyframe_points) >= 1:
                                orig_start = fc.keyframe_points[0].co[0]
                                abc_delta = birth_frame - orig_start
                                for kp in fc.keyframe_points:
                                    kp.co[0] += abc_delta
                                fc.update()
                                shifted = True

                    if not shifted:
                        start_frame = min(
                            (fc.keyframe_points[0].co[0]
                             for fc in iter_fcurves(act)
                             if fc.data_path.endswith("frame")
                             and len(fc.keyframe_points) > 0),
                            default=None,
                        )
                        if start_frame is not None:
                            shift_action(act, birth_frame - start_frame)
                            shifted = True

                if not shifted:
                    print(f"  Warning: No cache keyframes for {new_obj.name}")

    if not is_flat:
        print(f"  Spawned template (root='{new_root.name}', "
              f"{len(objects)} objs) at frame {int(birth_frame)}")


# ─────────────────────────────────────────────────────────────
#  Instance data extraction (unchanged)
# ─────────────────────────────────────────────────────────────

def extract_instance_data(obj):
    depsgraph = bpy.context.evaluated_depsgraph_get()
    eval_obj = obj.evaluated_get(depsgraph)
    mesh = eval_obj.data

    unique_hits = {}
    attrs = mesh.attributes

    attr_filter = "IBulletHit"
    attr_birth = "BirthFrame"
    attr_pos = "IPosition"
    attr_rot = "IRotation"

    if all(a in attrs for a in [attr_filter, attr_birth, attr_pos, attr_rot]):
        f_data = attrs[attr_filter].data
        b_data = attrs[attr_birth].data
        p_data = attrs[attr_pos].data
        r_data = attrs[attr_rot].data

        print(f"Scanning realized mesh with {len(mesh.vertices)} vertices...")

        for i in range(len(mesh.vertices)):
            if f_data[i].value:
                birth = float(b_data[i].value)
                pos_vec = p_data[i].vector
                rot_vec = r_data[i].vector

                key = (birth, round(pos_vec.x, 4), round(pos_vec.y, 4), round(pos_vec.z, 4))

                if key not in unique_hits:
                    mat = mathutils.Matrix.Translation(pos_vec)
                    mat @= mathutils.Euler(rot_vec).to_matrix().to_4x4()
                    unique_hits[key] = (mat, birth)

        print(f"Extraction complete: Found {len(unique_hits)} unique bullet hits.")
    else:
        missing = [a for a in [attr_filter, attr_birth, attr_pos, attr_rot] if a not in attrs]
        print(f"Error: Missing attributes on {obj.name}: {missing}")

    return list(unique_hits.values())


# ─────────────────────────────────────────────────────────────
#  Operator with popup UI
# ─────────────────────────────────────────────────────────────

class DUMBTOOLS_OT_bullet_hits(bpy.types.Operator):
    """Generate Bullet Hit effects from Geometry Nodes instance data"""
    bl_idname = "dumbtools.bullet_hits"
    bl_label = "Bullet Hits"
    bl_options = {'REGISTER', 'UNDO'}

    def get_collections(self, context):
        """Return all collections as enum items for the dropdown."""
        items = [(col.name, col.name, "") for col in bpy.data.collections]
        if not items:
            items = [('NONE', '(No Collections)', '')]
        return items

    source_collection: bpy.props.EnumProperty(
        name="Source Collection",
        description="Collection containing bullet-hit template sub-collections",
        items=get_collections,
    )

    def invoke(self, context, event):
        # Try to default to "BulletHits" if it exists
        if "BulletHits" in bpy.data.collections:
            self.source_collection = "BulletHits"
        return context.window_manager.invoke_props_dialog(self, width=350)

    def draw(self, context):
        layout = self.layout
        layout.prop(self, "source_collection", icon='OUTLINER_COLLECTION')

    def execute(self, context):
        active_obj = context.active_object
        if not active_obj:
            self.report({'ERROR'}, "No active object selected.")
            return {'CANCELLED'}

        if self.source_collection == 'NONE':
            self.report({'ERROR'}, "No collection selected.")
            return {'CANCELLED'}

        templates = find_templates(self.source_collection)
        if not templates:
            self.report({'ERROR'},
                        f"No valid templates found in '{self.source_collection}'. "
                        f"Needs sub-collections, parented hierarchies, or objects.")
            return {'CANCELLED'}

        bullet_hits = extract_instance_data(active_obj)
        if not bullet_hits:
            self.report({'WARNING'}, "No bullet-hit instances found on the active object.")
            return {'CANCELLED'}

        gen_col = get_or_create_collection(f"BulletHits_Generated_{active_obj.name}")

        # Remember current frame to restore later
        original_frame = context.scene.frame_current

        for matrix, birth in bullet_hits:
            template = random.choice(templates)
            spawn_template(template, matrix, birth, gen_col)

        # Restore original frame
        context.scene.frame_set(original_frame)

        self.report({'INFO'}, f"Spawned {len(bullet_hits)} bullet hits from '{self.source_collection}'.")
        return {'FINISHED'}


# ─────────────────────────────────────────────────────────────
#  Registration & auto-invoke
# ─────────────────────────────────────────────────────────────

def register():
    try:
        bpy.utils.register_class(DUMBTOOLS_OT_bullet_hits)
    except ValueError:
        bpy.utils.unregister_class(DUMBTOOLS_OT_bullet_hits)
        bpy.utils.register_class(DUMBTOOLS_OT_bullet_hits)

def unregister():
    try:
        bpy.utils.unregister_class(DUMBTOOLS_OT_bullet_hits)
    except RuntimeError:
        pass

register()
bpy.ops.dumbtools.bullet_hits('INVOKE_DEFAULT')
