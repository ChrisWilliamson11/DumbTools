# Tooltip: Batch retarget multiple FBX mocap files onto a target rig via constraint bake + NLA

import bpy
import os
from bpy.props import StringProperty, PointerProperty, CollectionProperty
from bpy.types import Operator, Panel, PropertyGroup
from bpy.types import OperatorFileListElement


# ─────────────────────────────────────────────────────────────────────────────
#  Constraint snapshot / restore
#  The bake operator clears constraints from baked bones. We snapshot them
#  before the loop and restore after each clip so the next clip's import
#  drives the target rig correctly.
# ─────────────────────────────────────────────────────────────────────────────

def _read_constraint_props(c):
    """Extract serialisable data from a single constraint."""
    d = {
        'type': c.type,
        'name': c.name,
        'influence': c.influence,
        'mute': c.mute,
        'show_expanded': getattr(c, 'show_expanded', True),
    }
    # Object/subtarget reference
    if hasattr(c, 'target') and c.target is not None:
        d['target'] = c.target.name
    if hasattr(c, 'subtarget'):
        d['subtarget'] = c.subtarget
    # Space settings
    for attr in ('target_space', 'owner_space', 'mix_mode', 'use_offset',
                 'chain_count', 'iterations', 'use_stretch', 'use_tail',
                 'head_tail', 'influence'):
        if hasattr(c, attr):
            try:
                d[attr] = getattr(c, attr)
            except Exception:
                pass
    return d


def snapshot_constraints(arm_obj):
    """Return {bone_name: [constraint_data, ...]} for all pose bones."""
    snap = {}
    for pbone in arm_obj.pose.bones:
        clist = [_read_constraint_props(c) for c in pbone.constraints]
        if clist:
            snap[pbone.name] = clist
    return snap


def restore_constraints(arm_obj, snapshot):
    """Re-apply constraints from a snapshot dict."""
    # Ensure we have an active object in object mode before touching constraints
    if bpy.context.object is None:
        arm_obj.select_set(True)
        bpy.context.view_layer.objects.active = arm_obj
    if bpy.context.object and bpy.context.object.mode != 'OBJECT':
        bpy.ops.object.mode_set(mode='OBJECT')

    for bone_name, clist in snapshot.items():
        pbone = arm_obj.pose.bones.get(bone_name)
        if pbone is None:
            continue
        # Clear whatever the bake left behind
        for c in reversed(list(pbone.constraints)):
            pbone.constraints.remove(c)
        # Re-create
        for d in clist:
            try:
                c = pbone.constraints.new(type=d['type'])
                c.name = d['name']
                c.influence = d.get('influence', 1.0)
                c.mute = d.get('mute', False)
                if hasattr(c, 'show_expanded'):
                    c.show_expanded = d.get('show_expanded', True)
                # Restore target reference
                if 'target' in d and d['target']:
                    obj = bpy.data.objects.get(d['target'])
                    if obj and hasattr(c, 'target'):
                        c.target = obj
                if 'subtarget' in d and hasattr(c, 'subtarget'):
                    c.subtarget = d['subtarget']
                # Restore remaining attrs
                for attr, val in d.items():
                    if attr in ('type', 'name', 'influence', 'mute',
                                'show_expanded', 'target', 'subtarget'):
                        continue
                    if hasattr(c, attr):
                        try:
                            setattr(c, attr, val)
                        except Exception:
                            pass
            except Exception as e:
                print(f"[RetargetFBX] Could not restore constraint "
                      f"'{d.get('name')}' on '{bone_name}': {e}")


# ─────────────────────────────────────────────────────────────────────────────
#  Bone-axis matching
#  Copies bone rolls from an FBX armature to the source rig so that the FBX
#  action's rotation values produce the same world-space poses on the source.
#  Run once before the batch, using the first FBX as the reference.
# ─────────────────────────────────────────────────────────────────────────────

