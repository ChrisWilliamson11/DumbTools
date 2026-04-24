# Tooltip: Creates a plane with a Geometry Input modifier per collection selected in the Outliner
import bpy

class DUMBTOOLS_OT_CopyCollectionsToObject(bpy.types.Operator):
    bl_idname = "outliner.copy_collections_to_object"
    bl_label = "Copy Collections To Object"
    bl_description = "Creates a plane with a Geometry Input modifier for each selected collection. All set to Relative Space, no instances. First modifier replaces original geometry."
    bl_options = {'REGISTER', 'UNDO'}

    @classmethod
    def poll(cls, context):
        return any(isinstance(item, bpy.types.Collection) for item in context.selected_ids)

    def execute(self, context):
        selected_collections = [
            item for item in context.selected_ids
            if isinstance(item, bpy.types.Collection)
        ]

        if not selected_collections:
            self.report({'WARNING'}, "No collections selected in the Outliner.")
            return {'CANCELLED'}

        # Create a single plane as the base object
        bpy.ops.mesh.primitive_plane_add(size=1, enter_editmode=False, align='WORLD')
        obj = context.active_object
        obj.name = "Combined_Collections"

        for i, col in enumerate(selected_collections):
            # Add the Geometry Input modifier from the bundled Essentials asset library
            bpy.ops.object.modifier_add_node_group(
                asset_library_type='ESSENTIALS',
                asset_library_identifier="",
                relative_asset_identifier="nodes\\geometry_nodes_essentials.blend\\NodeTree\\Geometry Input"
            )

            # Grab the modifier that was just appended
            mod = obj.modifiers[-1]

            mod["Socket_6"] = 'Collection'   # Input Type
            mod["Socket_3"] = col            # Collection reference
            mod["Socket_4"] = True           # Relative Space — ON
            mod["Socket_5"] = False          # As Instance — OFF
            mod["Socket_1"] = (i == 0)       # Replace Original — ON for first only

            label = " [Replace Original]" if i == 0 else ""
            print(f"  → Added Geometry Input for '{col.name}'{label}")

        self.report({'INFO'}, f"Created '{obj.name}' with {len(selected_collections)} Geometry Input modifier(s).")
        return {'FINISHED'}


def draw_menu(self, context):
    self.layout.separator()
    self.layout.operator(DUMBTOOLS_OT_CopyCollectionsToObject.bl_idname)


def register():
    bpy.utils.register_class(DUMBTOOLS_OT_CopyCollectionsToObject)
    bpy.types.OUTLINER_MT_collection.append(draw_menu)


def unregister():
    bpy.types.OUTLINER_MT_collection.remove(draw_menu)
    if DUMBTOOLS_OT_CopyCollectionsToObject.is_registered:
        bpy.utils.unregister_class(DUMBTOOLS_OT_CopyCollectionsToObject)


register()
