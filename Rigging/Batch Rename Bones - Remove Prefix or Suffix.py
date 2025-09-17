# Tooltip: Remove a specified prefix/suffix or symmetrize names (.L/.R) for selected bones.
import bpy
import re
import json

# Scene property to persist last rename mapping
_def_scene_prop_name = "dumbtools_last_bone_renames"

def _ensure_scene_props():
    if not hasattr(bpy.types.Scene, _def_scene_prop_name):
        setattr(
            bpy.types.Scene,
            _def_scene_prop_name,
            bpy.props.StringProperty(
                name="DumbTools Last Bone Renames",
                description="JSON payload of the last bone rename mapping",
                default="",
            ),
        )


class DUMBTOOLS_OT_BatchRenameBones(bpy.types.Operator):
    """Rename selected bones by removing a prefix/suffix or symmetrizing names (.L/.R)."""
    bl_idname = "dumbtools.batch_rename_bones_remove"
    bl_label = "Batch Rename Bones"
    bl_options = {'REGISTER', 'UNDO'}

    # General action mode
    mode: bpy.props.EnumProperty(
        name="Mode",
        description="Choose renaming behavior",
        items=[
            ('REMOVE', "Remove Prefix/Suffix",
             "Remove exact text from start or end of each selected bone name"),
            ('SYMMETRIZE', "Symmetrize (.L/.R)",
             "Find Left/Right pairs and rename to common core + .L/.R"),
        ],
        default='REMOVE'
    )

    # Properties for the REMOVE mode (still supported if called programmatically)
    substring: bpy.props.StringProperty(
        name="Text to remove",
        description=(
            "Exact text to strip from start (prefix) or end (suffix) of each selected"
            " bone's name"
        ),
        default=""
    )

    position: bpy.props.EnumProperty(
        name="Position",
        description="Where to remove the text from",
        items=[
            ('PREFIX', "Prefix", "Remove only if the name starts with the text"),
            ('SUFFIX', "Suffix", "Remove only if the name ends with the text"),
        ],
        default='PREFIX'
    )

    # Dialog action buttons
    dialog_action: bpy.props.EnumProperty(
        name="Action",
        description="Action chosen from the popup buttons",
        items=[
            ('NONE', "None", "No dialog action"),
            ('SYMMETRIZE', "Symmetrise", "Symmetrize names to core + .L/.R"),
            ('RESTORE', "Restore", "Restore previous names from last mapping"),
            ('CANCEL', "Cancel", "Cancel and close"),
        ],
        default='NONE',
        options={'HIDDEN'}
    )

    @classmethod
    def poll(cls, context):
        obj = context.active_object
        return obj is not None and obj.type == 'ARMATURE' and obj.data is not None

    def draw(self, context):
        layout = self.layout
        # Focus this popup on symmetrizing/restoring as requested
        col = layout.column(align=True)
        col.label(text="Symmetrize names to core + .L/.R")
        col.label(text="Pairs detected via Left/Right or .L/.R, _L/_R, -L/-R")

        layout.separator()
        row = layout.row(align=True)
        op1 = row.operator(self.bl_idname, text="Symmetrise", icon='ARROW_LEFTRIGHT')
        op1.dialog_action = 'SYMMETRIZE'
        op2 = row.operator(self.bl_idname, text="Restore Names", icon='RECOVER_LAST')
        op2.dialog_action = 'RESTORE'
        op3 = row.operator(self.bl_idname, text="Cancel", icon='CANCEL')
        op3.dialog_action = 'CANCEL'


    def invoke(self, context, event):
        # Open a custom popup with our buttons (no default OK/Cancel)
        context.window_manager.invoke_popup(self, width=380)
        return {'RUNNING_MODAL'}

    def execute(self, context):
        obj = context.active_object
        arm = obj.data

        # Handle dialog actions first
        if self.dialog_action == 'CANCEL':
            return {'CANCELLED'}
        if self.dialog_action == 'RESTORE':
            # Call the restore operator and close this popup
            bpy.ops.dumbtools.restore_last_bone_names()
            return {'FINISHED'}
        # Default or Symmetrise action proceeds to symmetrize logic

        # Collect selected bone names first (stable list before renaming)
        selected_names = [b.name for b in arm.bones if b.select]

        if self.mode == 'REMOVE':
            if not selected_names:
                self.report({'WARNING'}, "No bones selected")
                return {'CANCELLED'}
            if not self.substring:
                self.report({'WARNING'}, "No text specified to remove")
                return {'CANCELLED'}
            return self._do_remove_prefix_suffix(context, arm, selected_names)

        # SYMMETRIZE path (allow empty selection to operate on all pairs)
        return self._do_symmetrize(context, arm, selected_names)

    # --- REMOVE mode implementation ---
    def _store_last_mapping(self, obj, renames):
        # Store mapping as JSON on the scene so it persists in the .blend
        try:
            payload = {
                "object": obj.name,
                "pairs": [(old, new) for (old, new) in renames],
            }
            _ensure_scene_props()
            bpy.context.scene.dumbtools_last_bone_renames = json.dumps(payload)
        except Exception:
            pass

    def _do_remove_prefix_suffix(self, context, arm, selected_names):
        removed_count = 0
        changed = 0
        renames = []
        for name in selected_names:
            new_name = name
            if self.position == 'PREFIX' and name.startswith(self.substring):
                new_name = name[len(self.substring):]
                removed_count += 1
            elif self.position == 'SUFFIX' and name.endswith(self.substring):
                new_name = name[:-len(self.substring)]
                removed_count += 1

            if new_name != name:
                try:
                    arm.bones[name].name = new_name
                    renames.append((name, new_name))
                    changed += 1
                except Exception as e:
                    self.report({'WARNING'}, f"Skipping '{name}': {e}")

        if renames:
            self._store_last_mapping(context.active_object, renames)

        self.report(
            {'INFO'},
            (
                f"Processed {len(selected_names)} bones, removed on {removed_count}, "
                f"renamed {changed}."
            ),
        )
        return {'FINISHED'}

    # --- SYMMETRIZE mode implementation ---
    def _normalize_core(self, text):
        # Remove explicit Left/Right words and trim common separators at ends
        core = re.sub('(?i)(left|right)', '', text)
        core = re.sub(r'[\s:_\-\.]+$', '', core)
        core = re.sub(r'^[\s:_\-\.]+', '', core)
        return core

    def _detect_side_and_core(self, name):
        # Return (core, side) where side in {'L','R',None}
        # 1) Suffix forms
        suffixes = ['.L', '.R', '_L', '_R', '-L', '-R']
        for suf in suffixes:
            if name.endswith(suf):
                side = 'L' if suf.endswith('L') else 'R'
                core = name[: -len(suf)]
                core = self._normalize_core(core)
                return core, side
        # 2) Contains 'Left'/'Right' (case-insensitive) anywhere
        low = name.lower()
        if 'left' in low and 'right' in low:
            # Ambiguous, skip side detection
            return name, None
        if 'left' in low:
            core = self._normalize_core(name)
            return core, 'L'
        if 'right' in low:
            core = self._normalize_core(name)
            return core, 'R'
        # No side detected
        return name, None

    def _do_symmetrize(self, context, arm, selected_names):
        # Build mapping from ALL bones core -> {'L': name, 'R': name}
        pairs = {}
        all_names = [b.name for b in arm.bones]
        for name in all_names:
            core, side = self._detect_side_and_core(name)
            if side in {'L', 'R'}:
                core_norm = core
                d = pairs.setdefault(core_norm, {})
                # Only keep first occurrence per side for this core
                d.setdefault(side, name)

        # Build list of cores that have both sides
        full_pairs = []  # list of tuples: (old_L, new_L, old_R, new_R, core)
        for core, sides in pairs.items():
            if 'L' in sides and 'R' in sides:
                new_l = f"{core}.L"
                new_r = f"{core}.R"
                full_pairs.append((sides['L'], new_l, sides['R'], new_r, core))

        if not full_pairs:
            self.report({'WARNING'}, "No Left/Right pairs detected in armature")
            return {'CANCELLED'}

        # If there is a selection, restrict to pairs where at least one side is selected
        selected_set = set(selected_names)
        if selected_set:
            rename_pairs = [
                (old_l, new_l, old_r, new_r)
                for (old_l, new_l, old_r, new_r, _core) in full_pairs
                if (old_l in selected_set or old_r in selected_set)
            ]
        else:
            rename_pairs = [
                (old_l, new_l, old_r, new_r)
                for (old_l, new_l, old_r, new_r, _c) in full_pairs
            ]

        if not rename_pairs:
            self.report({'WARNING'}, "No matching pairs intersect with selection")
            return {'CANCELLED'}

        # Two-phase renaming to avoid collisions
        temp_suffix = "__DT_TMP__"
        temp_names = {}
        # Phase 1: move any name that would collide to a temp name
        for old_l, new_l, old_r, new_r in rename_pairs:
            for old_name, new_name in [(old_l, new_l), (old_r, new_r)]:
                if new_name in arm.bones and new_name != old_name:
                    tmp = old_name + temp_suffix
                    # Ensure tmp is unique
                    i = 1
                    tmp_unique = tmp
                    while tmp_unique in arm.bones:
                        i += 1
                        tmp_unique = f"{tmp}_{i}"
                    arm.bones[old_name].name = tmp_unique
                    temp_names[old_name] = tmp_unique

        # Phase 2: assign final names
        changed = 0
        renames = []
        for old_l, new_l, old_r, new_r in rename_pairs:
            final_map = [
                (temp_names.get(old_l, old_l), new_l),
                (temp_names.get(old_r, old_r), new_r),
            ]
            for src, dst in final_map:
                if src in arm.bones:
                    try:
                        arm.bones[src].name = dst
                        renames.append((src, dst))
                        changed += 1
                    except Exception as e:
                        self.report({'WARNING'}, f"Skipping '{src}' -> '{dst}': {e}")

        if renames:
            self._store_last_mapping(context.active_object, renames)

        self.report(
            {'INFO'},
            f"Symmetrized {len(rename_pairs)} pairs ({changed} renames)."
        )
        return {'FINISHED'}