def match_source_axes_to_fbx(source_rig, fbx_arm, context):
    """
    Copy bone rolls from fbx_arm → source_rig for every bone whose name matches.
    Both rigs are visited in Edit Mode; only the roll (local X-axis orientation)
    is changed — head/tail positions are left untouched.
    Returns the number of bones matched.
    """
    # ── Read FBX bone rolls ──────────────────────────────────────────────────
    fbx_rolls = {}
    bpy.ops.object.select_all(action='DESELECT')
    fbx_arm.select_set(True)
    context.view_layer.objects.active = fbx_arm
    bpy.ops.object.mode_set(mode='EDIT')
    for eb in fbx_arm.data.edit_bones:
        fbx_rolls[eb.name] = eb.roll
    bpy.ops.object.mode_set(mode='OBJECT')

    if not fbx_rolls:
        print("[RetargetFBX]   match_axes: no edit bones found in FBX arm — skipped")
        return 0

    # ── Apply to source rig ──────────────────────────────────────────────────
    bpy.ops.object.select_all(action='DESELECT')
    source_rig.select_set(True)
    context.view_layer.objects.active = source_rig
    bpy.ops.object.mode_set(mode='EDIT')

    matched = 0
    skipped = []
    for eb in source_rig.data.edit_bones:
        if eb.name in fbx_rolls:
            eb.roll = fbx_rolls[eb.name]
            matched += 1
        else:
            skipped.append(eb.name)

    bpy.ops.object.mode_set(mode='OBJECT')

    print(f"[RetargetFBX]   match_axes: matched {matched} / "
          f"{len(source_rig.data.bones)} bones")
    if skipped:
        print(f"[RetargetFBX]   match_axes: {len(skipped)} unmatched bones "
              f"(no FBX counterpart): {skipped[:8]}{'...' if len(skipped) > 8 else ''}")
    return matched


# ─────────────────────────────────────────────────────────────────────────────
#  Per-FBX processing helpers
# ─────────────────────────────────────────────────────────────────────────────

def import_fbx_clean(fbx_path, delete_arm=True):
    """
    Import one FBX. Returns (imported_action, base_name, arm_obj).
    Deletes non-armature junk objects always.
    Deletes the imported armature only when delete_arm=True (full pipeline).
    When delete_arm=False the armature stays in the scene for inspection.
    """
    before_objs = set(o.name for o in bpy.data.objects)

    try:
        bpy.ops.import_scene.fbx(
            filepath=fbx_path,
            automatic_bone_orientation=True,
            ignore_leaf_bones=True,
            global_scale=1.0,
            use_custom_props=True,
            use_anim=True,
        )
    except Exception as e:
        print(f"[RetargetFBX] Import failed for {fbx_path}: {e}")
        return None, None, None

    base_name = os.path.splitext(os.path.basename(fbx_path))[0]

    after_objs = set(o.name for o in bpy.data.objects)
    new_objs = [bpy.data.objects[n] for n in (after_objs - before_objs)
                if n in bpy.data.objects]
    new_arms = [o for o in new_objs if o.type == 'ARMATURE']

    imported_action = None
    kept_arm = new_arms[0] if new_arms else None

    if kept_arm:
        # Rename armature to match FBX base name
        try:
            kept_arm.name = base_name
        except Exception:
            pass
        # Grab and rename the action
        if kept_arm.animation_data and kept_arm.animation_data.action:
            imported_action = kept_arm.animation_data.action
            try:
                imported_action.name = base_name
            except Exception:
                pass
        if delete_arm:
            # Detach so the action survives object deletion
            kept_arm.animation_data.action = None

    # Always delete non-armature junk
    for o in new_objs:
        if kept_arm and o.name == kept_arm.name:
            if delete_arm:
                # Delete the arm too
                try:
                    bpy.data.objects.remove(o, do_unlink=True)
                except Exception:
                    pass
        else:
            try:
                bpy.data.objects.remove(o, do_unlink=True)
            except Exception:
                pass

    arm_in_scene = None if delete_arm else kept_arm
    print(f"[RetargetFBX]   Imported '{base_name}' — "
          f"{'armature deleted (action kept)' if delete_arm else 'armature kept in scene for inspection'}")
    return imported_action, base_name, arm_in_scene


