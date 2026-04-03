# Tooltip: Save and apply scene collection hierarchy as JSON; export current scene's collection tree with object lists, and import to match structure in another file.

import bpy
import json
from bpy.types import Operator, Panel
from bpy.props import StringProperty, BoolProperty
from bpy_extras.io_utils import ExportHelper, ImportHelper


def collection_to_dict(coll):
    """Serialize a Blender collection to a dict with name, objects, and children."""
    return {
        'name': coll.name,
        'objects': [obj.name for obj in coll.objects],
        'children': [collection_to_dict(child) for child in coll.children],
    }


def scene_hierarchy_to_dict(scene: bpy.types.Scene):
    return {
        'version': 1,
        'scene_name': scene.name,
        'root': collection_to_dict(scene.collection),
    }


def collect_all_object_names(node, out_set):
    out_set.update(node.get('objects', []))
    for child in node.get('children', []):
        collect_all_object_names(child, out_set)



def count_object_refs(node) -> int:
    """Count total object references in the JSON tree (not unique)."""
    total = len(node.get('objects', []))
    for child in node.get('children', []):
        total += count_object_refs(child)
    return total


def find_child_by_name(parent_coll: bpy.types.Collection, name: str):
    for c in parent_coll.children:
        if c.name == name:
            return c
    return None


def ensure_collection_under_parent(name: str, parent_coll: bpy.types.Collection):
    """Ensure a collection of given name exists and is linked under parent.
    Returns the (linked) collection datablock.
    """
    existing_child = find_child_by_name(parent_coll, name)
    if existing_child:
        return existing_child

    col = bpy.data.collections.get(name)
    if not col:
        col = bpy.data.collections.new(name)
    # Link under parent if not already
    if not any(c is col for c in parent_coll.children):
        parent_coll.children.link(col)
    return col



def get_leftovers_collection(scene: bpy.types.Scene, name: str = "Leftovers"):
    """Get or create a 'Leftovers' collection and ensure it's linked under the scene root."""
    col = bpy.data.collections.get(name)
    if not col:
        col = bpy.data.collections.new(name)
    if not any(c is col for c in scene.collection.children):
        try:
            scene.collection.children.link(col)
        except Exception:
            pass
    return col


def apply_hierarchy_node(node, parent_coll: bpy.types.Collection, json_object_names, strict_mode=False, is_root=False):
    """Apply node under parent collection.
    - When is_root=True, use the existing scene root collection directly (do not create another root).
    Returns a tuple:
      (collections_created, object_links_added, objects_already_in_place,
       missing_objects, child_collections_unlinked, child_collections_removed,
       object_links_removed)
    """
    created = 0
    linked = 0
    already = 0
    missing = 0
    unlinked_colls = 0
    removed_colls = 0
    unlinked_objs = 0

    # Determine the working collection for this node
    if is_root:
        coll = parent_coll  # use scene root as-is
    else:
        name = node.get('name', 'Collection')
        coll = find_child_by_name(parent_coll, name)
        if coll is None:
            # Try reuse existing by name anywhere, else create new
            coll_data = bpy.data.collections.get(name)
            if coll_data is None:
                coll_data = bpy.data.collections.new(name)
                created += 1
            if not any(c is coll_data for c in parent_coll.children):
                parent_coll.children.link(coll_data)
            coll = coll_data

    # Strict: remove child collections under this parent that aren't in JSON
    desired_child_names = {c.get('name') for c in node.get('children', []) if c.get('name')}
    if strict_mode:
        for child in list(coll.children):
            # Keep 'Leftovers' if present
            if child.name not in desired_child_names and child.name != "Leftovers":
                try:
                    coll.children.unlink(child)
                    unlinked_colls += 1
                except Exception:
                    pass
                # Attempt to remove the collection datablock if orphaned
                try:
                    if getattr(child, 'users', 0) == 0:
                        bpy.data.collections.remove(child)
                        removed_colls += 1
                except Exception:
                    pass

    # Enforce object membership for this collection
    desired = set(node.get('objects', []))

    # Link desired objects
    for obj_name in desired:
        obj = bpy.data.objects.get(obj_name)
        if obj is None:
            missing += 1
            continue
        if any(o is obj for o in coll.objects):
            already += 1
        else:
            try:
                coll.objects.link(obj)
                linked += 1
            except Exception:
                pass

    # Strict: unlink objects that are not desired in this collection
    if strict_mode:
        for o in list(coll.objects):
            if o.name not in desired:
                try:
                    coll.objects.unlink(o)
                    unlinked_objs += 1
                except Exception:
                    pass

    # Recurse into children
    for child_node in node.get('children', []):
        (c_created, c_linked, c_already, c_missing,
         c_unlinked_colls, c_removed_colls, c_unlinked_objs) = apply_hierarchy_node(
            child_node, coll, json_object_names, strict_mode, is_root=False
        )
        created += c_created
        linked += c_linked
        already += c_already
        missing += c_missing
        unlinked_colls += c_unlinked_colls
        removed_colls += c_removed_colls
        unlinked_objs += c_unlinked_objs

    return created, linked, already, missing, unlinked_colls, removed_colls, unlinked_objs


