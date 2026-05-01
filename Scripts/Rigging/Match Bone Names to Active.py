# Tooltip: Match bone names from the active armature onto the selected armature by hierarchy + position

import bpy
import mathutils
from bpy.props import (CollectionProperty, BoolProperty, IntProperty,
                       StringProperty, PointerProperty)
from bpy.types import Operator, Panel, PropertyGroup, UIList


# ─────────────────────────────────────────────────────────────────────────────
#  Matching algorithm
#  Strategy
#  ─────────
#  1. Walk the two armature trees in lockstep, starting from roots.
#  2. At each parent node, assign its ref-children to target-children by
#     nearest world-space head position (Hungarian-style greedy).
#  3. X-side preference: if a ref child is clearly positive-X and a target
#     child is negative-X (or vice versa), apply a large distance penalty so
#     left chains don't swap with right chains.
#  4. Recurse into the matched pairs.
#  Position is only used to resolve *which* child maps to *which* — hierarchy
#  is always the primary signal.
# ─────────────────────────────────────────────────────────────────────────────

_X_SIDE_THRESHOLD = 0.02   # metres — bones beyond ±this are considered "sided"
_X_SIDE_PENALTY   = 1000.0 # added to distance when X-sides disagree


def _bone_world_head(arm_obj, bone):
    """World-space rest-pose head position of a bone."""
    return arm_obj.matrix_world @ bone.head_local


def _x_side(world_pos):
    """Returns 'L', 'R', or None for bones near centre."""
    x = world_pos.x
    if x >  _X_SIDE_THRESHOLD:
        return 'L'
    if x < -_X_SIDE_THRESHOLD:
        return 'R'
    return None


def _assign_children(ref_arm, tgt_arm, ref_bones, tgt_bones, mapping, used_ref):
    """
    Greedily assign each tgt_bone in tgt_bones to the nearest ref_bone in
    ref_bones (by world position, with X-side penalty), then recurse.
    mapping: {tgt_bone_name: ref_bone_name}
    used_ref: set of already-claimed ref bone names
    """
    if not ref_bones or not tgt_bones:
        return

    # Pre-compute positions and sides
    ref_info = {b: (_bone_world_head(ref_arm, b), _x_side(_bone_world_head(ref_arm, b)))
                for b in ref_bones}
    tgt_info = {b: (_bone_world_head(tgt_arm, b), _x_side(_bone_world_head(tgt_arm, b)))
                for b in tgt_bones}

    claimed_ref = set()  # claimed within this call (subset of used_ref)

    for tgt_b in tgt_bones:
        tgt_pos, tgt_side = tgt_info[tgt_b]
        best_ref  = None
        best_cost = float('inf')

        for ref_b in ref_bones:
            if ref_b.name in used_ref or ref_b.name in claimed_ref:
                continue
            ref_pos, ref_side = ref_info[ref_b]
            dist = (tgt_pos - ref_pos).length

            # X-side penalty: disagree → add large cost
            if tgt_side and ref_side and tgt_side != ref_side:
                dist += _X_SIDE_PENALTY

            if dist < best_cost:
                best_cost = dist
                best_ref  = ref_b

        if best_ref:
            mapping[tgt_b.name] = best_ref.name
            claimed_ref.add(best_ref.name)
            used_ref.add(best_ref.name)

    # Recurse: for each matched pair descend into their children
    for tgt_b in tgt_bones:
        ref_name = mapping.get(tgt_b.name)
        if not ref_name:
            continue
        ref_b = ref_arm.data.bones.get(ref_name)
        if ref_b is None:
            continue
        ref_ch = list(ref_b.children)
        tgt_ch = list(tgt_b.children)
        if ref_ch and tgt_ch:
            _assign_children(ref_arm, tgt_arm, ref_ch, tgt_ch, mapping, used_ref)


def build_mapping(ref_arm, tgt_arm):
    """
    Returns {tgt_bone_name: ref_bone_name} for the full skeleton.
    """
    mapping  = {}
    used_ref = set()

    ref_roots = [b for b in ref_arm.data.bones if b.parent is None]
    tgt_roots = [b for b in tgt_arm.data.bones if b.parent is None]

    _assign_children(ref_arm, tgt_arm, ref_roots, tgt_roots, mapping, used_ref)
    return mapping


def apply_mapping(tgt_arm, mapping):
    """
    Rename bones in tgt_arm according to mapping {old_name: new_name}.
    Two-phase to avoid collision when swapping names.
    """
    arm_data = tgt_arm.data
    TEMP = "__DTMBN_TMP__"

    # Phase 1 — move to temp names
    temp_map = {}
    for old, new in mapping.items():
        if old == new:
            continue
        if old in arm_data.bones:
            tmp = TEMP + old
            arm_data.bones[old].name = tmp
            temp_map[tmp] = new

    # Phase 2 — assign final names
    failed = []
    for tmp, new in temp_map.items():
        if tmp in arm_data.bones:
            try:
                arm_data.bones[tmp].name = new
            except Exception as e:
                failed.append(f"{tmp} → {new}: {e}")

    return failed


# ─────────────────────────────────────────────────────────────────────────────
#  Property / UIList for the preview dialog
# ─────────────────────────────────────────────────────────────────────────────

