# Tooltip: Generate Dust Puffs effects based on Footstep holds
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
    """Discover templates inside the chosen source collection."""
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

    return [{'root': o, 'objects': [o], 'mode': 'flat'} for o in objs]


# ─────────────────────────────────────────────────────────────
#  Image-sequence offset shifting
# ─────────────────────────────────────────────────────────────

def shift_material_image_offsets(obj, birth_frame, image_offset=0):
    if not hasattr(obj, 'material_slots'):
        return

    target_start = int(birth_frame) - 1 + image_offset
    copied_mesh = False

    for slot_idx, slot in enumerate(obj.material_slots):
        mat = slot.material
        if not mat or not mat.node_tree:
            continue
        nt = mat.node_tree

        seq_nodes = [
            n for n in nt.nodes
            if getattr(n, 'type', '') == 'TEX_IMAGE'
        ]

        action = None
        matching_fcs = []
        if nt.animation_data and nt.animation_data.action:
            action = nt.animation_data.action
            matching_fcs = [
                fc for fc in iter_fcurves(action)
                if 'image_user.frame_offset' in fc.data_path
                and len(fc.keyframe_points) >= 2
            ]

        if not seq_nodes and not matching_fcs:
            continue

        if obj.data and obj.data.users > 1 and not copied_mesh:
            obj.data = obj.data.copy()
            copied_mesh = True

        new_mat = mat.copy()
        obj.material_slots[slot_idx].material = new_mat
        new_nt = new_mat.node_tree

        shifted_nodes = set()

        if matching_fcs and new_nt.animation_data:
            slot_id = None
            if hasattr(new_nt.animation_data, 'action_slot') and new_nt.animation_data.action_slot:
                slot_id = new_nt.animation_data.action_slot.identifier

            new_nt.animation_data.action = new_nt.animation_data.action.copy()
            new_action = new_nt.animation_data.action

            if slot_id and hasattr(new_action, 'slots'):
                for s in new_action.slots:
                    if s.identifier == slot_id:
                        new_nt.animation_data.action_slot = s
                        break

            earliest = None
            offset_fcs = []
            import re
            for fc in iter_fcurves(new_action):
                if 'image_user.frame_offset' in fc.data_path and len(fc.keyframe_points) >= 2:
                    offset_fcs.append(fc)
                    first_t = fc.keyframe_points[0].co[0]
                    if earliest is None or first_t < earliest:
                        earliest = first_t

                    match = re.search(r'nodes\["([^"]+)"\]', fc.data_path)
                    if match:
                        shifted_nodes.add(match.group(1))

            if earliest is not None:
                delta = target_start - earliest
                for fc in offset_fcs:
                    for kp in fc.keyframe_points:
                        kp.co[0] += delta
                    fc.update()

                print(f"  Shifted image_user.frame_offset on '{new_mat.name}' "
                      f"by {delta} frames (first kf {earliest} -> {target_start})")

        new_seq_nodes = [
            n for n in new_nt.nodes
            if getattr(n, 'type', '') == 'TEX_IMAGE'
        ]

        for node in new_seq_nodes:
            if node.name not in shifted_nodes:
                if hasattr(node, 'image_user'):
                    node.image_user.frame_start = target_start
                    print(f"  Set frame_start={target_start} on image node '{node.name}' in '{new_mat.name}'")


# ─────────────────────────────────────────────────────────────
#  Animated flat-object repositioning
# ─────────────────────────────────────────────────────────────

_TRANSFORM_PATHS = ('location', 'rotation_euler', 'rotation_quaternion', 'scale')