def process_one_fbx(fbx_path, source_rig, target_rig, context, props):
    """
    Full pipeline for a single FBX clip, gated by stage flags on props.
    Returns the baked *_remap action or None on failure / bake disabled.
    """
    scn = context.scene

    # ── STAGE 1: Import & clean ───────────────────────────────────────────────
    if props.do_import:
        # delete_arm only when we're going to proceed — otherwise keep it
        # in the scene so the user can inspect the imported skeleton
        delete_arm = props.do_assign
        imported_action, base_name, _ = import_fbx_clean(fbx_path, delete_arm=delete_arm)
        if imported_action is None and props.do_assign:
            print(f"[RetargetFBX] No action found in {fbx_path} — skipping.")
            return None
        if not props.do_assign:
            print(f"[RetargetFBX]   Import-only mode: armature left in scene. "
                  f"Action found: {imported_action.name if imported_action else 'NONE'}")
            return None
    else:
        # Reuse whatever is already on the source rig
        base_name = os.path.splitext(os.path.basename(fbx_path))[0]
        imported_action = (source_rig.animation_data.action
                           if source_rig.animation_data else None)
        if imported_action is None:
            print(f"[RetargetFBX] do_import is OFF but no action on source rig — skipping.")
            return None

    # ── STAGE 2: Assign to source rig ────────────────────────────────────────
    if props.do_assign:
        if not source_rig.animation_data:
            source_rig.animation_data_create()

        # Disable NLA so direct action assignment isn't overridden
        src_anim = source_rig.animation_data
        nla_was_active = src_anim.use_nla
        src_anim.use_nla = False
        src_anim.action  = imported_action

        # ── Blender 5 slotted-action fix ─────────────────────────────────────
        # In Blender 5, assigning an action isn't enough — a slot must also be
        # selected, otherwise the rig gets no animation data at all.
        # The FBX import creates a slot bound to the now-deleted FBX armature;
        # we reassign the first available slot (or create a new one) to
        # the source rig so the curves actually drive it.
        if imported_action and hasattr(imported_action, 'slots'):
            slots = imported_action.slots
            if slots:
                # Reuse the existing slot (it has all the F-Curves)
                try:
                    src_anim.action_slot = slots[0]
                    print(f"[RetargetFBX]   Slot assigned: '{slots[0].name}'")
                except Exception as e:
                    print(f"[RetargetFBX]   Slot assign failed: {e}")
            else:
                print("[RetargetFBX]   Warning: action has no slots — "
                      "animation may not play on source rig")

        # Verify the assignment actually stuck
        actual = src_anim.action
        if actual and actual.name == imported_action.name:
            print(f"[RetargetFBX]   ✓ Action confirmed on source rig: '{actual.name}'")
        else:
            print(f"[RetargetFBX]   ✗ Action mismatch after assign! "
                  f"Expected '{imported_action.name}', got '{actual}'")

        # Set timeline
        fr = imported_action.frame_range
        scn.frame_start = int(fr[0])
        scn.frame_end   = int(fr[1])
        print(f"[RetargetFBX]   Frames {scn.frame_start}–{scn.frame_end}")
        print(f"[RetargetFBX]   Source NLA was {'active' if nla_was_active else 'already off'} "
              f"— disabled for bake")
    else:
        nla_was_active = False
        print(f"[RetargetFBX]   do_assign is OFF — using existing source rig state")

    # ── STAGE 3: Bake ─────────────────────────────────────────────────────────
    if not props.do_bake:
        print(f"[RetargetFBX]   do_bake is OFF — stopping after assign stage.")
        return None

    remap_name   = base_name + "_remap"
    remap_action = bpy.data.actions.new(name=remap_name)
    remap_action.use_fake_user = True
    if not target_rig.animation_data:
        target_rig.animation_data_create()
    target_rig.animation_data.action = remap_action

    # Ensure target_rig is active and in pose mode, all visible bones selected
    bpy.ops.object.select_all(action='DESELECT')
    target_rig.select_set(True)
    context.view_layer.objects.active = target_rig
    bpy.ops.object.mode_set(mode='POSE')
    bpy.ops.pose.select_all(action='SELECT')

    # ── Force depsgraph evaluation before bake ────────────────────────────────
    scn.frame_set(scn.frame_start)
    context.view_layer.update()

    # ── Pre-bake diagnostics ──────────────────────────────────────────────────
    current_mode = context.object.mode if context.object else 'UNKNOWN'
    n_bones      = len(target_rig.pose.bones)
    src_action   = (source_rig.animation_data.action.name
                    if source_rig.animation_data and source_rig.animation_data.action
                    else 'NONE')
    print(f"[RetargetFBX]   PRE-BAKE CHECK:")
    print(f"[RetargetFBX]     mode         = {current_mode}  (expected: POSE)")
    print(f"[RetargetFBX]     target bones = {n_bones}")
    print(f"[RetargetFBX]     src action   = {src_action}  (should not be NONE)")
    print(f"[RetargetFBX]     frame range  = {scn.frame_start}–{scn.frame_end}")
    print(f"[RetargetFBX]     current frame= {scn.frame_current}")

    try:
        bpy.ops.nla.bake(
            frame_start=scn.frame_start,
            frame_end=scn.frame_end,
            only_selected=True,
            visual_keying=True,
            clear_constraints=True,   # constraints gone — restored after
            clear_parents=False,
            use_current_action=True,
            bake_types={'POSE'},
        )
    except Exception as e:
        print(f"[RetargetFBX] Bake failed for '{base_name}': {e}")
        bpy.ops.object.mode_set(mode='OBJECT')
        # Restore NLA state even on failure
        if props.do_assign and source_rig.animation_data:
            source_rig.animation_data.use_nla = nla_was_active
        return None

    bpy.ops.object.mode_set(mode='OBJECT')

    # Restore source rig NLA state
    if props.do_assign and source_rig.animation_data:
        source_rig.animation_data.use_nla = nla_was_active

    # Retrieve the action actually written (bake may have swapped it)
    baked = target_rig.animation_data.action
    if baked:
        baked.name = remap_name
        baked.use_fake_user = True
        print(f"[RetargetFBX]   Baked → '{remap_name}'")
    else:
        print(f"[RetargetFBX]   Warning: no action found on target after bake.")

    return baked



