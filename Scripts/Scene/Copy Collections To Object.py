# Tooltip: Creates a plane with a Geometry Input modifier per collection selected in the Outliner. Each is set to Collection / Relative Space / no instances. The first replaces the original plane geometry.

import bpy

def main():
    # Gather collections selected in the Outliner
    selected_collections = [
        item for item in bpy.context.selected_ids
        if isinstance(item, bpy.types.Collection)
    ]

    if not selected_collections:
        print("✗ No collections selected in the Outliner.")
        return

    # Create a single plane as the base object
    bpy.ops.mesh.primitive_plane_add(size=1, enter_editmode=False, align='WORLD')
    obj = bpy.context.active_object
    obj.name = "Combined_Collections"

    for i, col in enumerate(selected_collections):
        # Add the Geometry Input modifier from the bundled Essentials asset library
        bpy.ops.object.modifier_add_node_group(
            asset_library_type='ESSENTIALS',
            asset_library_identifier="",
            relative_asset_identifier="nodes\\geometry_nodes_essentials.blend\\NodeTree\\Geometry Input"
        )

        # Grab the modifier that was just added (always appended last)
        mod = obj.modifiers[-1]

        # Socket_6 = Input Type
        mod["Socket_6"] = 'Collection'
        # Socket_3 = Collection reference
        mod["Socket_3"] = col
        # Socket_4 = Relative Space — ON
        mod["Socket_4"] = True
        # Socket_5 = As Instance — OFF
        mod["Socket_5"] = False
        # Socket_1 = Replace Original — ON for first modifier only (removes the plane geo)
        mod["Socket_1"] = (i == 0)

        label = " [Replace Original]" if i == 0 else ""
        print(f"  → Added Geometry Input for '{col.name}'{label}")

    print(f"✓ Created '{obj.name}' with {len(selected_collections)} Geometry Input modifier(s).")

main()
