# Tooltip: Select rig objects, then select new armature LAST (active). Retargets all parenting, armature modifiers, and driver references to the new armature.

import bpy


class DUMBTOOLS_OT_switch_to_new_armature(bpy.types.Operator):
    bl_idname = "dumbtools.switch_to_new_armature"
    bl_label = "Switch To New Armature"
    bl_description = (
        "Retarget all armature references (parents, modifiers, drivers) "
        "on selected objects to the active armature"
    )
    bl_options = {'REGISTER', 'UNDO'}

    @classmethod
    def poll(cls, context):
        active = context.active_object
        if not active or active.type != 'ARMATURE':
            return False
        if len(context.selected_objects) < 2:
            return False
        return True

    def execute(self, context):
        new_armature = context.active_object
        objects_to_process = [
            obj for obj in context.selected_objects if obj != new_armature
        ]

        if not objects_to_process:
            self.report({'WARNING'}, "No objects selected besides the active armature")
            return {'CANCELLED'}

        # ---- Collect old armatures ----
        # We infer which armatures are "old" by scanning all references on the
        # selected objects and collecting any armature that isn't the new one.
        old_armatures = self._collect_old_armatures(objects_to_process, new_armature)

        if not old_armatures:
            self.report({'WARNING'}, "Selected objects have no references to any other armature")
            return {'CANCELLED'}

        old_names = ", ".join(sorted(a.name for a in old_armatures))
        print(f"[SwitchArmature] New armature: {new_armature.name}")
        print(f"[SwitchArmature] Old armature(s) detected: {old_names}")
        print(f"[SwitchArmature] Objects to process: {len(objects_to_process)}")

        # ---- Process ----
        stats = {"parents": 0, "modifiers": 0, "driver_vars": 0}

        for obj in objects_to_process:
            self._retarget_parent(obj, old_armatures, new_armature, stats)
            self._retarget_modifiers(obj, old_armatures, new_armature, stats)
            self._retarget_shape_key_drivers(obj, old_armatures, new_armature, stats)
            self._retarget_object_drivers(obj, old_armatures, new_armature, stats)

        # ---- Refresh ----
        try:
            context.view_layer.update()
            context.evaluated_depsgraph_get().update()
        except Exception:
            pass

        # ---- Summary ----
        summary = (
            f"Parents: {stats['parents']}, "
            f"Modifiers: {stats['modifiers']}, "
            f"Driver vars: {stats['driver_vars']}"
        )
        print(f"[SwitchArmature] === Summary ===")
        print(f"[SwitchArmature] {summary}")
        self.report(
            {'INFO'},
            f"Switched to {new_armature.name} — {summary}",
        )
        return {'FINISHED'}

    # ------------------------------------------------------------------
    # Collect old armatures
    # ------------------------------------------------------------------

    def _collect_old_armatures(self, objects, new_armature):
        """Scan all references and return a set of armature objects that aren't the new one."""
        old = set()

        for obj in objects:
            # Parent
            if obj.parent and obj.parent.type == 'ARMATURE' and obj.parent != new_armature:
                old.add(obj.parent)

            # Armature modifiers
            for mod in getattr(obj, 'modifiers', []):
                if mod.type == 'ARMATURE' and mod.object and mod.object.type == 'ARMATURE':
                    if mod.object != new_armature:
                        old.add(mod.object)

            # Shape key drivers
            sk = getattr(getattr(obj, 'data', None), 'shape_keys', None)
            if sk:
                self._collect_armatures_from_anim_data(
                    getattr(sk, 'animation_data', None), new_armature, old
                )

            # Object-level drivers
            self._collect_armatures_from_anim_data(
                getattr(obj, 'animation_data', None), new_armature, old
            )

        return old

    def _collect_armatures_from_anim_data(self, anim_data, new_armature, out_set):
        """Scan driver variables in animation_data for armature references."""
        if not anim_data or not anim_data.drivers:
            return
        for fcu in anim_data.drivers:
            drv = getattr(fcu, 'driver', None)
            if not drv:
                continue
            for var in drv.variables:
                for tgt in var.targets:
                    tid = getattr(tgt, 'id', None)
                    if tid and getattr(tid, 'type', None) == 'ARMATURE' and tid != new_armature:
                        out_set.add(tid)

    # ------------------------------------------------------------------
    # 1. Parent relationships
    # ------------------------------------------------------------------

    def _retarget_parent(self, obj, old_armatures, new_armature, stats):
        if not obj.parent or obj.parent not in old_armatures:
            return

        old_name = obj.parent.name
        parent_type = obj.parent_type  # 'OBJECT', 'BONE', 'BONE_RELATIVE', 'ARMATURE', etc.
        bone_name = obj.parent_bone    # relevant for BONE / BONE_RELATIVE

        # Direct assignment preserves inverse matrix and avoids transform reset.
        obj.parent = new_armature
        # parent_type and parent_bone are preserved automatically when we only
        # change obj.parent, but let's be explicit to be safe.
        obj.parent_type = parent_type
        if bone_name:
            obj.parent_bone = bone_name

        detail = f" (bone: {bone_name})" if bone_name else ""
        print(
            f"[SwitchArmature] Parent: {obj.name} "
            f"{parent_type} {old_name} → {new_armature.name}{detail}"
        )
        stats["parents"] += 1

    # ------------------------------------------------------------------
    # 2. Armature modifiers
    # ------------------------------------------------------------------

    def _retarget_modifiers(self, obj, old_armatures, new_armature, stats):
        for mod in getattr(obj, 'modifiers', []):
            if mod.type != 'ARMATURE':
                continue
            if mod.object and mod.object in old_armatures:
                old_name = mod.object.name
                mod.object = new_armature
                print(
                    f"[SwitchArmature] Modifier: {obj.name} "
                    f"'{mod.name}' {old_name} → {new_armature.name}"
                )
                stats["modifiers"] += 1

    # ------------------------------------------------------------------
    # 3. Shape key drivers
    # ------------------------------------------------------------------

    def _retarget_shape_key_drivers(self, obj, old_armatures, new_armature, stats):
        sk = getattr(getattr(obj, 'data', None), 'shape_keys', None)
        if not sk:
            return
        anim_data = getattr(sk, 'animation_data', None)
        if not anim_data or not anim_data.drivers:
            return

        label = f"{obj.name}.shape_keys"
        for fcu in anim_data.drivers:
            self._retarget_driver_fcurve(fcu, label, old_armatures, new_armature, stats)

    # ------------------------------------------------------------------
    # 4. Object-level drivers
    # ------------------------------------------------------------------

    def _retarget_object_drivers(self, obj, old_armatures, new_armature, stats):
        anim_data = getattr(obj, 'animation_data', None)
        if not anim_data or not anim_data.drivers:
            return

        label = obj.name
        for fcu in anim_data.drivers:
            self._retarget_driver_fcurve(fcu, label, old_armatures, new_armature, stats)

    # ------------------------------------------------------------------
    # Shared driver retargeting
    # ------------------------------------------------------------------

    def _retarget_driver_fcurve(self, fcu, label, old_armatures, new_armature, stats):
        """Retarget all variable targets in a single driver FCurve."""
        drv = getattr(fcu, 'driver', None)
        if not drv:
            return

        data_path = fcu.data_path or ""

        for var in drv.variables:
            # Variable types and their target counts:
            #   SINGLE_PROP  — 1 target
            #   TRANSFORMS   — 1 target
            #   ROTATION_DIFF — 2 targets
            #   LOC_DIFF     — 2 targets
            #   CONTEXT_PROP — 0 targets (context-based, skip)
            for tgt in var.targets:
                tid = getattr(tgt, 'id', None)
                if not tid or tid not in old_armatures:
                    continue

                old_name = tid.name
                tgt.id = new_armature

                # Build a descriptive log line
                extra_parts = []
                extra_parts.append(var.type)

                bone = getattr(tgt, 'bone_target', '')
                if bone:
                    extra_parts.append(f"bone: {bone}")

                tgt_data_path = getattr(tgt, 'data_path', '')
                if tgt_data_path:
                    extra_parts.append(f"path: {tgt_data_path}")

                extra = " ".join(extra_parts)
                print(
                    f"[SwitchArmature] Driver: {label}: {data_path} "
                    f"var '{var.name}' {extra} "
                    f"{old_name} → {new_armature.name}"
                )
                stats["driver_vars"] += 1


def register():
    try:
        bpy.utils.register_class(DUMBTOOLS_OT_switch_to_new_armature)
    except ValueError:
        pass


def unregister():
    try:
        bpy.utils.unregister_class(DUMBTOOLS_OT_switch_to_new_armature)
    except ValueError:
        pass


register()
bpy.ops.dumbtools.switch_to_new_armature('INVOKE_DEFAULT')