# ─────────────────────────────────────────────────────────────────────────────
#  NLA push — stacked tracks, all starting at frame 1
# ─────────────────────────────────────────────────────────────────────────────

def push_to_nla(target_rig, actions):
    """Create one NLA track per action, each strip starting at frame 1."""
    if not target_rig.animation_data:
        target_rig.animation_data_create()
    # Clear active action so NLA editor takes over
    target_rig.animation_data.action = None

    for action in actions:
        if action is None:
            continue
        track = target_rig.animation_data.nla_tracks.new()
        track.name = action.name
        try:
            strip = track.strips.new(action.name, 1, action)
            strip.action_frame_start = action.frame_range[0]
            strip.action_frame_end   = action.frame_range[1]
        except Exception as e:
            print(f"[RetargetFBX] NLA strip error for '{action.name}': {e}")


# ─────────────────────────────────────────────────────────────────────────────
#  Main operator
# ─────────────────────────────────────────────────────────────────────────────

class RETARGET_OT_multiple_fbx(Operator):
    """Import and bake multiple FBX mocap clips onto the target rig, then combine as NLA tracks"""
    bl_idname  = "retarget.multiple_fbx"
    bl_label   = "Retarget Multiple FBX"
    bl_options = {'REGISTER', 'UNDO'}

    # File browser
    directory:   StringProperty(subtype='DIR_PATH')
    files:       CollectionProperty(type=OperatorFileListElement)
    filter_glob: StringProperty(default='*.fbx', options={'HIDDEN'})

    @classmethod
    def poll(cls, context):
        p = context.scene.retarget_fbx_props
        return bool(p.source_rig and p.target_rig)

    def invoke(self, context, event):
        context.window_manager.fileselect_add(self)
        return {'RUNNING_MODAL'}

    def execute(self, context):
        props      = context.scene.retarget_fbx_props
        source_rig = props.source_rig
        target_rig = props.target_rig

        if not source_rig or not target_rig:
            self.report({'ERROR'}, "Set Source and Target rigs in the panel first.")
            return {'CANCELLED'}

        fbx_files = [
            os.path.join(self.directory, f.name)
            for f in self.files
            if f.name.lower().endswith('.fbx')
        ]
        if not fbx_files:
            self.report({'ERROR'}, "No FBX files selected.")
            return {'CANCELLED'}

        output_folder = self.directory
        total = len(fbx_files)
        print(f"\n[RetargetFBX] ── Starting batch: {total} file(s) ──")

        # ── Snapshot target constraints before anything touches them ──────────
        constraint_snapshot = snapshot_constraints(target_rig)
        if not any(constraint_snapshot.values()):
            self.report({'WARNING'},
                "No constraints found on target rig bones. "
                "Make sure the target rig is constrained to the source rig.")

        # Remember original source action so we can restore it at the end
        original_source_action = (
            source_rig.animation_data.action
            if source_rig.animation_data else None
        )

        baked_actions = []

        # ── PRE-LOOP: optionally match source rig bone axes to FBX ───────────
        # Done once using the first FBX file as the reference.
        # This copies bone rolls from the FBX rig to the source rig so that
        # the FBX action's rotation values produce the correct world-space pose.
        # NOTE: this permanently changes the source rig's edit-mode bone rolls.
        if props.do_match_axes:
            print("[RetargetFBX] Matching source rig bone axes to FBX...")
            ref_fbx = fbx_files[0]
            _, _, ref_arm = import_fbx_clean(ref_fbx, delete_arm=False)
            if ref_arm:
                match_source_axes_to_fbx(source_rig, ref_arm, context)
                # Clean up: remove arm and orphaned action from this temp import
                if ref_arm.animation_data and ref_arm.animation_data.action:
                    tmp_act = ref_arm.animation_data.action
                    ref_arm.animation_data.action = None
                    bpy.data.actions.remove(tmp_act)
                bpy.data.objects.remove(ref_arm, do_unlink=True)
            else:
                print("[RetargetFBX] match_axes: could not import reference FBX — skipped")

        wm = context.window_manager
        wm.progress_begin(0, total)

        for i, fbx_path in enumerate(fbx_files):
            fname = os.path.basename(fbx_path)
            print(f"\n[RetargetFBX] [{i + 1}/{total}] {fname}")
            wm.progress_update(i)

            baked = process_one_fbx(fbx_path, source_rig, target_rig, context, props)
            if baked:
                baked_actions.append(baked)

            # Restore constraints ONLY between clips — to prime the rig for
            # the next FBX import. After the last clip, constraints stay off
            # so the saved .blend shows clean NLA playback without constraints
            # fighting or hiding the baked animation tracks.
            is_last_clip = (i == total - 1)
            if props.do_bake and not is_last_clip:
                print("[RetargetFBX] Restoring constraints (preparing for next clip)...")
                restore_constraints(target_rig, constraint_snapshot)
            elif props.do_bake and is_last_clip:
                print("[RetargetFBX] Last clip done — constraints left off for clean NLA playback.")


        wm.progress_update(total)
        wm.progress_end()

        # ── Short-circuit at the last enabled stage ───────────────────────────
        # Each block below returns early so nothing after a disabled stage runs.

        # After bake: restore source rig. If bake was OFF, leave imported
        # action on source rig so user can inspect it, then stop here.
        if not props.do_bake:
            self.report({'INFO'},
                f"Stage complete: imported & assigned {total} clip(s). "
                "Inspect source rig then enable Bake to continue.")
            return {'FINISHED'}

        if props.do_bake and source_rig.animation_data:
            source_rig.animation_data.action = original_source_action

        if not baked_actions:
            self.report({'ERROR'}, "No clips were successfully baked.")
            return {'CANCELLED'}

        # ── Push all baked actions as NLA tracks ──────────────────────────────
        if not props.do_nla_push:
            self.report({'INFO'},
                f"Stage complete: baked {len(baked_actions)} clip(s). "
                "Enable Push to NLA to continue.")
            return {'FINISHED'}

        print(f"[RetargetFBX] Pushing {len(baked_actions)} actions to NLA...")
        push_to_nla(target_rig, baked_actions)


        if props.do_save:
            base_names = [os.path.splitext(os.path.basename(p))[0] for p in fbx_files]

            # Build filename from the leading underscore-segments that are
            # identical across ALL files. Stop at the first differing segment.
            # e.g. AG_UR_015_T201_I + AG_UR_090_T201_I  →  AG_UR.blend
            split     = [n.split('_') for n in base_names]
            common_segs = []
            for segs in zip(*split):
                if len(set(segs)) == 1:
                    common_segs.append(segs[0])
                else:
                    break
            blend_stem    = '_'.join(common_segs) if common_segs else "combined_retarget"
            combined_path = os.path.join(output_folder, blend_stem + ".blend")
            try:
                bpy.ops.wm.save_as_mainfile(filepath=combined_path, copy=True)
                print(f"[RetargetFBX] Combined file saved → {combined_path}")
            except Exception as e:
                self.report({'WARNING'}, f"Could not save combined file: {e}")
            self.report(
                {'INFO'},
                f"Done! Baked {len(baked_actions)} clip(s). Combined: {combined_path}"
            )
        else:
            self.report({'INFO'}, f"Done! Baked {len(baked_actions)} clip(s). (Save skipped)")
        return {'FINISHED'}



