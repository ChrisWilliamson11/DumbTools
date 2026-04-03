# Tooltip: This will add a geometry nodes setup which puts XY & Z dimensions on the selected object(s) to visualise the dimensions of the object's geometry.
import bpy
import os

# Get the base directory from DumbTools preferences
addon_prefs = bpy.context.preferences.addons["DumbTools"].preferences
base_dir = addon_prefs.script_folder


# File path to the Blender file containing the 'DimensionObject'
external_file_path = os.path.join(base_dir, "Docs", "Assets", "DimensionObject.blend")

# Name of the object to append
dimension_object_name = "DimensionObject"

# Function to append an item (object) from the specified Blender file
def append_item(file_path, item_name):
    bpy.ops.wm.append(
        filepath=f"{file_path}\\Object\\{item_name}",
        directory=f"{file_path}\\Object\\",
        filename=item_name
    )

# Function to duplicate an object and set a target object for its Geometry Nodes modifier
def duplicate_and_set_target(dimension_object, target_object):
    # Duplicate the Dimension object
    new_dimension_object = dimension_object.copy()
    new_dimension_object.data = dimension_object.data.copy()
    bpy.context.collection.objects.link(new_dimension_object)
    
    # Set the target object in the Geometry Nodes modifier
    if "GeometryNodes" in new_dimension_object.modifiers:
        new_dimension_object.modifiers["GeometryNodes"]["Socket_0"] = target_object
    else:
        print(f"The duplicated Dimension object does not have a Geometry Nodes modifier.")
    
    return new_dimension_object

# Ensure an object is selected to be the target
selected_objects = bpy.context.selected_objects[:].copy()
if not selected_objects:
    print("No object selected.")
else:
    # Append the 'DimensionObject' to the current scene
    append_item(external_file_path, dimension_object_name)
    
    # Retrieve the appended 'DimensionObject'
    dimension_object = bpy.data.objects.get(dimension_object_name)
    
    if dimension_object:
        # Duplicate the 'DimensionObject' for each selected object and set it as the target
        for target_obj in selected_objects:
            new_dimension_obj = duplicate_and_set_target(dimension_object, target_obj)
            bpy.context.view_layer.objects.active = new_dimension_obj
            bpy.ops.object.select_all(action='DESELECT')
            new_dimension_obj.select_set(True)
        # Delete the original appended 'DimensionObject'
        bpy.data.objects.remove(dimension_object, do_unlink=True)
    else:
        print(f"'{dimension_object_name}' was not found in the scene.")
