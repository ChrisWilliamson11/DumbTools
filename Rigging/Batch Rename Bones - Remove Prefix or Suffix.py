# Tooltip: Remove a specified prefix or suffix from the names of selected bones.
import bpy

class DUMBTOOLS_OT_BatchRenameBones(bpy.types.Operator):
    """Remove a specified prefix or suffix from selected bones"""
    bl_idname = "dumbtools.batch_rename_bones_remove"
    bl_label = "Batch Rename Bones (Remove Prefix/Suffix)"
    bl_options = {'REGISTER', 'UNDO'}

    substring: bpy.props.StringProperty(
        name="Text to remove",
        description="Exact text to strip from the start (prefix) or end (suffix) of each selected bone's name",
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

    @classmethod
    def poll(cls, context):
        obj = context.active_object
        return obj is not None and obj.type == 'ARMATURE' and obj.data is not None

    def draw(self, context):
        layout = self.layout
        layout.prop(self, "substring")
        layout.prop(self, "position", expand=True)


    def invoke(self, context, event):
        # Open a dialog to enter the substring and choose prefix/suffix
        return context.window_manager.invoke_props_dialog(self)

    def execute(self, context):
        obj = context.active_object
        arm = obj.data

        if not self.substring:
            self.report({'WARNING'}, "No text specified to remove")
            return {'CANCELLED'}

        # Collect selected bone names first (stable list before renaming)
        selected_names = [b.name for b in arm.bones if b.select]
        if not selected_names:
            self.report({'WARNING'}, "No bones selected")
            return {'CANCELLED'}

        removed_count = 0
        changed = 0

        # Build a quick set to detect potential name collisions
        existing_names = {b.name for b in arm.bones}

        for name in selected_names:
            new_name = name
            if self.position == 'PREFIX' and name.startswith(self.substring):
                new_name = name[len(self.substring):]
                removed_count += 1
            elif self.position == 'SUFFIX' and name.endswith(self.substring):
                new_name = name[:-len(self.substring)]
                removed_count += 1

            if new_name != name:
                # Handle rare case where target name already exists; let Blender auto-unique
                try:
                    arm.bones[name].name = new_name
                    changed += 1
                except Exception as e:
                    self.report({'WARNING'}, f"Skipping '{name}': {e}")

        self.report({'INFO'}, f"Processed {len(selected_names)} bones, removed on {removed_count}, renamed {changed}.")
        return {'FINISHED'}


def register():
    bpy.utils.register_class(DUMBTOOLS_OT_BatchRenameBones)


def unregister():
    bpy.utils.unregister_class(DUMBTOOLS_OT_BatchRenameBones)


register()
# Invoke the operator so it pops a dialog when run from the script launcher
bpy.ops.dumbtools.batch_rename_bones_remove('INVOKE_DEFAULT')

