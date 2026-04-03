# Tooltip: This script will reduce the mesh to the exact number of faces specified.

import bpy
import bmesh

def get_triangle_count(mesh_obj):
    bm = bmesh.new()
    bm.from_mesh(mesh_obj.data)
    triangle_count = sum(len(f.verts) - 2 for f in bm.faces)
    bm.free()
    return triangle_count

def decimate_to_triangle_count(mesh_obj, target_triangles, tolerance=5):
    # Ensure the object is in Object Mode
    bpy.ops.object.mode_set(mode='OBJECT')
    
    current_triangles = get_triangle_count(mesh_obj)

    if current_triangles <= target_triangles:
        print(f"Object already has {current_triangles} triangles, which is less than or equal to the target of {target_triangles}.")
        return

    # Initial ratio calculation
    ratio = target_triangles / current_triangles
    lower_bound, upper_bound = 0, 1

    while abs(current_triangles - target_triangles) > tolerance:
        # Apply the decimate modifier
        decimate_modifier = mesh_obj.modifiers.new(name="Decimate", type='DECIMATE')
        decimate_modifier.ratio = ratio
        decimate_modifier.use_collapse_triangulate = True

        # Apply the modifier
        bpy.ops.object.modifier_apply(modifier=decimate_modifier.name)

        # Check the result
        current_triangles = get_triangle_count(mesh_obj)

        if current_triangles > target_triangles:
            upper_bound = ratio
            ratio = (ratio + lower_bound) / 2
        else:
            lower_bound = ratio
            ratio = (ratio + upper_bound) / 2

        # If we're within tolerance or can't improve further, break
        if abs(current_triangles - target_triangles) <= tolerance or upper_bound - lower_bound < 0.0001:
            break

        # Undo the modifier application to try again
        bpy.ops.ed.undo()

    print(f"Decimation complete. Final triangle count: {current_triangles}")

class OBJECT_OT_decimate_to_count(bpy.types.Operator):
    bl_idname = "object.decimate_to_count"
    bl_label = "Decimate to Face Count"
    bl_options = {'REGISTER', 'UNDO'}

    target_count: bpy.props.IntProperty(
        name="Target Face Count",
        description="Target number of faces after decimation",
        default=100,
        min=1
    )

    def execute(self, context):
        obj = context.active_object
        if obj and obj.type == 'MESH':
            decimate_to_triangle_count(obj, self.target_count)
        else:
            self.report({'ERROR'}, "No valid mesh object selected.")
        return {'FINISHED'}

    def invoke(self, context, event):
        return context.window_manager.invoke_props_dialog(self)



def menu_func(self, context):
    self.layout.operator(OBJECT_OT_decimate_to_count.bl_idname)

def register():
    bpy.utils.register_class(OBJECT_OT_decimate_to_count)
    bpy.types.VIEW3D_MT_object.append(menu_func)

def unregister():
    bpy.utils.unregister_class(OBJECT_OT_decimate_to_count)
    bpy.types.VIEW3D_MT_object.remove(menu_func)

if __name__ == "__main__":
    register()
    # Add this line to invoke the operator
    bpy.ops.object.decimate_to_count('INVOKE_DEFAULT')

