# Tooltip: If you have x2 collections of objects with the same names (ignoring suffixes .001, .002 etc), this will copy the materials from the objects in the first collection to the objects in the second collection.
import bpy

class CopyMaterialsOperator(bpy.types.Operator):
    """Copy Materials from Source to Target Collection"""
    bl_idname = "object.copy_materials"
    bl_label = "Copy Materials Between Collections"
    bl_options = {'REGISTER', 'UNDO'}

    # These functions are used to update the drop-down list of collections
    def get_collections(self, context):
        items = [(coll.name, coll.name, "") for coll in bpy.data.collections]
        return items

    source_collection: bpy.props.EnumProperty(
        name="Source Collection",
        description="Collection to copy materials from",
        items=get_collections
    )

    target_collection: bpy.props.EnumProperty(
        name="Target Collection",
        description="Collection to copy materials to",
        items=get_collections
    )

    def execute(self, context):
        source_collection = bpy.data.collections.get(self.source_collection)
        target_collection = bpy.data.collections.get(self.target_collection)
        
        if not source_collection or not target_collection:
            self.report({'ERROR'}, f"Either {self.source_collection} or {self.target_collection} is not found!")
            return {'CANCELLED'}

        # Function to copy materials (same as you provided earlier)
        copy_materials_from_source_to_target(source_collection, target_collection)
        self.report({'INFO'}, f"Materials copied from {self.source_collection} to {self.target_collection}.")
        return {'FINISHED'}

    def invoke(self, context, event):
        return context.window_manager.invoke_props_dialog(self)

def get_base_name(name):
    """
    Removes any numeric suffix from the object's name to get the base name.
    For example: 'Cube.001' will return 'Cube'
    """
    if "." in name and name.split(".")[-1].isdigit():
        return ".".join(name.split(".")[:-1])
    return name

def copy_materials_from_source_to_target(source_collection, target_collection):
    """
    Copies materials from objects in the source collection to objects in the target collection
    matching by name (ignoring number suffixes).
    """
    unmatched_objects = []  # To store names of source objects without a match in target collection

    for source_obj in source_collection.objects:
        base_name = get_base_name(source_obj.name)
        found_match = False
        for target_obj in target_collection.objects:
            if get_base_name(target_obj.name) == base_name:
                # Clear materials on target object
                target_obj.data.materials.clear()
                # Copy materials from source to target
                for mat in source_obj.data.materials:
                    target_obj.data.materials.append(mat)
                found_match = True
                break
        
        if not found_match:
            unmatched_objects.append(source_obj.name)

    if unmatched_objects:
        print("Objects in source collection without a match in target collection:")
        for obj_name in unmatched_objects:
            print(f" - {obj_name}")
    else:
        print("All objects from source collection found a match in target collection.")

def register():
    # Check if the class is already registered
    if "CopyMaterialsOperator" not in bpy.types.Operator.__subclasses__():
        bpy.utils.register_class(CopyMaterialsOperator)
    else:
        print("CopyMaterialsOperator is already registered")

# Unregister function remains the same
def unregister():
    if "CopyMaterialsOperator" in bpy.types.Operator.__subclasses__():
        bpy.utils.unregister_class(CopyMaterialsOperator)

# Call the register function
register()

# Now you can safely call your operator
bpy.ops.object.copy_materials('INVOKE_DEFAULT')
