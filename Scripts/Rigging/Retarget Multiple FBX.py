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
#  Per-FBX processing helpers
# ─────────────────────────────────────────────────────────────────────────────

def import_fbx_clean(fbx_path):
    """
    Import one FBX. Returns (imported_action, base_name).
    Deletes every new non-armature object (Rokoko mesh junk etc.)
    Also deletes the imported armature object after detaching its action.
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
        return None, None

    base_name = os.path.splitext(os.path.basename(fbx_path))[0]

    after_objs = set(o.name for o in bpy.data.objects)
    new_objs = [bpy.data.objects[n] for n in (after_objs - before_objs)
                if n in bpy.data.objects]
    new_arms = [o for o in new_objs if o.type == 'ARMATURE']

    imported_action = None
    kept_arm = new_arms[0] if new_arms else None

    if kept_arm:
        # Grab action before renaming / deleting the armature
        if kept_arm.animation_data and kept_arm.animation_data.action:
            imported_action = kept_arm.animation_data.action
            try:
                imported_action.name = base_name
            except Exception:
                pass
            # Detach so the action survives object deletion
            kept_arm.animation_data.action = None

    # Delete every new object (armature and junk)
    for o in new_objs:
        try:
            bpy.data.objects.remove(o, do_unlink=True)
        except Exception:
            pass

    return imported_action, base_name


def process_one_fbx(fbx_path, source_rig, target_rig, context):
    """
    Full pipeline for a single FBX clip.
    Returns the baked *_remap action or None on failure.
    """
    scn = context.scene
    imported_action, base_name = import_fbx_clean(fbx_path)

    if imported_action is None:
        print(f"[RetargetFBX] No action found in {fbx_path} — skipping.")
        return None

    # ── Assign imported action → source rig ──────────────────────────────────
    if not source_rig.animation_data:
        source_rig.animation_data_create()
    source_rig.animation_data.action = imported_action

    # ── Timeline from action ──────────────────────────────────────────────────
    fr = imported_action.frame_range
    scn.frame_start = int(fr[0])
    scn.frame_end   = int(fr[1])
    print(f"[RetargetFBX] '{base_name}'  frames {scn.frame_start}–{scn.frame_end}")

    # ── New empty action on target ────────────────────────────────────────────
    remap_name   = base_name + "_remap"
    remap_action = bpy.data.actions.new(name=remap_name)
    remap_action.use_fake_user = True
    if not target_rig.animation_data:
        target_rig.animation_data_create()
    target_rig.animation_data.action = remap_action

    # ── Pose mode, select all visible bones ──────────────────────────────────
    # Set active object FIRST — after import_fbx_clean deletes everything the
    # active object is None, so mode_set would fail its poll otherwise.
    bpy.ops.object.select_all(action='DESELECT')
    target_rig.select_set(True)
    context.view_layer.objects.active = target_rig
    bpy.ops.object.mode_set(mode='POSE')
    bpy.ops.pose.select_all(action='SELECT')

    # ── Bake ──────────────────────────────────────────────────────────────────
    try:
        bpy.ops.nla.bake(
            frame_start=scn.frame_start,
            frame_end=scn.frame_end,
            only_selected=True,
            visual_keying=True,
            clear_constraints=True,   # constraints gone — we restore them after
            clear_parents=False,
            use_current_action=True,
            bake_types={'POSE'},
        )
    except Exception as e:
        print(f"[RetargetFBX] Bake failed for '{base_name}': {e}")
        bpy.ops.object.mode_set(mode='OBJECT')
        return None

    bpy.ops.object.mode_set(mode='OBJECT')

    # Retrieve the action that was actually written (bake may have swapped it)
    baked = target_rig.animation_data.action
    if baked:
        baked.name = remap_name
        baked.use_fake_user = True
        print(f"[RetargetFBX] Baked → '{remap_name}'")
    else:
        print(f"[RetargetFBX] Warning: no action found on target after bake.")

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
        print(f"\n[RetargetFBX] ── Starting batch: {len(fbx_files)} file(s) ──")

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

        for fbx_path in fbx_files:
            baked = process_one_fbx(fbx_path, source_rig, target_rig, context)
            if baked:
                baked_actions.append(baked)

            # Restore target rig constraints for the next clip
            print("[RetargetFBX] Restoring constraints...")
            restore_constraints(target_rig, constraint_snapshot)

        # Restore source rig to its original action
        if source_rig.animation_data:
            source_rig.animation_data.action = original_source_action

        if not baked_actions:
            self.report({'ERROR'}, "No clips were successfully baked.")
            return {'CANCELLED'}

        # ── Push all baked actions as NLA tracks ──────────────────────────────
        print(f"[RetargetFBX] Pushing {len(baked_actions)} actions to NLA...")
        push_to_nla(target_rig, baked_actions)

        # ── Save combined .blend alongside the FBX files ──────────────────────
        combined_path = os.path.join(output_folder, "combined_retarget.blend")
        try:
            bpy.ops.wm.save_as_mainfile(filepath=combined_path, copy=True)
            print(f"[RetargetFBX] Combined file saved → {combined_path}")
        except Exception as e:
            self.report({'WARNING'}, f"Could not save combined file: {e}")

        self.report(
            {'INFO'},
            f"Done! Baked {len(baked_actions)} clip(s). "
            f"Combined file: {combined_path}"
        )
        return {'FINISHED'}


# ─────────────────────────────────────────────────────────────────────────────
#  Properties
# ─────────────────────────────────────────────────────────────────────────────

class RetargetFBXProperties(PropertyGroup):
    source_rig: PointerProperty(
        name="Source Rig",
        description="Armature that receives the imported mocap action (has constraints on it or drives the target)",
        type=bpy.types.Object,
        poll=lambda self, obj: obj.type == 'ARMATURE',
    )
    target_rig: PointerProperty(
        name="Target Rig",
        description="Armature constrained TO the source — this is what gets baked",
        type=bpy.types.Object,
        poll=lambda self, obj: obj.type == 'ARMATURE',
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

        # Quick-fill from selection
        row = layout.row(align=True)
        row.operator("retarget.pick_rigs_from_selection", text="Pick from Selection",
                     icon='EYEDROPPER')

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
