import bpy
import csv
from bpy_extras.io_utils import ImportHelper

def get_columns_callback(self, context):
    items = []
    if self.filepath:
        try:
            with open(self.filepath, mode='r', encoding='utf-8') as f:
                first_line = f.readline()
                if first_line:
                    header = list(csv.reader([first_line]))[0]
                    if len(header) > 1:
                        for i, col in enumerate(header[1:]):
                            idx_str = str(i + 1)
                            items.append((idx_str, col, f"Apply rotation modes from {col}"))
        except Exception:
            pass
    if not items:
        items.append(("0", "No valid columns", ""))
    return items

class DUMBTOOLS_OT_apply_bone_rot_modes_dialog(bpy.types.Operator):
    bl_idname = "dumbtools.apply_bone_rot_modes_dialog"
    bl_label = "Choose Column to Apply"
    bl_options = {'REGISTER', 'UNDO'}
    
    filepath: bpy.props.StringProperty(options={'HIDDEN'})
    
    column_index: bpy.props.EnumProperty(
        name="Rig Column",
        description="Choose which rig's rotation modes to apply",
        items=get_columns_callback
    )

    def invoke(self, context, event):
        # Try to default the enum to the active armature's name if present
        try:
            with open(self.filepath, mode='r', encoding='utf-8') as f:
                first_line = f.readline()
                if first_line and context.active_object:
                    header = list(csv.reader([first_line]))[0]
                    if context.active_object.name in header:
                        idx = header.index(context.active_object.name)
                        self.column_index = str(idx)
        except Exception:
            pass
            
        return context.window_manager.invoke_props_dialog(self)

    def execute(self, context):
        if self.column_index == "0":
            self.report({'ERROR'}, "No valid column selected.")
            return {'CANCELLED'}
            
        armature = context.active_object
        if not armature or armature.type != 'ARMATURE':
            self.report({'ERROR'}, "Active object must be an armature.")
            return {'CANCELLED'}
            
        try:
            col_idx = int(self.column_index)
            target_name = ""
            
            with open(self.filepath, mode='r', newline='', encoding='utf-8') as f:
                reader = csv.reader(f)
                header = next(reader, None)
                if header and len(header) > col_idx:
                    target_name = header[col_idx]
                
                applied_count = 0
                missing_bones = 0
                
                for row in reader:
                    if len(row) <= col_idx:
                        continue
                        
                    bone_name = row[0]
                    rot_mode = row[col_idx]
                    
                    if rot_mode == "N/A" or not rot_mode:
                        continue
                        
                    if bone_name in armature.pose.bones:
                        try:
                            armature.pose.bones[bone_name].rotation_mode = rot_mode
                            applied_count += 1
                        except TypeError:
                            self.report({'WARNING'}, f"Invalid rotation mode '{rot_mode}' for bone '{bone_name}'.")
                    else:
                        missing_bones += 1
                        
                self.report({'INFO'}, f"Applied {applied_count} modes from '{target_name}'. {missing_bones} bones skipped.")
                
        except Exception as e:
            self.report({'ERROR'}, f"Failed to apply CSV data: {e}")
            return {'CANCELLED'}
            
        return {'FINISHED'}


class DUMBTOOLS_OT_apply_bone_rot_modes_file(bpy.types.Operator, ImportHelper):
    """Load rotation modes and axis orders from a CSV file"""
    bl_idname = "dumbtools.apply_bone_rot_modes_file"
    bl_label = "Load Bone Rotation Modes (CSV)"
    bl_options = {'REGISTER', 'UNDO'}
    
    filename_ext = ".csv"
    filter_glob: bpy.props.StringProperty(
        default="*.csv",
        options={'HIDDEN'},
        maxlen=255,
    )
    
    @classmethod
    def poll(cls, context):
        return context.active_object and context.active_object.type == 'ARMATURE'

    def execute(self, context):
        bpy.ops.dumbtools.apply_bone_rot_modes_dialog('INVOKE_DEFAULT', filepath=self.filepath)
        return {'FINISHED'}


def register():
    try:
        bpy.utils.register_class(DUMBTOOLS_OT_apply_bone_rot_modes_dialog)
        bpy.utils.register_class(DUMBTOOLS_OT_apply_bone_rot_modes_file)
    except Exception:
        pass

def unregister():
    try:
        bpy.utils.unregister_class(DUMBTOOLS_OT_apply_bone_rot_modes_dialog)
        bpy.utils.unregister_class(DUMBTOOLS_OT_apply_bone_rot_modes_file)
    except Exception:
        pass

register()
bpy.ops.dumbtools.apply_bone_rot_modes_file('INVOKE_DEFAULT')