def reposition_flat_animated_object(new_obj, src_obj, matrix_world, birth_frame, object_offset=0):
    if not new_obj.animation_data or not new_obj.animation_data.action:
        return False

    action_ref = new_obj.animation_data.action
    has_transforms = any(
        fc.data_path in _TRANSFORM_PATHS and len(fc.keyframe_points) >= 1
        for fc in iter_fcurves(action_ref)
    )
    if not has_transforms:
        return False

    new_obj.animation_data.action = action_ref.copy()
    action = new_obj.animation_data.action

    target_start = int(birth_frame) - 1 + object_offset
    hit_pos = matrix_world.translation.copy()
    hit_rot_euler = matrix_world.to_euler()

    earliest = None
    for fc in iter_fcurves(action):
        if fc.data_path in _TRANSFORM_PATHS and len(fc.keyframe_points) >= 1:
            t = fc.keyframe_points[0].co[0]
            if earliest is None or t < earliest:
                earliest = t

    if earliest is None:
        return False

    time_delta = target_start - earliest
    for fc in iter_fcurves(action):
        if fc.data_path in _TRANSFORM_PATHS:
            for kp in fc.keyframe_points:
                kp.co[0] += time_delta
            fc.update()

    loc_fcs = {}
    for fc in iter_fcurves(action):
        if fc.data_path == 'location':
            loc_fcs[fc.array_index] = fc

    if (len(loc_fcs) == 3
            and all(len(loc_fcs[i].keyframe_points) >= 2 for i in range(3))):

        src_hit_pos = mathutils.Vector((
            loc_fcs[0].keyframe_points[1].co[1],
            loc_fcs[1].keyframe_points[1].co[1],
            loc_fcs[2].keyframe_points[1].co[1],
        ))

        src_rot_mat = src_obj.rotation_euler.to_matrix()
        hit_rot_mat = hit_rot_euler.to_matrix()
        rot_delta_mat = hit_rot_mat @ src_rot_mat.inverted()

        num_kfs = min(len(loc_fcs[i].keyframe_points) for i in range(3))
        for kf_idx in range(num_kfs):
            kf_pos = mathutils.Vector((
                loc_fcs[0].keyframe_points[kf_idx].co[1],
                loc_fcs[1].keyframe_points[kf_idx].co[1],
                loc_fcs[2].keyframe_points[kf_idx].co[1],
            ))
            relative = kf_pos - src_hit_pos
            rotated_relative = rot_delta_mat @ relative
            new_pos = hit_pos + rotated_relative

            loc_fcs[0].keyframe_points[kf_idx].co[1] = new_pos.x
            loc_fcs[1].keyframe_points[kf_idx].co[1] = new_pos.y
            loc_fcs[2].keyframe_points[kf_idx].co[1] = new_pos.z

        for i in range(3):
            loc_fcs[i].update()

        print(f"  Repositioned '{new_obj.name}' location kfs "
              f"(2nd kf {src_hit_pos} -> {hit_pos})")

    rot_fcs = {}
    for fc in iter_fcurves(action):
        if fc.data_path == 'rotation_euler':
            rot_fcs[fc.array_index] = fc

    if rot_fcs:
        src_rot_euler_vec = mathutils.Vector(src_obj.rotation_euler)
        hit_rot_euler_vec = mathutils.Vector(hit_rot_euler)
        rot_euler_delta = hit_rot_euler_vec - src_rot_euler_vec

        for axis_idx, fc in rot_fcs.items():
            for kp in fc.keyframe_points:
                kp.co[1] += rot_euler_delta[axis_idx]
            fc.update()
    else:
        new_obj.rotation_euler = hit_rot_euler

    print(f"  Animated flat object '{new_obj.name}' placed at frame {int(birth_frame)}")
    return True


# ─────────────────────────────────────────────────────────────
#  Spawning (unified)
# ─────────────────────────────────────────────────────────────

