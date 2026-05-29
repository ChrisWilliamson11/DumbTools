import bpy
import csv
from bpy_extras.io_utils import ExportHelper

class DUMBTOOLS_OT_compare_bone_rotation_modes(bpy.types.Operator, ExportHelper):
    """Compare rotation modes and axis orders of bones across selected armatures and export to CSV"""
    bl_idname = "dumbtools.compare_bone_rot_modes"
    bl_label = "Export Bone Rotation Modes to CSV"
    bl_options = {'REGISTER', 'UNDO'}
    
    filename_ext = ".csv"
    filter_glob: bpy.props.StringProperty(
        default="*.csv",
        options={'HIDDEN'},
        maxlen=255,
    )
    
    @classmethod
    def poll(cls, context):
        return any(obj.type == 'ARMATURE' for obj in context.selected_objects)

    def execute(self, context):
        armatures = [obj for obj in context.selected_objects if obj.type == 'ARMATURE']
        
        if not armatures:
            self.report({'WARNING'}, "No armatures selected.")
            return {'CANCELLED'}
            
        # Collect all unique bone names across all selected armatures
        all_bone_names = set()
        for arm in armatures:
            for bone in arm.pose.bones:
                all_bone_names.add(bone.name)
                
        all_bone_names = sorted(list(all_bone_names))
        
        # Prepare data for CSV
        header = ["Bone Name"] + [arm.name for arm in armatures]
        rows = []
        
        for bone_name in all_bone_names:
            row = [bone_name]
            for arm in armatures:
                # Check if this bone exists in the current armature
                if bone_name in arm.pose.bones:
                    pose_bone = arm.pose.bones[bone_name]
                    # rotation_mode gives values like 'QUATERNION', 'XYZ', 'XZY', 'AXIS_ANGLE', etc.
                    # which represents both the mode and the axis order for Eulers.
                    rot_mode = pose_bone.rotation_mode
                    row.append(rot_mode)
                else:
                    # Bone doesn't exist in this armature
                    row.append("N/A")
            rows.append(row)
            
        # Write to CSV
        try:
            with open(self.filepath, mode='w', newline='', encoding='utf-8') as f:
                writer = csv.writer(f)
                writer.writerow(header)
                writer.writerows(rows)
            self.report({'INFO'}, f"Exported bone rotation modes to {self.filepath}")
        except Exception as e:
            self.report({'ERROR'}, f"Failed to write CSV: {e}")
            return {'CANCELLED'}
            
        return {'FINISHED'}

def register():
    try:
        bpy.utils.register_class(DUMBTOOLS_OT_compare_bone_rotation_modes)
    except Exception:
        pass

def unregister():
    try:
        bpy.utils.unregister_class(DUMBTOOLS_OT_compare_bone_rotation_modes)
    except Exception:
        pass

register()
bpy.ops.dumbtools.compare_bone_rot_modes('INVOKE_DEFAULT')