# ─────────────────────────────────────────────────────────────────────────────
#  Properties
# ─────────────────────────────────────────────────────────────────────────────

class RetargetFBXProperties(PropertyGroup):
    source_rig: PointerProperty(
        name="Source Rig",
        description="Armature that receives the imported mocap action",
        type=bpy.types.Object,
        poll=lambda self, obj: obj.type == 'ARMATURE',
    )
    target_rig: PointerProperty(
        name="Target Rig",
        description="Armature constrained TO the source — this is what gets baked",
        type=bpy.types.Object,
        poll=lambda self, obj: obj.type == 'ARMATURE',
    )
    # ── Stage gates ───────────────────────────────────────────────────────────
    do_import: bpy.props.BoolProperty(
        name="Import FBX & clean",
        description="Import each FBX, delete junk objects, rename armature/action",
        default=True,
    )
    do_assign: bpy.props.BoolProperty(
        name="Assign action to source rig",
        description="Assign the imported action to the source rig (disables NLA override) and set timeline",
        default=True,
    )
    do_bake: bpy.props.BoolProperty(
        name="Bake to target rig",
        description="Enter pose mode on target, select all visible bones, bake with visual keying",
        default=True,
    )
    do_nla_push: bpy.props.BoolProperty(
        name="Push to NLA",
        description="Push all baked actions as stacked NLA tracks on the target rig",
        default=True,
    )
    do_save: bpy.props.BoolProperty(
        name="Save combined .blend",
        description="Save a copy of the scene (with NLA tracks) alongside the FBX files",
        default=True,
    )
    do_match_axes: bpy.props.BoolProperty(
        name="Match source rig bone axes to FBX",
        description=(
            "Before the batch, copy bone rolls from the first FBX armature to the "
            "source rig. This aligns local bone axes so the FBX action's rotation "
            "values produce the correct world-space pose. Permanently changes the "
            "source rig's edit-mode bone rolls."
        ),
        default=False,
    )


