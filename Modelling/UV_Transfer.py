# Tooltip: This script will transfer the UVs from the 'UVSource' collection to the 'Shards' collection.

import bpy

def add_data_transfer_modifier():
    # Get the collections
    shards_collection = bpy.data.collections.get("Shards")
    uv_source_collection = bpy.data.collections.get("UVSource")
    
    if not shards_collection or not uv_source_collection:
        print("Error: 'Shards' or 'UVSource' collection not found.")
        return
    
    # Iterate through objects in the Shards collection
    for shard in shards_collection.objects:
        # Find the matching UV source object
        uv_source_name = f"{shard.name}_UV"
        uv_source = uv_source_collection.objects.get(uv_source_name)
        
        if not uv_source:
            print(f"Warning: No matching UV source found for {shard.name}")
            continue
        
        # Add Data Transfer modifier
        modifier = shard.modifiers.new(name="DataTransfer", type='DATA_TRANSFER')
        
        # Set modifier properties
        modifier.object = uv_source
        modifier.use_object_transform = True
        
        # Transfer UVs
        
        
        modifier.use_loop_data = True 
        modifier.data_types_loops = {'UV'}
        modifier.loop_mapping = 'TOPOLOGY'
        
 # Enable UV transfer
        
        # Transfer Face Data
        #modifier.data_types_polys = {'SMOOTH'}
        #modifier.poly_mapping = 'TOPOLOGY'
        
        # Generate Data Layers
        bpy.context.view_layer.objects.active = shard
        bpy.ops.object.datalayout_transfer(modifier="DataTransfer")
        bpy.ops.object.modifier_apply(modifier="DataTransfer")

# Run the function
add_data_transfer_modifier()