class MatchBonePair(PropertyGroup):
    tgt_name: StringProperty()
    ref_name: StringProperty()


class MATCHBN_UL_pairs(UIList):
    def draw_item(self, context, layout, data, item, icon,
                  active_data, active_propname, index):
        row = layout.row(align=True)
        row.label(text=item.tgt_name, icon='BONE_DATA')
        row.label(text="→")
        row.label(text=item.ref_name)


# ─────────────────────────────────────────────────────────────────────────────
#  Operator — build mapping and show preview dialog
# ─────────────────────────────────────────────────────────────────────────────

class MATCHBN_OT_match(Operator):
    """Match bone names from Active onto Selected armature by hierarchy + position.
Active = reference (name donor). Selected (non-active) = target to be renamed."""
    bl_idname  = "matchbn.match_bones"
    bl_label   = "Match Bone Names to Active"
    bl_options = {'REGISTER', 'UNDO'}

    # Populated in invoke, consumed in execute
    _mapping: dict = {}

    @classmethod
    def poll(cls, context):
        objs = context.selected_objects
        active = context.active_object
        if not active or active.type != 'ARMATURE':
            return False
        others = [o for o in objs if o != active and o.type == 'ARMATURE']
        return len(others) >= 1

    def invoke(self, context, event):
        active  = context.active_object
        targets = [o for o in context.selected_objects
                   if o != active and o.type == 'ARMATURE']
        tgt_arm = targets[0]

        # Build mapping
        mapping = build_mapping(active, tgt_arm)
        MATCHBN_OT_match._mapping = mapping

        # Populate the scene list for the UIList
        scn = context.scene
        scn.matchbn_pairs.clear()
        for tgt_name, ref_name in sorted(mapping.items()):
            item = scn.matchbn_pairs.add()
            item.tgt_name = tgt_name
            item.ref_name = ref_name

        scn.matchbn_pairs_index = 0
        scn.matchbn_tgt_name    = tgt_arm.name

        return context.window_manager.invoke_props_dialog(self, width=480)

    def draw(self, context):
        layout = self.layout
        scn    = context.scene

        tgt_name = scn.matchbn_tgt_name
        ref_name = context.active_object.name

        layout.label(
            text=f"Reference: '{ref_name}'  →  will rename: '{tgt_name}'",
            icon='ARMATURE_DATA'
        )
        layout.label(
            text=f"{len(scn.matchbn_pairs)} bone(s) matched  "
                 f"(target name  →  new name from reference)",
            icon='INFO'
        )
        layout.separator()
        layout.template_list(
            "MATCHBN_UL_pairs", "",
            scn, "matchbn_pairs",
            scn, "matchbn_pairs_index",
            rows=12,
        )
        layout.separator()
        layout.label(text="Click OK to apply. This operation supports Undo (Ctrl+Z).")

    def execute(self, context):
        scn = context.scene

        tgt_name = scn.matchbn_tgt_name
        tgt_arm  = bpy.data.objects.get(tgt_name)
        if tgt_arm is None:
            self.report({'ERROR'}, f"Target armature '{tgt_name}' not found.")
            return {'CANCELLED'}

        mapping = MATCHBN_OT_match._mapping
        if not mapping:
            self.report({'ERROR'}, "No mapping built — run again.")
            return {'CANCELLED'}

        failed = apply_mapping(tgt_arm, mapping)

        msg = f"Renamed {len(mapping) - len(failed)} / {len(mapping)} bones on '{tgt_name}'."
        if failed:
            msg += f"  {len(failed)} failed (see console)."
            for f in failed:
                print(f"[MatchBoneNames] FAILED: {f}")
            self.report({'WARNING'}, msg)
        else:
            self.report({'INFO'}, msg)

        return {'FINISHED'}


# ─────────────────────────────────────────────────────────────────────────────
#  Register / Unregister
# ─────────────────────────────────────────────────────────────────────────────

_classes = (
    MatchBonePair,
    MATCHBN_UL_pairs,
    MATCHBN_OT_match,
)


def register():
    for cls in _classes:
        try:
            bpy.utils.register_class(cls)
        except Exception:
            bpy.utils.unregister_class(cls)
            bpy.utils.register_class(cls)

    if not hasattr(bpy.types.Scene, 'matchbn_pairs'):
        bpy.types.Scene.matchbn_pairs = CollectionProperty(type=MatchBonePair)
    if not hasattr(bpy.types.Scene, 'matchbn_pairs_index'):
        bpy.types.Scene.matchbn_pairs_index = IntProperty()
    if not hasattr(bpy.types.Scene, 'matchbn_tgt_name'):
        bpy.types.Scene.matchbn_tgt_name = StringProperty()


def unregister():
    for cls in reversed(_classes):
        try:
            bpy.utils.unregister_class(cls)
        except Exception:
            pass
    for attr in ('matchbn_pairs', 'matchbn_pairs_index', 'matchbn_tgt_name'):
        try:
            delattr(bpy.types.Scene, attr)
        except Exception:
            pass


register()
bpy.ops.matchbn.match_bones('INVOKE_DEFAULT')