# ─────────────────────────────────────────────────────────────────────────────
#  Panel
# ─────────────────────────────────────────────────────────────────────────────

class RETARGET_PT_panel(Panel):
    bl_label      = "Retarget Multiple FBX"
    bl_idname     = "RETARGET_PT_panel"
    bl_space_type = 'VIEW_3D'
    bl_region_type= 'UI'
    bl_category   = 'DumbTools'

    def draw(self, context):
        layout = self.layout
        props  = context.scene.retarget_fbx_props

        col = layout.column(align=True)
        col.label(text="Rigs:", icon='ARMATURE_DATA')
        col.prop(props, "source_rig", text="Source  (gets mocap action)")
        col.prop(props, "target_rig", text="Target  (constrained → baked)")

        layout.separator()
        row = layout.row(align=True)
        row.operator("retarget.pick_rigs_from_selection", text="Pick from Selection",
                     icon='EYEDROPPER')

        layout.separator()
        layout.label(text="Stages:", icon='SETTINGS')
        col = layout.column(align=True)
        col.prop(props, "do_import")
        col.prop(props, "do_assign")
        col.prop(props, "do_bake")
        col.prop(props, "do_nla_push")
        col.prop(props, "do_save")

        layout.separator()
        box = layout.box()
        box.label(text="One-time setup:", icon='ORIENTATION_GLOBAL')
        box.prop(props, "do_match_axes")
        if props.do_match_axes:
            box.label(text="Uses first FBX as reference.", icon='INFO')
            box.label(text="Permanently changes source rig rolls.", icon='ERROR')

        layout.separator()
        ready = bool(props.source_rig and props.target_rig)
        col2  = layout.column()
        col2.enabled = ready
        col2.operator("retarget.multiple_fbx", text="Select FBX Files & Retarget",
                      icon='IMPORT')
        if not ready:
            layout.label(text="Set both rigs above first.", icon='ERROR')



