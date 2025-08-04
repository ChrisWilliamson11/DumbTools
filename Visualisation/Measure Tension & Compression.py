# Tooltip: This will add a geometry nodes setup to the selected object(s) to visualise the tension and compression of the object's geometry.
import bpy

# File path to the Blender file containing the node groups and material
external_file_path = "S:/NON_PROJECT/ASSETS/3D/BlenderAssetLibrary/Geometry Nodes/TensionCompressionDistance.blend"

# Names of the node groups and material to append
node_group_top_name = "TCD_CaptureVertexData.001"
node_group_bottom_name = "TCD_DisplayData.001"
material_name = "TCD_DisplayVertexData.001"

# Function to append an item from the specified Blender file
def append_item(item_type, item_name, file_path):
    bpy.ops.wm.append(
        filepath=f"{file_path}\\{item_type}\\{item_name}",
        directory=f"{file_path}\\{item_type}\\",
        filename=item_name
    )

# Store currently selected objects
selected_objects = bpy.context.selected_objects[:]

# Append the node groups and material
append_item('NodeTree', node_group_top_name, external_file_path)
append_item('NodeTree', node_group_bottom_name, external_file_path)
append_item('Material', material_name, external_file_path)

# Re-select the objects that were selected before appending
for obj in selected_objects:
    obj.select_set(True)
    
# Ensure an object is selected
if bpy.context.selected_objects:
    # Ensure at least one object is selected
    if selected_objects:
        for obj in selected_objects:
            # Add Geometry Nodes modifier to the top of the stack
            geo_mod_top = obj.modifiers.new(name="GeoNodesTop", type='NODES')
            geo_mod_top.node_group = bpy.data.node_groups[node_group_top_name]
            
            # Move the top modifier to the top of the stack
            while obj.modifiers[0] != geo_mod_top:
                bpy.ops.object.modifier_move_up(modifier=geo_mod_top.name)
            
            # Add Geometry Nodes modifier to the bottom of the stack
            geo_mod_bottom = obj.modifiers.new(name="GeoNodesBottom", type='NODES')
            geo_mod_bottom.node_group = bpy.data.node_groups[node_group_bottom_name]
            
            # The bottom modifier is already at the bottom since it's the last added
            
            # Assign the material to the object
            if material_name in bpy.data.materials:
                mat = bpy.data.materials[material_name]
                if len(obj.data.materials) == 0:
                    obj.data.materials.append(mat)
                else:
                    obj.data.materials[0] = mat
else:
    print("No object selected.")