def spawn_template(template, matrix_world, birth_frame, gen_col, vdb_offset=0, image_offset=0, alembic_offset=0, object_offset=0, hit_scale=1.0):
    root      = template['root']
    objects   = template['objects']
    is_flat   = template['mode'] == 'flat'

    old_to_new = {}
    for src_obj in objects:
        new_obj = src_obj.copy()
        if src_obj.type == 'VOLUME' and src_obj.data:
            new_obj.data = src_obj.data.copy()
        gen_col.objects.link(new_obj)
        old_to_new[src_obj] = new_obj

    for src_obj in objects:
        new_obj = old_to_new[src_obj]
        if src_obj.parent and src_obj.parent in old_to_new:
            new_obj.parent = old_to_new[src_obj.parent]
            new_obj.matrix_parent_inverse = src_obj.matrix_parent_inverse.copy()

    bpy.context.view_layer.update()

    new_root = old_to_new[root]

    if is_flat:
        new_root.parent = None

        if not reposition_flat_animated_object(new_root, root, matrix_world, birth_frame, object_offset):
            src_origin = root.matrix_world.translation.copy()
            hit_pos    = matrix_world.translation.copy()
            hit_rot    = matrix_world.to_euler()

            new_root.rotation_euler = hit_rot

            new_root.location = src_origin
            new_root.keyframe_insert(data_path="location", frame=int(birth_frame) - 1 + object_offset)

            new_root.location = hit_pos
            new_root.keyframe_insert(data_path="location", frame=int(birth_frame) + object_offset)

            if new_root.animation_data and new_root.animation_data.action:
                for fc in iter_fcurves(new_root.animation_data.action):
                    if fc.data_path == "location":
                        for kp in fc.keyframe_points:
                            kp.interpolation = 'CONSTANT'

            print(f"  Spawned static flat object '{new_root.name}' at frame {int(birth_frame) + object_offset} "
                  f"({src_origin} -> {hit_pos})")
    else:
        new_root.matrix_world = matrix_world

    for src_obj in objects:
        new_obj = old_to_new[src_obj]

        if src_obj.type == 'VOLUME' and new_obj.data:
            try:
                new_obj.data.frame_start = int(birth_frame - 1 + vdb_offset)
            except Exception:
                pass

            vis_frame = 0.0
            if new_obj.animation_data and new_obj.animation_data.action:
                new_obj.animation_data.action = new_obj.animation_data.action.copy()
                vis_frame = frame_at_visible(new_obj.animation_data.action)

            delta = birth_frame + vdb_offset - vis_frame
            if new_obj.animation_data and new_obj.animation_data.action:
                shift_action(new_obj.animation_data.action, delta)
            if (new_obj.data and new_obj.data.animation_data
                    and new_obj.data.animation_data.action):
                new_obj.data.animation_data.action = (
                    new_obj.data.animation_data.action.copy())
                shift_action(new_obj.data.animation_data.action, delta)

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
                                abc_delta = birth_frame + alembic_offset - orig_start
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
                            shift_action(act, birth_frame + alembic_offset - start_frame)
                            shifted = True

                if not shifted:
                    try:
                        new_cache.frame_offset = int(birth_frame + alembic_offset)
                        print(f"  Set cache frame_offset={int(birth_frame + alembic_offset)} on {new_obj.name} (no keyframes)")
                    except Exception as e:
                        print(f"  Warning: Could not set frame_offset on {new_obj.name}: {e}")

        if not is_flat and new_obj.animation_data and new_obj.animation_data.action:
            if src_obj.type != 'VOLUME':
                new_obj.animation_data.action = new_obj.animation_data.action.copy()
                earliest = None
                for fc in iter_fcurves(new_obj.animation_data.action):
                    if fc.data_path in _TRANSFORM_PATHS and len(fc.keyframe_points) >= 1:
                        t = fc.keyframe_points[0].co[0]
                        if earliest is None or t < earliest:
                            earliest = t
                if earliest is not None:
                    td = (int(birth_frame) - 1 + object_offset) - earliest
                    for fc in iter_fcurves(new_obj.animation_data.action):
                        if fc.data_path in _TRANSFORM_PATHS:
                            for kp in fc.keyframe_points:
                                kp.co[0] += td
                            fc.update()
                    print(f"  Time-shifted animation on '{new_obj.name}' by {td} frames")

    for src_obj in objects:
        new_obj = old_to_new[src_obj]
        shift_material_image_offsets(new_obj, birth_frame, image_offset)

    for src_obj in objects:
        new_obj = old_to_new[src_obj]
        if new_obj.type == 'EMPTY':
            new_obj.scale = (hit_scale, hit_scale, hit_scale)

    if not is_flat:
        print(f"  Spawned template (root='{new_root.name}', "
              f"{len(objects)} objs) at frame {int(birth_frame)}")


