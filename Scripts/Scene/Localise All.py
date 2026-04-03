# Tooltip: Find all linked libraries in the scene and make everything local. This will convert all linked objects, collections, materials, and other data to local data blocks.
import bpy

def make_all_linked_data_local():
    """
    Make all linked data in the scene local.
    This includes objects, collections, materials, meshes, and other data blocks.
    """

    # Track what we're making local for reporting
    made_local = {
        'objects': 0,
        'collections': 0,
        'materials': 0,
        'meshes': 0,
        'armatures': 0,
        'curves': 0,
        'lights': 0,
        'cameras': 0,
        'images': 0,
        'textures': 0,
        'node_groups': 0,
        'actions': 0,
        'other': 0
    }

    libraries_found = []

    print("Starting localization of all linked data...")

    # First, collect all libraries that are linked
    for library in bpy.data.libraries:
        libraries_found.append(library.name)
        print(f"Found linked library: {library.filepath}")

    if not libraries_found:
        print("No linked libraries found in the scene.")
        return made_local

    # Make objects local
    print("\nMaking objects local...")
    for obj in bpy.data.objects:
        if obj.library:
            print(f"  Making object local: {obj.name} (from {obj.library.name})")
            obj.make_local()
            made_local['objects'] += 1

    # Make collections local
    print("\nMaking collections local...")
    for collection in bpy.data.collections:
        if collection.library:
            print(f"  Making collection local: {collection.name} (from {collection.library.name})")
            collection.make_local()
            made_local['collections'] += 1

    # Make materials local
    print("\nMaking materials local...")
    for material in bpy.data.materials:
        if material.library:
            print(f"  Making material local: {material.name} (from {material.library.name})")
            material.make_local()
            made_local['materials'] += 1

    # Make meshes local
    print("\nMaking meshes local...")
    for mesh in bpy.data.meshes:
        if mesh.library:
            print(f"  Making mesh local: {mesh.name} (from {mesh.library.name})")
            mesh.make_local()
            made_local['meshes'] += 1

    # Make armatures local
    print("\nMaking armatures local...")
    for armature in bpy.data.armatures:
        if armature.library:
            print(f"  Making armature local: {armature.name} (from {armature.library.name})")
            armature.make_local()
            made_local['armatures'] += 1

    # Make curves local
    print("\nMaking curves local...")
    for curve in bpy.data.curves:
        if curve.library:
            print(f"  Making curve local: {curve.name} (from {curve.library.name})")
            curve.make_local()
            made_local['curves'] += 1

    # Make lights local
    print("\nMaking lights local...")
    for light in bpy.data.lights:
        if light.library:
            print(f"  Making light local: {light.name} (from {light.library.name})")
            light.make_local()
            made_local['lights'] += 1

    # Make cameras local
    print("\nMaking cameras local...")
    for camera in bpy.data.cameras:
        if camera.library:
            print(f"  Making camera local: {camera.name} (from {camera.library.name})")
            camera.make_local()
            made_local['cameras'] += 1

    # Make images local
    print("\nMaking images local...")
    for image in bpy.data.images:
        if image.library:
            print(f"  Making image local: {image.name} (from {image.library.name})")
            image.make_local()
            made_local['images'] += 1

    # Make textures local
    print("\nMaking textures local...")
    for texture in bpy.data.textures:
        if texture.library:
            print(f"  Making texture local: {texture.name} (from {texture.library.name})")
            texture.make_local()
            made_local['textures'] += 1

    # Make node groups local
    print("\nMaking node groups local...")
    for node_group in bpy.data.node_groups:
        if node_group.library:
            print(f"  Making node group local: {node_group.name} (from {node_group.library.name})")
            node_group.make_local()
            made_local['node_groups'] += 1

    # Make actions local
    print("\nMaking actions local...")
    for action in bpy.data.actions:
        if action.library:
            print(f"  Making action local: {action.name} (from {action.library.name})")
            action.make_local()
            made_local['actions'] += 1

    # Handle other data types that might be linked
    other_data_types = [
        ('fonts', bpy.data.fonts),
        ('sounds', bpy.data.sounds),
        ('speakers', bpy.data.speakers),
        ('grease_pencils', bpy.data.grease_pencils),
        ('movieclips', bpy.data.movieclips),
        ('masks', bpy.data.masks),
        ('linestyles', bpy.data.linestyles),
        ('brushes', bpy.data.brushes),
        ('palettes', bpy.data.palettes),
        ('paint_curves', bpy.data.paint_curves),
        ('workspaces', bpy.data.workspaces),
        ('screens', bpy.data.screens),
        ('window_managers', bpy.data.window_managers),
    ]

    print("\nMaking other data types local...")
    for data_type_name, data_collection in other_data_types:
        for data_block in data_collection:
            if hasattr(data_block, 'library') and data_block.library:
                try:
                    print(f"  Making {data_type_name[:-1]} local: {data_block.name} (from {data_block.library.name})")
                    data_block.make_local()
                    made_local['other'] += 1
                except Exception as e:
                    print(f"  Warning: Could not make {data_type_name[:-1]} '{data_block.name}' local: {e}")

    return made_local, libraries_found

