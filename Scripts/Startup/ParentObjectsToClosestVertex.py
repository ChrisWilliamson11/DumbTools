# Tooltip: Parent all selected objects to the closest vertex of the active object

import bpy
import bmesh
from mathutils import Vector

class OBJECT_OT_VertexParentSet(bpy.types.Operator):
    bl_idname = "object.vertex_parent_set_closest"
    bl_label = "Parent selected objects to closest vertex of active object"
    bl_options = {'REGISTER', 'UNDO'}

    def execute(self, context):
        active_obj = context.active_object
        selected_objs = [obj for obj in context.selected_objects if obj != active_obj]

        for obj in selected_objs:
            # Store original world matrix BEFORE parenting
            orig_matrix_world = obj.matrix_world.copy()

            closest_vert_index = self.find_closest_vertex(active_obj, obj)
            if closest_vert_index is not None:
                obj.parent = active_obj
                obj.parent_type = 'VERTEX'
                obj.parent_vertices = [closest_vert_index, 0, 0]

                # Reset parent inverse so we have a clean base to restore from
                obj.matrix_parent_inverse.identity()

                # Let Blender evaluate the new parent chain before we restore position
                context.view_layer.update()

                # Restore world position — Blender decomposes this into the correct
                # local-space location/rotation/scale given the new vertex parent
                obj.matrix_world = orig_matrix_world

        return {'FINISHED'}

    def find_closest_vertex(self, parent, child):
        mesh = parent.data
        bm = bmesh.new()
        bm.from_mesh(mesh)

        closest_vert_index = None
        min_dist = float('inf')

        # Use matrix_world.translation so this works even if child already has a parent
        child_world_pos = child.matrix_world.translation

        for vert in bm.verts:
            vert_world_pos = parent.matrix_world @ vert.co
            distance = (vert_world_pos - child_world_pos).length
            if distance < min_dist:
                min_dist = distance
                closest_vert_index = vert.index

        bm.free()
        return closest_vert_index

def menu_func(self, context):
    self.layout.operator(OBJECT_OT_VertexParentSet.bl_idname)

def register():
    bpy.utils.register_class(OBJECT_OT_VertexParentSet)
    bpy.types.VIEW3D_MT_object_parent.append(menu_func)

def unregister():
    bpy.types.VIEW3D_MT_object_parent.remove(menu_func)
    bpy.utils.unregister_class(OBJECT_OT_VertexParentSet)

register()