# ─────────────────────────────────────────────────────────────────────────────
#  Convenience: fill rigs from viewport selection
#  Select source first, then Shift+click target (active).
# ─────────────────────────────────────────────────────────────────────────────

class RETARGET_OT_pick_rigs(Operator):
    """Fill Source/Target from current selection.
Select source rig first, then Shift-click target rig (active object)."""
    bl_idname  = "retarget.pick_rigs_from_selection"
    bl_label   = "Pick Rigs from Selection"
    bl_options = {'REGISTER', 'UNDO'}

    def execute(self, context):
        props   = context.scene.retarget_fbx_props
        active  = context.active_object
        selected = [o for o in context.selected_objects
                    if o.type == 'ARMATURE' and o is not active]

        if not active or active.type != 'ARMATURE':
            self.report({'ERROR'}, "Active object must be an ARMATURE (this will be the Target).")
            return {'CANCELLED'}

        props.target_rig = active

        if selected:
            props.source_rig = selected[0]
            self.report({'INFO'},
                f"Source: {selected[0].name}  |  Target: {active.name}")
        else:
            self.report({'WARNING'},
                f"Target set to '{active.name}'. "
                "Select source rig too (Shift-click), then run again.")

        return {'FINISHED'}


# ─────────────────────────────────────────────────────────────────────────────
#  Register / Unregister
# ─────────────────────────────────────────────────────────────────────────────

_classes = (
    RetargetFBXProperties,
    RETARGET_OT_multiple_fbx,
    RETARGET_OT_pick_rigs,
    RETARGET_PT_panel,
)


def register():
    for cls in _classes:
        try:
            bpy.utils.register_class(cls)
        except Exception:
            bpy.utils.unregister_class(cls)
            bpy.utils.register_class(cls)
    if not hasattr(bpy.types.Scene, 'retarget_fbx_props'):
        bpy.types.Scene.retarget_fbx_props = PointerProperty(
            type=RetargetFBXProperties
        )


def unregister():
    for cls in reversed(_classes):
        try:
            bpy.utils.unregister_class(cls)
        except Exception:
            pass
    try:
        del bpy.types.Scene.retarget_fbx_props
    except Exception:
        pass


register()
