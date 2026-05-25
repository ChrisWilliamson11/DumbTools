# Tooltip: Parent all selected objects to the closest vertex of the active object

import bpy
from mathutils import Matrix

class OBJECT_OT_VertexParentSet(bpy.types.Operator):
    bl_idname = "object.vertex_parent_set_closest"
    bl_label = "Parent selected objects to closest vertex of active object"
    bl_options = {'REGISTER', 'UNDO'}

    def execute(self, context):
        active_obj = context.active_object
        selected_objs = [obj for obj in context.selected_objects if obj != active_obj]

        # Evaluated depsgraph gives us deformed/animated vertex positions
        depsgraph = context.evaluated_depsgraph_get()

        for obj in selected_objs:
            # Store original world translation before touching anything
            orig_world_pos = obj.matrix_world.translation.copy()

            closest_vert_index, vertex_world_pos = self.find_closest_vertex(
                active_obj, obj, depsgraph
            )
            if closest_vert_index is None:
                continue

            obj.parent = active_obj
            obj.parent_type = 'VERTEX'
            obj.parent_vertices = [closest_vert_index, 0, 0]
            obj.use_parent_final_indices = True
            obj.matrix_parent_inverse.identity()

            # PARVERT1 with identity matrix_parent_inverse:
            #   child_world_translation = vertex_world_pos + obj.location
            # So to keep the child exactly where it was:
            #   obj.location = orig_world_pos - vertex_world_pos
            # This is direct and avoids relying on view_layer.update() / matrix_world
            # setter which can use a stale runtime parent matrix cache.
            obj.location = orig_world_pos - vertex_world_pos

        return {'FINISHED'}

    def find_closest_vertex(self, parent, child, depsgraph):
        # evaluated_get() gives the mesh AFTER all modifiers/shape-keys/armatures,
        # so we compare against actual visible vertex positions, not the rest pose.
        eval_parent = parent.evaluated_get(depsgraph)
        eval_mesh = eval_parent.to_mesh()

        closest_vert_index = None
        min_dist = float('inf')
        child_world_pos = child.matrix_world.translation  # world pos even if child has a parent

        for i, vert in enumerate(eval_mesh.vertices):
            vert_world_pos = eval_parent.matrix_world @ vert.co
            dist = (vert_world_pos - child_world_pos).length
            if dist < min_dist:
                min_dist = dist
                closest_vert_index = i

        vertex_world_pos = None
        if closest_vert_index is not None:
            vertex_world_pos = (eval_parent.matrix_world @ eval_mesh.vertices[closest_vert_index].co).copy()

        eval_parent.to_mesh_clear()
        return closest_vert_index, vertex_world_pos


def menu_func(self, context):
    self.layout.operator(OBJECT_OT_VertexParentSet.bl_idname)

def register():
    bpy.utils.register_class(OBJECT_OT_VertexParentSet)
    bpy.types.VIEW3D_MT_object_parent.append(menu_func)

def unregister():
    bpy.types.VIEW3D_MT_object_parent.remove(menu_func)
    bpy.utils.unregister_class(OBJECT_OT_VertexParentSet)

register()
