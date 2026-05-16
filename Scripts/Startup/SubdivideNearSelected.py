# Tooltip: Iteratively subdivide the active mesh near the vertices/points of all other selected objects
import bpy
import bmesh
from mathutils import kdtree


class MESH_OT_subdivide_near_selected(bpy.types.Operator):
    """Iteratively subdivide the active mesh closer to points of other selected objects.

    Works with mesh vertices and point cloud points as proximity sources.
    The active object is subdivided; all other selected objects provide
    the target points that drive subdivision density.
    """

    bl_idname = "mesh.subdivide_near_selected"
    bl_label = "Subdivide Near Selected"
    bl_options = {'REGISTER', 'UNDO'}

    max_iterations: bpy.props.IntProperty(
        name="Iterations",
        description="Number of subdivision passes (higher = finer detail near points)",
        default=5,
        min=1,
        max=50,
    )

    base_threshold: bpy.props.FloatProperty(
        name="Radius",
        description="Maximum effect radius in Blender units",
        default=4.0,
        min=0.001,
        soft_max=50.0,
        unit='LENGTH',
    )

    gamma: bpy.props.FloatProperty(
        name="Gamma",
        description=(
            "Controls how quickly the threshold shrinks per iteration. "
            "Values > 1 concentrate subdivisions closer to the target points"
        ),
        default=1.0,
        min=0.1,
        soft_max=5.0,
    )

    min_face_area: bpy.props.FloatProperty(
        name="Min Face Area",
        description=(
            "Faces smaller than this area (in Blender units²) will be "
            "skipped to prevent over-subdivision"
        ),
        default=0.0,
        min=0.0,
        soft_max=1.0,
    )

    # ------------------------------------------------------------------
    # UI
    # ------------------------------------------------------------------

    def draw(self, context):
        layout = self.layout
        layout.use_property_split = True
        layout.prop(self, "max_iterations")
        layout.prop(self, "base_threshold")
        layout.prop(self, "gamma")
        layout.prop(self, "min_face_area")

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    def _gather_target_points(self, context, active_obj):
        """Collect world-space points from every selected object except the active one.

        Supports MESH (vertices) and POINTCLOUD types.
        """
        points = []
        for obj in context.selected_objects:
            if obj is active_obj:
                continue

            mat = obj.matrix_world

            if obj.type == 'MESH' and obj.data.vertices:
                points.extend(mat @ v.co for v in obj.data.vertices)

            elif obj.type == 'POINTCLOUD' and obj.data.points:
                points.extend(mat @ p.position for p in obj.data.points)

            else:
                # Fallback: if the object has evaluated mesh data (curves,
                # surfaces, etc.) we can try to grab its depsgraph mesh.
                try:
                    depsgraph = context.evaluated_depsgraph_get()
                    eval_obj = obj.evaluated_get(depsgraph)
                    eval_mesh = eval_obj.to_mesh()
                    if eval_mesh and eval_mesh.vertices:
                        points.extend(mat @ v.co for v in eval_mesh.vertices)
                    eval_obj.to_mesh_clear()
                except Exception:
                    pass

        return points

    @staticmethod
    def _build_kdtree(points):
        kd = kdtree.KDTree(len(points))
        for i, pt in enumerate(points):
            kd.insert(pt, i)
        kd.balance()
        return kd

    # ------------------------------------------------------------------
    # Execute
    # ------------------------------------------------------------------

    def execute(self, context):
        active_obj = context.active_object

        if not active_obj or active_obj.type != 'MESH':
            self.report({'ERROR'}, "Active object must be a mesh.")
            return {'CANCELLED'}

        if len(context.selected_objects) < 2:
            self.report(
                {'ERROR'},
                "Select at least one other object to use as proximity target.",
            )
            return {'CANCELLED'}

        # --- Gather target points ----------------------------------
        target_points = self._gather_target_points(context, active_obj)
        if not target_points:
            self.report(
                {'WARNING'},
                "No target points found on the other selected objects.",
            )
            return {'CANCELLED'}

        kd = self._build_kdtree(target_points)

        # --- Work entirely in Object Mode via bmesh.new() ----------
        # Avoiding bpy.ops.object.mode_set() inside execute() is
        # critical: those calls push their own undo entries, which
        # makes *them* the "last operator" and hides our F9 panel.
        final_threshold = self.base_threshold

        for iteration in range(self.max_iterations):
            bm = bmesh.new()
            bm.from_mesh(active_obj.data)
            bm.faces.ensure_lookup_table()

            # Biased progression: higher gamma = effect concentrates closer
            progress = iteration / max(1, self.max_iterations - 1)
            biased_factor = (1.0 - progress) ** self.gamma
            current_threshold = self.base_threshold * biased_factor
            final_threshold = current_threshold

            mesh_matrix = active_obj.matrix_world
            faces_to_subdivide = []

            for face in bm.faces:
                # Optional area guard
                if self.min_face_area > 0.0 and face.calc_area() < self.min_face_area:
                    continue

                face_center_world = mesh_matrix @ face.calc_center_median()
                _, _, dist = kd.find(face_center_world)

                if dist < current_threshold:
                    faces_to_subdivide.append(face)

            if not faces_to_subdivide:
                bm.free()
                break

            edges_to_sub = list({e for f in faces_to_subdivide for e in f.edges})

            bmesh.ops.subdivide_edges(
                bm,
                edges=edges_to_sub,
                cuts=1,
                use_grid_fill=True,
            )

            bm.to_mesh(active_obj.data)
            bm.free()
            active_obj.data.update()

        face_count = len(active_obj.data.polygons)
        self.report(
            {'INFO'},
            f"Subdivision complete — {face_count} faces, "
            f"final threshold {final_threshold:.4f}",
        )
        return {'FINISHED'}

    def invoke(self, context, event):
        return self.execute(context)


# ------------------------------------------------------------------
# Menu entry & Registration (DumbTools Startup pattern)
# ------------------------------------------------------------------

def menu_draw(self, context):
    self.layout.operator(
        MESH_OT_subdivide_near_selected.bl_idname,
        text="Subdivide Near Selected",
        icon='MOD_SUBSURF',
    )


def register():
    try:
        bpy.utils.unregister_class(MESH_OT_subdivide_near_selected)
    except RuntimeError:
        pass
    bpy.utils.register_class(MESH_OT_subdivide_near_selected)
    bpy.types.VIEW3D_MT_object.append(menu_draw)


def unregister():
    bpy.utils.unregister_class(MESH_OT_subdivide_near_selected)
    bpy.types.VIEW3D_MT_object.remove(menu_draw)


register()
