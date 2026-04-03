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

        # Store original world space positions
        original_positions = {obj: obj.location.copy() for obj in selected_objs}

        for obj in selected_objs:
            # Calculate offset and parent to closest vertex
            offset, closest_vert_index = self.calculate_offset_and_closest_vertex(active_obj, obj)
            if closest_vert_index is not None:
                obj.parent = active_obj
                obj.parent_type = 'VERTEX'
                obj.parent_vertices = [closest_vert_index, 0, 0]

                # Move object to world origin
                obj.location = (0, 0, 0)

                # Apply offset in world space
                obj.location += active_obj.matrix_world @ offset

        return {'FINISHED'}

    def calculate_offset_and_closest_vertex(self, parent, child):
        mesh = parent.data
        bm = bmesh.new()
        bm.from_mesh(mesh)
        closest_vert_index = None
        min_dist = float('inf')
        child_location = child.location
        for vert in bm.verts:
            vert_world_position = parent.matrix_world @ vert.co
            distance = (vert_world_position - child_location).length
            if distance < min_dist:
                min_dist = distance
                closest_vert_index = vert.index
        bm.free()

        # Calculate offset in world space
        offset = child_location - parent.matrix_world @ mesh.vertices[closest_vert_index].co
        return offset, closest_vert_index

def menu_func(self, context):
    self.layout.operator(OBJECT_OT_VertexParentSet.bl_idname)

def register():
    bpy.utils.register_class(OBJECT_OT_VertexParentSet)
    bpy.types.VIEW3D_MT_object_parent.append(menu_func)

def unregister():
    bpy.types.VIEW3D_MT_object_parent.remove(menu_func)
    bpy.utils.unregister_class(OBJECT_OT_VertexParentSet)

register()
