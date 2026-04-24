# Tooltip: Creates a plane with a Geometry Input modifier per selected collection. Each modifier is set to Collection / Relative Space / no instances. The first one replaces the original geometry.

import bpy

def main():
    # Gather collections selected in the Outliner via selected_ids
    selected_collections = [
        item for item in bpy.context.selected_ids
        if isinstance(item, bpy.types.Collection)
    ]

    if not selected_collections:
        print("✗ No collections selected in the Outliner.")
        return

    # Create a single plane
    bpy.ops.mesh.primitive_plane_add(size=1, enter_editmode=False, align='WORLD')
    obj = bpy.context.active_object
    obj.name = "Combined_Collections"

    # Add a Geometry Input modifier per collection
    for i, col in enumerate(selected_collections):
        mod = obj.modifiers.new(name=f"GeoInput_{col.name}", type='GEOMETRY_INPUT')

        mod.input_type = 'COLLECTION'
        mod.collection = col
        mod.transform_space = 'RELATIVE'
        mod.use_instance = False

        # First modifier replaces the plane geometry; subsequent ones merge in
        mod.use_replace = (i == 0)

        print(f"  → Added modifier for collection '{col.name}'" + (" [Replace]" if i == 0 else ""))

    print(f"✓ Created '{obj.name}' with {len(selected_collections)} Geometry Input modifier(s).")

main()