def cleanup_unused_libraries():
    """
    Remove any libraries that are no longer being used after making data local.
    """
    print("\nCleaning up unused libraries...")

    # Get libraries that still exist
    libraries_to_remove = []
    for library in bpy.data.libraries:
        # Check if any data blocks still reference this library
        has_references = False

        # Check all data collections for references to this library
        data_collections = [
            bpy.data.objects, bpy.data.collections, bpy.data.materials, bpy.data.meshes,
            bpy.data.armatures, bpy.data.curves, bpy.data.lights, bpy.data.cameras,
            bpy.data.images, bpy.data.textures, bpy.data.node_groups, bpy.data.actions,
            bpy.data.fonts, bpy.data.sounds, bpy.data.speakers, bpy.data.grease_pencils,
            bpy.data.movieclips, bpy.data.masks, bpy.data.linestyles, bpy.data.brushes,
            bpy.data.palettes, bpy.data.paint_curves
        ]

        for collection in data_collections:
            for data_block in collection:
                if hasattr(data_block, 'library') and data_block.library == library:
                    has_references = True
                    break
            if has_references:
                break

        if not has_references:
            libraries_to_remove.append(library)
            print(f"  Marking library for removal: {library.filepath}")

    # Remove unused libraries
    for library in libraries_to_remove:
        try:
            bpy.data.libraries.remove(library)
            print(f"  Removed unused library: {library.filepath}")
        except Exception as e:
            print(f"  Warning: Could not remove library {library.filepath}: {e}")

def main():
    """
    Main function to localize all linked data and clean up.
    """
    print("=" * 60)
    print("LOCALIZING ALL LINKED DATA")
    print("=" * 60)

    # Make all linked data local
    made_local, libraries_found = make_all_linked_data_local()

    # Clean up unused libraries
    cleanup_unused_libraries()

    # Purge orphan data blocks
    print("\nPurging orphan data blocks...")
    bpy.ops.outliner.orphans_purge(do_local_ids=True, do_linked_ids=True, do_recursive=True)

    # Report results
    print("\n" + "=" * 60)
    print("LOCALIZATION COMPLETE")
    print("=" * 60)

    if libraries_found:
        print(f"Libraries processed: {len(libraries_found)}")
        for lib in libraries_found:
            print(f"  - {lib}")
    else:
        print("No linked libraries were found.")

    print(f"\nData blocks made local:")
    total_made_local = 0
    for data_type, count in made_local.items():
        if count > 0:
            print(f"  {data_type.capitalize()}: {count}")
            total_made_local += count

    if total_made_local == 0:
        print("  No linked data blocks found to localize.")
    else:
        print(f"\nTotal data blocks localized: {total_made_local}")

    print("\nAll linked data has been made local!")
    print("You may want to save your file now.")

# Run the main function
if __name__ == "__main__":
    main()