# ─────────────────────────────────────────────────────────────
#  Instance data extraction (Footsteps)
# ─────────────────────────────────────────────────────────────

def extract_footstep_data(context):
    active_obj = context.active_object
    if not active_obj or active_obj.type != 'ARMATURE':
        print("Error: Active object is not an Armature.")
        return []

    action = None
    if active_obj.animation_data:
        action = active_obj.animation_data.action
    if not action:
        print("Error: No action found on the active Armature.")
        return []

    selected_bones = context.selected_pose_bones
    if not selected_bones:
        print("Error: No pose bones selected.")
        return []
        
    bone_names = {b.name for b in selected_bones}
    unique_hits = {} # key: (bone_name, frame)

    for fc in iter_fcurves(action):
        if not fc.data_path.startswith("pose.bones["):
            continue
            
        try:
            # Extract bone name which is inside quotes
            bone_name = fc.data_path.split('"')[1]
        except IndexError:
            try:
                bone_name = fc.data_path.split("'")[1]
            except IndexError:
                continue
                
        if bone_name not in bone_names:
            continue

        kps = fc.keyframe_points
        for i in range(len(kps) - 1):
            kp1 = kps[i]
            kp2 = kps[i+1]
            
            if kp1.select_control_point:
                # Check for hold (same value)
                if abs(kp1.co[1] - kp2.co[1]) < 1e-4:
                    impact_frame = int(kp1.co[0])
                    unique_hits[(bone_name, impact_frame)] = True

    if not unique_hits:
        print("No selected hold keyframes found for the selected bones.")
        return []

    print(f"Extraction complete: Found {len(unique_hits)} unique footstep hits.")

    hits_data = []
    original_frame = context.scene.frame_current

    for bone_name, impact_frame in unique_hits.keys():
        context.scene.frame_set(impact_frame)
        context.view_layer.update()
        
        pbone = active_obj.pose.bones.get(bone_name)
        if pbone:
            mat = active_obj.matrix_world @ pbone.matrix
            hits_data.append((mat.copy(), float(impact_frame)))

    context.scene.frame_set(original_frame)
    return hits_data


# ─────────────────────────────────────────────────────────────
#  Operator with popup UI
# ─────────────────────────────────────────────────────────────