class SCENECOL_OT_export_collections(Operator, ExportHelper):
    """Save active scene's collection hierarchy to JSON"""
    bl_idname = "scene_hierarchy.export_collections"
    bl_label = "Save Collections JSON"
    bl_options = {"REGISTER"}

    filename_ext = ".json"
    filter_glob: StringProperty(default="*.json", options={'HIDDEN'})

    def execute(self, context):
        try:
            data = scene_hierarchy_to_dict(context.scene)
            with open(self.filepath, 'w', encoding='utf-8') as f:
                json.dump(data, f, indent=2)
            self.report({'INFO'}, f"Saved scene hierarchy to {self.filepath}")
            return {'FINISHED'}
        except Exception as e:
            self.report({'ERROR'}, f"Error saving JSON: {e}")
            return {'CANCELLED'}


class SCENECOL_OT_apply_collections(Operator, ImportHelper):
    """Load a JSON and match this scene's collection structure and object membership"""
    bl_idname = "scene_hierarchy.apply_collections"
    bl_label = "Apply Collections JSON"
    bl_options = {"REGISTER", "UNDO"}

    filename_ext = ".json"
    filter_glob: StringProperty(default="*.json", options={'HIDDEN'})

    strict_mode: BoolProperty(
        name="Strict Mode",
        description=(
            "Strict: Enforce both collections and objects. Unlink/remove child collections not in JSON; "
            "for each collection, unlink objects not listed for it. Objects not referenced anywhere "
            "in the JSON are linked to 'Leftovers'."
        ),
        default=True,
    )

    def execute(self, context):
        try:
            with open(self.filepath, 'r', encoding='utf-8') as f:
                data = json.load(f)

            root = data.get('root')
            if not root:
                self.report({'ERROR'}, "Invalid JSON: missing 'root'")
                return {'CANCELLED'}

            json_object_names = set()
            collect_all_object_names(root, json_object_names)
            refs_total = count_object_refs(root)

            created, linked, already, missing, unlinked_colls, removed_colls, unlinked_objs = apply_hierarchy_node(
                root, context.scene.collection, json_object_names, self.strict_mode, is_root=True
            )

            # Link any objects not present in JSON to a 'Leftovers' collection
            leftovers_linked = 0
            leftovers_coll = get_leftovers_collection(context.scene)
            for obj in bpy.data.objects:
                if (
                    obj.name not in json_object_names
                    and not any(o is obj for o in leftovers_coll.objects)
                ):
                    try:
                        leftovers_coll.objects.link(obj)
                        leftovers_linked += 1
                    except Exception:
                        pass

            # Refresh the depsgraph/view layer
            try:
                context.view_layer.update()
                context.evaluated_depsgraph_get().update()
            except Exception:
                pass

            matched_total = linked + already
            msg = (
                f"Collections created: {created}, Collections removed: {removed_colls} "
                f"(unlinked only: {unlinked_colls}), JSON refs: {refs_total}, "
                f"Objects matched: {matched_total} (linked: {linked}, already: {already}), "
                f"Object links removed: {unlinked_objs}, Missing from scene: {missing}, "
                f"Not in JSON → Leftovers: {leftovers_linked}"
            )
            self.report({'INFO'}, msg)
            return {'FINISHED'}

        except Exception as e:
            self.report({'ERROR'}, f"Error applying JSON: {e}")
            return {'CANCELLED'}


class SCENECOL_PT_panel(Panel):
    bl_label = "Scene Collection Hierarchy JSON"
    bl_idname = "SCENECOL_PT_panel"
    bl_space_type = 'VIEW_3D'
    bl_region_type = 'UI'
    bl_category = 'DumbTools'

    def draw(self, context):
        layout = self.layout
        col = layout.column(align=True)
        col.operator(SCENECOL_OT_export_collections.bl_idname, icon='EXPORT')
        row = col.row(align=True)
        op = row.operator(SCENECOL_OT_apply_collections.bl_idname, icon='IMPORT')
        # Set operator default from scene toggle
        op.strict_mode = getattr(context.scene, "scene_col_json_strict_mode", True)
        col.prop(context.scene, "scene_col_json_strict_mode", text="Strict Mode")


def register():
    # Register classes
    for cls in (SCENECOL_OT_export_collections, SCENECOL_OT_apply_collections, SCENECOL_PT_panel):
        try:
            bpy.utils.register_class(cls)
        except (ValueError, RuntimeError):
            pass
    # Scene toggle for panel/operator default
    if not hasattr(bpy.types.Scene, "scene_col_json_strict_mode"):
        bpy.types.Scene.scene_col_json_strict_mode = BoolProperty(
            name="Strict Mode",
            description=(
                "Strict: Enforce both collections and objects. Unlink/remove non-JSON child collections; "
                "unlink objects not listed for each collection. Non-JSON objects go to 'Leftovers'."
            ),
            default=True,
        )


def unregister():
    # Remove scene property
    if hasattr(bpy.types.Scene, "scene_col_json_strict_mode"):
        try:
            del bpy.types.Scene.scene_col_json_strict_mode
        except Exception:
            pass
    # Unregister classes (reverse order)
    for cls in (SCENECOL_PT_panel, SCENECOL_OT_apply_collections, SCENECOL_OT_export_collections):
        try:
            bpy.utils.unregister_class(cls)
        except (ValueError, RuntimeError):
            pass


# Auto-register when running from Text Editor
unregister()
register()

