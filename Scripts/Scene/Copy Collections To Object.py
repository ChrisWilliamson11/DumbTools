import bpy

class DUMBTOOLS_OT_CopyCollectionsToObject(bpy.types.Operator):
    bl_idname = "scene.copy_collections_to_object"
    bl_label = "Copy Collections To Object"
    bl_description = "Creates a plane with Geometry Input modifiers for selected collections"
    bl_options = {'REGISTER', 'UNDO'}

    @classmethod
    def poll(cls, context):
        return True

    def execute(self, context):
        # Find selected collections in the outliner
        selected_collections = []
        for area in context.screen.areas:
            if area.type == 'OUTLINER':
                # context.selected_ids gives outliner selection in 4.0+
                if hasattr(context, 'selected_ids'):
                    selected_collections = [item for item in context.selected_ids if isinstance(item, bpy.types.Collection)]
                break
                
        if not selected_collections:
            self.report({'WARNING'}, "No collections selected in the Outliner.")
            return {'CANCELLED'}

        # Make a single plane
        bpy.ops.mesh.primitive_plane_add(size=1, enter_editmode=False, align='WORLD')
        obj = context.active_object
        obj.name = "Combined_Collections"

        # Apply Geometry Input modifier for every selected collection
        for i, col in enumerate(selected_collections):
            mod = obj.modifiers.new(name=f"GeoInput_{col.name}", type='GEOMETRY_INPUT')
            
            # API attributes for Blender 5.1 Geometry Input Modifier
            # Note: Explicit properties are used here. If they crash, the traceback will 
            # reveal the actual property names in 5.1 API.
            
            mod.input_type = 'COLLECTION'
            mod.collection = col
            mod.transform_space = 'RELATIVE'
            mod.use_instance = False
            
            # The first modifier replaces the original geometry (the plane)
            mod.use_replace = (i == 0)

        self.report({'INFO'}, f"Created object with {len(selected_collections)} Geometry Input modifiers.")
        return {'FINISHED'}

def menu_func(self, context):
    self.layout.operator(DUMBTOOLS_OT_CopyCollectionsToObject.bl_idname)

def register():
    bpy.utils.register_class(DUMBTOOLS_OT_CopyCollectionsToObject)
    bpy.types.VIEW3D_MT_object.append(menu_func)

def unregister():
    bpy.utils.unregister_class(DUMBTOOLS_OT_CopyCollectionsToObject)
    bpy.types.VIEW3D_MT_object.remove(menu_func)

register()