class DUMBTOOLS_OT_footstep_dust(bpy.types.Operator):
    """Generate Dust Puffs effects based on Footstep holds"""
    bl_idname = "dumbtools.footstep_dust"
    bl_label = "Dust Puffs from Footsteps"
    bl_options = {'REGISTER', 'UNDO'}

    def get_collections(self, context):
        """Return all collections as enum items for the dropdown."""
        items = [(col.name, col.name, "") for col in bpy.data.collections]
        if not items:
            items = [('NONE', '(No Collections)', '')]
        return items

    source_collection: bpy.props.EnumProperty(
        name="Source Collection",
        description="Collection containing footstep template sub-collections",
        items=get_collections,
    )

    vdb_offset: bpy.props.IntProperty(
        name="VDB Offset",
        description="Offset in frames for VDB volume sequence start",
        default=0,
    )

    image_offset: bpy.props.IntProperty(
        name="Image Sequence Offset",
        description="Offset in frames for material image sequences",
        default=-1,
    )

    alembic_offset: bpy.props.IntProperty(
        name="Alembic Offset",
        description="Offset in frames for Alembic cache timing",
        default=-2,
    )

    object_offset: bpy.props.IntProperty(
        name="Object Animation Offset",
        description="Offset in frames for object-level transform animations and snaps",
        default=-1,
    )

    hit_scale: bpy.props.FloatProperty(
        name="Scale",
        description="Scale amount to apply to all spawned Empties",
        default=1.0,
    )

    def invoke(self, context, event):
        scene = context.scene
        if hasattr(scene, 'fd_source_collection') and scene.fd_source_collection in bpy.data.collections:
            self.source_collection = scene.fd_source_collection
        elif "DustPuffs" in bpy.data.collections:
            self.source_collection = "DustPuffs"
            
        self.vdb_offset     = getattr(scene, 'fd_vdb_offset',     0)
        self.image_offset   = getattr(scene, 'fd_image_offset',  -1)
        self.alembic_offset = getattr(scene, 'fd_alembic_offset',-2)
        self.object_offset  = getattr(scene, 'fd_object_offset', -1)
        self.hit_scale      = getattr(scene, 'fd_hit_scale',     1.0)
        return context.window_manager.invoke_props_dialog(self, width=350)

    def draw(self, context):
        layout = self.layout
        layout.prop(self, "source_collection", icon='OUTLINER_COLLECTION')

        box = layout.box()
        box.label(text="Timing Offsets (Frames)", icon='TIME')
        box.prop(self, "vdb_offset", text="VDB Offset")
        box.prop(self, "image_offset", text="Image Sequence")
        box.prop(self, "alembic_offset", text="Alembic Offset")
        box.prop(self, "object_offset", text="Object Animation")
        layout.separator()
        layout.prop(self, "hit_scale", text="Scale")

    def execute(self, context):
        active_obj = context.active_object
        if not active_obj or active_obj.type != 'ARMATURE':
            self.report({'ERROR'}, "No active Armature selected.")
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

        footsteps = extract_footstep_data(context)
        if not footsteps:
            self.report({'WARNING'}, "No selected footstep holds found on the active Armature.")
            return {'CANCELLED'}

        gen_col = get_or_create_collection(f"FootstepDust_Generated_{active_obj.name}")

        original_frame = context.scene.frame_current

        for matrix, birth in footsteps:
            template = random.choice(templates)
            spawn_template(
                template,
                matrix,
                birth,
                gen_col,
                vdb_offset=self.vdb_offset,
                image_offset=self.image_offset,
                alembic_offset=self.alembic_offset,
                object_offset=self.object_offset,
                hit_scale=self.hit_scale,
            )

        context.scene.frame_set(original_frame)

        scene = context.scene
        scene.fd_source_collection = self.source_collection
        scene.fd_vdb_offset        = self.vdb_offset
        scene.fd_image_offset      = self.image_offset
        scene.fd_alembic_offset    = self.alembic_offset
        scene.fd_object_offset     = self.object_offset
        scene.fd_hit_scale         = self.hit_scale

        self.report({'INFO'}, f"Spawned {len(footsteps)} dust puffs from '{self.source_collection}'.")
        return {'FINISHED'}


# ─────────────────────────────────────────────────────────────
#  Registration & auto-invoke
# ─────────────────────────────────────────────────────────────

_SCENE_PROPS = [
    ('fd_source_collection', bpy.props.StringProperty(
        name="FD Source Collection", default="")),
    ('fd_vdb_offset', bpy.props.IntProperty(
        name="FD VDB Offset", default=0)),
    ('fd_image_offset', bpy.props.IntProperty(
        name="FD Image Offset", default=-1)),
    ('fd_alembic_offset', bpy.props.IntProperty(
        name="FD Alembic Offset", default=-2)),
    ('fd_object_offset', bpy.props.IntProperty(
        name="FD Object Offset", default=-1)),
    ('fd_hit_scale', bpy.props.FloatProperty(
        name="FD Hit Scale", default=1.0)),
]

def register():
    try:
        bpy.utils.register_class(DUMBTOOLS_OT_footstep_dust)
    except ValueError:
        bpy.utils.unregister_class(DUMBTOOLS_OT_footstep_dust)
        bpy.utils.register_class(DUMBTOOLS_OT_footstep_dust)
    for prop_name, prop_value in _SCENE_PROPS:
        setattr(bpy.types.Scene, prop_name, prop_value)

def unregister():
    try:
        bpy.utils.unregister_class(DUMBTOOLS_OT_footstep_dust)
    except RuntimeError:
        pass
    for prop_name, _ in _SCENE_PROPS:
        if hasattr(bpy.types.Scene, prop_name):
            delattr(bpy.types.Scene, prop_name)

register()
bpy.ops.dumbtools.footstep_dust('INVOKE_DEFAULT')