class DUMBTOOLS_OT_RestoreLastBoneNames(bpy.types.Operator):
    bl_idname = "dumbtools.restore_last_bone_names"
    bl_label = "Restore Previous Names"
    bl_options = {'REGISTER', 'UNDO'}

    @classmethod
    def poll(cls, context):
        _ensure_scene_props()
        data = bpy.context.scene.dumbtools_last_bone_renames
        return bool(data)

    def execute(self, context):
        _ensure_scene_props()
        payload = bpy.context.scene.dumbtools_last_bone_renames
        if not payload:
            self.report({'WARNING'}, "No stored rename mapping found")
            return {'CANCELLED'}
        try:
            data = json.loads(payload)
            obj_name = data.get("object")
            pairs = data.get("pairs", [])
        except Exception as e:
            self.report({'ERROR'}, f"Failed to parse stored mapping: {e}")
            return {'CANCELLED'}

        obj = context.active_object
        if not obj or obj.type != 'ARMATURE':
            self.report({'ERROR'}, "Active object is not an armature")
            return {'CANCELLED'}

        if obj.name != obj_name:
            self.report({'WARNING'}, f"Stored mapping belongs to object '{obj_name}', active is '{obj.name}'.")

        arm = obj.data
        restored = 0
        # We stored (old_name, new_name); to restore we try to map new_name -> old_name
        # Use two-phase to avoid collisions
        temp_suffix = "__DT_RESTORE__"
        need_temp = []
        final_map = []
        for old_name, new_name in pairs:
            if new_name in arm.bones and old_name != new_name:
                # If old_name exists already and different bone holds new_name, we need temp
                if old_name in arm.bones and old_name != new_name:
                    need_temp.append(new_name)
                final_map.append((new_name, old_name))

        # Phase 1: temp rename
        temp_names = {}
        for n in need_temp:
            tmp = n + temp_suffix
            i = 1
            tmp_unique = tmp
            while tmp_unique in arm.bones:
                i += 1
                tmp_unique = f"{tmp}_{i}"
            arm.bones[n].name = tmp_unique
            temp_names[n] = tmp_unique

        # Phase 2: final restore
        for src, dst in final_map:
            src_actual = temp_names.get(src, src)
            if src_actual in arm.bones:
                try:
                    arm.bones[src_actual].name = dst
                    restored += 1
                except Exception as e:
                    self.report({'WARNING'}, f"Restore skip '{src_actual}' -> '{dst}': {e}")

        self.report({'INFO'}, f"Restored {restored} bone names")
        return {'FINISHED'}


def register():
    _ensure_scene_props()
    bpy.utils.register_class(DUMBTOOLS_OT_BatchRenameBones)
    bpy.utils.register_class(DUMBTOOLS_OT_RestoreLastBoneNames)


def unregister():
    bpy.utils.unregister_class(DUMBTOOLS_OT_RestoreLastBoneNames)
    bpy.utils.unregister_class(DUMBTOOLS_OT_BatchRenameBones)


register()
bpy.ops.dumbtools.batch_rename_bones_remove('INVOKE_DEFAULT')
