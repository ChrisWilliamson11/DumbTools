# SPDX-License-Identifier: MIT
# Make all linked library datablocks local
# Works in Blender 2.93+ (tested on 3.x/4.x APIs)

bl_info = {
    "name": "Make All Linked Datablocks Local",
    "author": "Augment Agent",
    "version": (1, 0, 0),
    "blender": (4, 5, 0),
    "location": "F3 Search > Make All Linked Datablocks Local",
    "description": "Traverses the entire .blend and makes any linked library datablocks local.",
    "category": "System",
}

import bpy
from bpy.types import Operator


def _iter_id_collections():
    """Yield (name, collection) for all ID collections in bpy.data.

    Prioritizes objects/collections first to create local users before their data.
    Skips bpy.data.libraries itself, since 'Library' isn't a make-local target.
    """
    priority = [
        "collections", "objects",
        "meshes", "materials", "node_groups",
        "armatures", "actions",
        "images", "textures",
        "curves", "cameras", "lights",
        "grease_pencils", "fonts", "worlds",
        "speakers", "lightprobes", "linestyles",
    ]
    seen = set()

    def get_valid(name):
        if name in seen or name == "libraries" or name.startswith("_"):
            return None
        if name in {"filepath", "is_saved", "is_dirty", "user_map", "window_managers", "screens"}:
            return None
        coll = getattr(bpy.data, name, None)
        if coll is None:
            return None
        ident = getattr(getattr(coll, "bl_rna", None), "identifier", "")
        if not ident.startswith("BlendData"):
            return None
        try:
            iter(coll)
        except TypeError:
            return None
        seen.add(name)
        return coll

    for name in priority:
        coll = get_valid(name)
        if coll:
            yield name, coll

    for name in dir(bpy.data):
        coll = get_valid(name)
        if coll:
            yield name, coll


def _make_local_try(idb) -> bool:
    """Make a single ID local.

    - If it is a library override, clear the override and keep its values.
    - If it is linked, make it local.
    Returns True if it ended up fully local (no library, no override).
    """
    # Case 1: Library override -> convert to plain local, adopting override values
    if getattr(idb, "override_library", None) is not None:
        try:
            ret = idb.make_local(clear_liboverride=True, clear_asset_data=True)
        except TypeError:
            # Older signatures without kwargs
            try:
                ret = idb.make_local()
            except Exception:
                return False
        except Exception:
            return False
        local_id = ret or idb
        return (getattr(local_id, "override_library", None) is None) and (getattr(local_id, "library", None) is None)

    # Case 2: Pure linked ID -> make local
    if getattr(idb, "library", None) is not None:
        try:
            ret = idb.make_local(clear_liboverride=True, clear_asset_data=True)
            local_id = ret or idb
            return getattr(local_id, "library", None) is None
        except TypeError:
            try:
                ret = idb.make_local()
                local_id = ret or idb
                return getattr(local_id, "library", None) is None
            except Exception:
                return False
        except Exception:
            return False

    return False


def make_all_linked_local(max_passes: int = 5, verbose: bool = True) -> int:
    """Make all linked (library) datablocks local, across the entire file.

    Runs up to max_passes to resolve dependencies (direct first, then indirect).
    Returns total number of successful make-local operations.
    """
    total_made = 0

    for pass_idx in range(max_passes):
        made_this_pass = 0
        # Collect overrides first, then linked (direct/indirect)
        overrides = []
        direct = []
        indirect = []
        for _, coll in _iter_id_collections():
            for idb in coll:
                if getattr(idb, "override_library", None) is not None:
                    overrides.append(idb)
                    continue
                lib = getattr(idb, "library", None)
                if lib is None:
                    continue
                if getattr(idb, "is_library_indirect", False):
                    indirect.append(idb)
                else:
                    direct.append(idb)

        # First convert overrides to plain local (adopt override values)
        for idb in overrides:
            if _make_local_try(idb):
                made_this_pass += 1

        # Then try direct linked ones
        for idb in direct:
            if _make_local_try(idb):
                made_this_pass += 1

        # Finally try indirect linked ones
        for idb in indirect:
            if _make_local_try(idb):
                made_this_pass += 1

        total_made += made_this_pass
        if verbose:
            print(f"[MakeLocal] Pass {pass_idx+1}: made local: {made_this_pass}")
        if made_this_pass == 0:
            break

    if verbose:
        # Final count of still externalized IDs (linked or overrides)
        remaining_linked = 0
        remaining_overrides = 0
        for _, coll in _iter_id_collections():
            for idb in coll:
                if getattr(idb, "library", None) is not None:
                    remaining_linked += 1
                elif getattr(idb, "override_library", None) is not None:
                    remaining_overrides += 1
        print(f"[MakeLocal] Total made local: {total_made}; Remaining linked: {remaining_linked}; Remaining overrides: {remaining_overrides}")

    return total_made


class AUGMENT_OT_make_all_linked_local(Operator):
    bl_idname = "wm.make_all_linked_datablocks_local"
    bl_label = "Make All Linked Datablocks Local"
    bl_options = {"REGISTER", "UNDO"}

    max_passes: bpy.props.IntProperty(
        name="Max Passes",
        description="How many dependency-resolution passes to attempt",
        default=5, min=1, max=50,
    )
    verbose: bpy.props.BoolProperty(
        name="Verbose",
        description="Print progress to the console",
        default=True,
    )

    def execute(self, context):
        made = make_all_linked_local(
            max_passes=self.max_passes,
            verbose=self.verbose,
        )
        self.report({'INFO'}, f"Made {made} datablocks local")
        return {'FINISHED'}


def menu_func(self, context):
    self.layout.operator(AUGMENT_OT_make_all_linked_local.bl_idname, icon='FILE_TICK')


def register():
    bpy.utils.register_class(AUGMENT_OT_make_all_linked_local)
    try:
        bpy.types.TOPBAR_MT_file.append(menu_func)
    except Exception:
        pass


def unregister():
    try:
        bpy.types.TOPBAR_MT_file.remove(menu_func)
    except Exception:
        pass
    bpy.utils.unregister_class(AUGMENT_OT_make_all_linked_local)



register()
make_all_linked_local()

