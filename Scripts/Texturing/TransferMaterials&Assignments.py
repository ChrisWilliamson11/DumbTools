# Tooltip: Transfer materials and face assignments from the selected source object to the active target object

import bpy

# Ensure that two objects are selected: the source object and the active target object
if len(bpy.context.selected_objects) < 2:
    raise Exception("Please select two objects: one source (non-active) and the active target")

# The active object is the target
target_object = bpy.context.active_object
# Get the first selected object that is not the active object as the source
source_object = [obj for obj in bpy.context.selected_objects if obj != target_object][0]

# Clear the target object's material slots
if target_object.data.materials:
    target_object.data.materials.clear()

# Transfer materials from the source object to the target object
for mat in source_object.data.materials:
    target_object.data.materials.append(mat)

# Transfer face assignments if the mesh topologies match
if len(source_object.data.polygons) == len(target_object.data.polygons):
    for i, poly in enumerate(source_object.data.polygons):
        target_object.data.polygons[i].material_index = poly.material_index
else:
    print("Warning: Source and target objects do not have the same number of faces. Cannot transfer face assignments.")

    