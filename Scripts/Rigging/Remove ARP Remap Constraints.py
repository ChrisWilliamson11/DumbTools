# Tooltip: Remove all Auto-Rig Pro REMAP constraints from the active armature

import bpy

class RIGGING_OT_remove_arp_constraints(bpy.types.Operator):
    """Remove all Auto-Rig Pro REMAP constraints from the active armature"""
    bl_idname = "rigging.remove_arp_constraints"
    bl_label = "Remove ARP Remap Constraints"
    bl_options = {'REGISTER', 'UNDO'}
    
    @classmethod
    def poll(cls, context):
        return context.active_object and context.active_object.type == 'ARMATURE'
        
    def execute(self, context):
        obj = context.active_object
        removed = 0
        
        for pbone in obj.pose.bones:
            to_remove = []
            for c in pbone.constraints:
                # Auto-Rig Pro appends "REMAP" to the constraints it creates
                if "REMAP" in c.name:
                    to_remove.append(c)
                # Fallback: if it targets another armature and is an external constraint
                elif hasattr(c, 'target') and c.target and c.target.type == 'ARMATURE' and c.target != obj:
                    to_remove.append(c)
                    
            for c in to_remove:
                pbone.constraints.remove(c)
                removed += 1
                
        self.report({'INFO'}, f"Removed {removed} retarget constraints from {obj.name}")
        return {'FINISHED'}

def register():
    try:
        bpy.utils.register_class(RIGGING_OT_remove_arp_constraints)
    except Exception:
        bpy.utils.unregister_class(RIGGING_OT_remove_arp_constraints)
        bpy.utils.register_class(RIGGING_OT_remove_arp_constraints)

def unregister():
    try:
        bpy.utils.unregister_class(RIGGING_OT_remove_arp_constraints)
    except Exception:
        pass

register()
bpy.ops.rigging.remove_arp_constraints()
