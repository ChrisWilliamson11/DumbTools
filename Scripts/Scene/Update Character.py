import bpy
import os
from bpy_extras.io_utils import ImportHelper
from bpy.props import StringProperty, BoolProperty, CollectionProperty, EnumProperty
from bpy.types import Operator

# -------------------------------------------------------------------
# NLA Copying Logic (Ported from NLA/Copy NLA tracks.py)
# -------------------------------------------------------------------

def _safe_set(obj, attr, value):
    if hasattr(obj, attr):
        try:
            setattr(obj, attr, value)
        except Exception:
            pass

def _copy_attrs(dst, src, attrs):
    for a in attrs:
        if hasattr(src, a) and hasattr(dst, a):
            try:
                setattr(dst, a, getattr(src, a))
            except Exception:
                pass

def _copy_influence_keyframes(dst_strip, src_strip):
    """Copy animated influence keyframes from src_strip to dst_strip."""
    if dst_strip is None or src_strip is None:
        return

    src_id = getattr(src_strip, "id_data", None)
    dst_id = getattr(dst_strip, "id_data", None)
    if src_id is None or dst_id is None:
        return

    src_path = None
    dst_path = None
    try:
        src_path = src_strip.path_from_id("influence")
    except Exception:
        pass
    try:
        dst_path = dst_strip.path_from_id("influence")
    except Exception:
        pass

    src_fc = None
    try:
        strip_fcurves = getattr(src_strip, "fcurves", None)
        if strip_fcurves:
            if src_path:
                for fc in strip_fcurves:
                    dp = getattr(fc, "data_path", "")
                    ai = getattr(fc, "array_index", 0)
                    if dp == src_path and ai == 0:
                        src_fc = fc
                        break
            if src_fc is None:
                for fc in strip_fcurves:
                    dp = getattr(fc, "data_path", "")
                    ai = getattr(fc, "array_index", 0)
                    if dp.endswith("influence") and ai == 0:
                        src_fc = fc
                        break
    except Exception:
        pass

    if src_fc is None:
        src_anim = getattr(src_id, "animation_data", None)
        src_action = getattr(src_anim, "action", None) if src_anim else None
        if src_action:
            try:
                if src_path:
                    src_fc = src_action.fcurves.find(src_path, index=0)
            except Exception:
                src_fc = None
            if src_fc is None:
                try:
                    for fc in src_action.fcurves:
                        if getattr(fc, "array_index", 0) != 0:
                            continue
                        dp = getattr(fc, "data_path", "")
                        if dp.endswith("influence"):
                            if src_path and dp != src_path:
                                continue
                            src_fc = fc
                            break
                except Exception:
                    pass

    if not src_fc or len(getattr(src_fc, "keyframe_points", [])) == 0:
        return

    try:
        if not getattr(dst_id, "animation_data", None):
            dst_id.animation_data_create()
    except Exception:
        pass
    _safe_set(dst_strip, "use_animated_influence", True)

    try:
        dst_fc_existing = None
        dst_strip_fcurves = getattr(dst_strip, "fcurves", None)
        if dst_strip_fcurves:
            if dst_path:
                for fc in dst_strip_fcurves:
                    dp = getattr(fc, "data_path", "")
                    ai = getattr(fc, "array_index", 0)
                    if dp == dst_path and ai == 0:
                        dst_fc_existing = fc
                        break
            if dst_fc_existing is None:
                for fc in dst_strip_fcurves:
                    dp = getattr(fc, "data_path", "")
                    ai = getattr(fc, "array_index", 0)
                    if dp.endswith("influence") and ai == 0:
                        dst_fc_existing = fc
                        break
        if dst_fc_existing:
            try:
                for i in range(len(dst_fc_existing.keyframe_points) - 1, -1, -1):
                    dst_fc_existing.keyframe_points.remove(
                        dst_fc_existing.keyframe_points[i]
                    )
                dst_fc_existing.update()
            except Exception:
                pass
    except Exception:
        pass

    for kp in list(src_fc.keyframe_points):
        frame = float(kp.co[0])
        value = float(kp.co[1])
        try:
            dst_strip.influence = value
        except Exception:
            pass
        try:
            dst_strip.keyframe_insert(data_path="influence", frame=frame)
        except Exception:
            pass

    dst_fc = None
    try:
        dst_strip_fcurves = getattr(dst_strip, "fcurves", None)
        if dst_strip_fcurves:
            if dst_path:
                for fc in dst_strip_fcurves:
                    if getattr(fc, "data_path", "") == dst_path and getattr(fc, "array_index", 0) == 0:
                        dst_fc = fc
                        break
            if dst_fc is None:
                for fc in dst_strip_fcurves:
                    if getattr(fc, "data_path", "").endswith("influence") and getattr(fc, "array_index", 0) == 0:
                        dst_fc = fc
                        break
    except Exception:
        dst_fc = None

    if dst_fc and len(dst_fc.keyframe_points) == len(src_fc.keyframe_points):
        for i, kp in enumerate(src_fc.keyframe_points):
            dkp = dst_fc.keyframe_points[i]
            _safe_set(
                dkp,
                "interpolation",
                getattr(kp, "interpolation", getattr(dkp, "interpolation", None)),
            )
            if hasattr(kp, "easing"):
                _safe_set(dkp, "easing", getattr(kp, "easing", getattr(dkp, "easing", None)))
            for attr in ("handle_left_type", "handle_right_type"):
                if hasattr(kp, attr):
                    _safe_set(dkp, attr, getattr(kp, attr))
            try:
                dkp.handle_left = kp.handle_left
                dkp.handle_right = kp.handle_right
            except Exception:
                try:
                    dkp.handle_left[0] = kp.handle_left[0]
                    dkp.handle_left[1] = kp.handle_left[1]
                    dkp.handle_right[0] = kp.handle_right[0]
                    dkp.handle_right[1] = kp.handle_right[1]
                except Exception:
                    pass
        try:
            dst_fc.update()
        except Exception:
            pass

def copy_nla_animation(source_armature, target_armature):
    if (
        not source_armature.animation_data
        or not source_armature.animation_data.nla_tracks
    ):
        return

    if not target_armature.animation_data:
        target_armature.animation_data_create()

    if target_armature.animation_data and target_armature.animation_data.nla_tracks:
        for tr in list(target_armature.animation_data.nla_tracks):
            target_armature.animation_data.nla_tracks.remove(tr)

    for track in source_armature.animation_data.nla_tracks:
        new_track = target_armature.animation_data.nla_tracks.new()
        new_track.name = track.name

        _copy_attrs(
            new_track,
            track,
            [
                "is_solo",
                "mute",
                "lock",
                "select",
            ],
        )
        if hasattr(track, "solo") and hasattr(new_track, "solo"):
            _safe_set(new_track, "solo", getattr(track, "solo"))

        for strip in track.strips:
            new_strip = new_track.strips.new(
                name=strip.name,
                start=int(strip.frame_start),
                action=strip.action,
            )

            _safe_set(new_strip, "frame_start", float(getattr(strip, "frame_start", new_strip.frame_start)))
            _safe_set(new_strip, "frame_end", float(getattr(strip, "frame_end", new_strip.frame_end)))
            _safe_set(new_strip, "action_frame_start", getattr(strip, "action_frame_start", new_strip.action_frame_start))
            _safe_set(new_strip, "action_frame_end", getattr(strip, "action_frame_end", new_strip.action_frame_end))
            _safe_set(new_strip, "scale", getattr(strip, "scale", new_strip.scale))
            _safe_set(new_strip, "repeat", getattr(strip, "repeat", new_strip.repeat))
            _safe_set(new_strip, "blend_in", getattr(strip, "blend_in", new_strip.blend_in))
            _safe_set(new_strip, "blend_out", getattr(strip, "blend_out", new_strip.blend_out))
            _safe_set(new_strip, "blend_type", getattr(strip, "blend_type", getattr(new_strip, "blend_type", None)))
            _safe_set(new_strip, "extrapolation", getattr(strip, "extrapolation", getattr(new_strip, "extrapolation", None)))
            _safe_set(new_strip, "use_animated_influence", getattr(strip, "use_animated_influence", getattr(new_strip, "use_animated_influence", False)))
            _safe_set(new_strip, "use_animated_time", getattr(strip, "use_animated_time", getattr(new_strip, "use_animated_time", False)))
            _safe_set(new_strip, "influence", getattr(strip, "influence", getattr(new_strip, "influence", 1.0)))

            _copy_influence_keyframes(new_strip, strip)

            _safe_set(new_strip, "mute", getattr(strip, "mute", getattr(new_strip, "mute", False)))
            _safe_set(new_strip, "select", getattr(strip, "select", getattr(new_strip, "select", False)))


# -------------------------------------------------------------------
# Update Character Logic
# -------------------------------------------------------------------

# Temporary storage for collection list between operators
_temp_collections = []

class SCENE_OT_choose_collection_popup(Operator):
    """Choose which collection to link"""
    bl_idname = "scene.update_character_choose_collection"
    bl_label = "Choose Collection"
    bl_options = {'REGISTER', 'INTERNAL'}
    
    filepath: StringProperty()
    
    def get_items(self, context):
        global _temp_collections
        items = []
        for name in _temp_collections:
            items.append((name, name, ""))
        return items
    
    collection_name: EnumProperty(
        name="Collection",
        description="Select the collection to link",
        items=get_items
    )
    
    def invoke(self, context, event):
        return context.window_manager.invoke_props_dialog(self)

    def execute(self, context):
        return bpy.ops.scene.update_character_process(
            filepath=self.filepath, 
            collection_name=self.collection_name
        )


class SCENE_OT_update_character_process(Operator):
    """Process the Link and Update"""
    bl_idname = "scene.update_character_process"
    bl_label = "Update Character"
    bl_options = {'REGISTER', 'UNDO'}
    
    filepath: StringProperty()
    collection_name: StringProperty()
    
    def execute(self, context):
        source_armature = context.active_object
        if not source_armature or source_armature.type != 'ARMATURE':
            self.report({'ERROR'}, "Active object must be an Armature")
            return {'CANCELLED'}
        
        # 1. Link Collection
        self.report({'INFO'}, f"Linking {self.collection_name} from {self.filepath}")
        
        with bpy.data.libraries.load(self.filepath, link=True) as (data_from, data_to):
            if self.collection_name in data_from.collections:
                data_to.collections = [self.collection_name]
            else:
                self.report({'ERROR'}, f"Collection '{self.collection_name}' not found in {self.filepath}")
                return {'CANCELLED'}
        
        linked_col = data_to.collections[0]
        
        # 2. Match Hierarchy
        # Find parent collection of source_armature
        dest_collection = context.scene.collection # Default
        if len(source_armature.users_collection) > 0:
            candidate = source_armature.users_collection[0]
            # Check if the collection is overridden (read-only)
            if hasattr(candidate, "override_library") and candidate.override_library:
                self.report({'WARNING'}, f"Collection '{candidate.name}' is overridden. Placing new character in Scene Collection.")
            else:
                dest_collection = candidate
            
        # Create Instance
        instance_obj = bpy.data.objects.new(linked_col.name, None)
        instance_obj.instance_type = 'COLLECTION'
        instance_obj.instance_collection = linked_col
        
        try:
            dest_collection.objects.link(instance_obj)
        except RuntimeError:
             # Fallback just in case
            self.report({'WARNING'}, f"Could not link to '{dest_collection.name}'. Placing in Scene Collection.")
            context.scene.collection.objects.link(instance_obj)

        
        # 3. Enable Library Override
        # Select ONLY the instance object
        bpy.ops.object.select_all(action='DESELECT')
        instance_obj.select_set(True)
        context.view_layer.objects.active = instance_obj
        
        # Snapshot objects before override
        objects_before = set(context.scene.objects)
        
        # Create Override
        bpy.ops.object.make_override_library()
        
        # Snapshot objects after override
        objects_after = set(context.scene.objects)
        new_objects = objects_after - objects_before
        
        # 4. Find the matching armature in the newly created override hierarchy
        new_armature = None
        
        # DEBUG LOGGING
        print(f"DEBUG: Linked Collection Objects: {[o.name for o in linked_col.all_objects]}")
        print(f"DEBUG: New Objects Created: {[o.name for o in new_objects]}")
        
        # Strategy: Look at the actual objects inside the linked collection to find the armature name
        # Then find the corresponding object in the overridden selection
        
        target_armature_original_name = None
        
        # Find armatures in the linked collection
        # Note: linked_col.all_objects gives all objects in hierarchy
        armatures_in_col = [o for o in linked_col.all_objects if o.type == 'ARMATURE']
        
        if armatures_in_col:
            # Try to match the source armature's name (without suffix)
            source_base = source_armature.name.split('.')[0]
            
            for arm in armatures_in_col:
                if arm.name == source_base:
                    target_armature_original_name = arm.name
                    break
            
            # Fallback: just use the first one if no name match
            if not target_armature_original_name:
                target_armature_original_name = armatures_in_col[0].name
        
        print(f"DEBUG: Target Armature Original Name: {target_armature_original_name}")

        # Now find the corresponding object in the new selection (the overrides)

        if target_armature_original_name:
             # Search within the new_objects we detected
             
             candidates = [obj for obj in new_objects if obj.type == 'ARMATURE']
             
             # Priority 1: Exact match of original name
             for obj in candidates:
                 if obj.name == target_armature_original_name:
                     new_armature = obj
                     break
            
             # Priority 2: Check if name starts with original name
             if not new_armature:
                 for obj in candidates:
                     # Check if obj.name looks like "OriginalName.001"
                     if obj.name.startswith(target_armature_original_name):
                         new_armature = obj
                         break
                         
        # Fallback Heuristic: Just pick the first new armature if all else fails
        if not new_armature:
             candidates = [obj for obj in new_objects if obj.type == 'ARMATURE']
             if candidates:
                 new_armature = candidates[0]
            
        if not new_armature:
            print("DEBUG: FAILED to find armature.")
            self.report({'WARNING'}, "Could not find an Armature in the linked collection override.")
            return {'FINISHED'} 
            
        # 5. Align Transform
        new_armature.matrix_world = source_armature.matrix_world
        
        # 6. Copy Action
        if source_armature.animation_data and source_armature.animation_data.action:
            if not new_armature.animation_data:
                new_armature.animation_data_create()
            new_armature.animation_data.action = source_armature.animation_data.action

        # Copy Parent relationship
        if source_armature.parent:
            new_armature.parent = source_armature.parent
            new_armature.matrix_parent_inverse = source_armature.matrix_parent_inverse.copy()
            
        # 7. Copy NLA
        copy_nla_animation(source_armature, new_armature)
        
        self.report({'INFO'}, f"Updated character with {linked_col.name}")
        return {'FINISHED'}


class SCENE_OT_update_character(Operator, ImportHelper):
    """Update Character Rig: Select the new .blend file"""
    bl_idname = "scene.update_character"
    bl_label = "Update Character"
    bl_options = {'REGISTER', 'UNDO'}

    filter_glob: StringProperty(
        default="*.blend",
        options={'HIDDEN'},
        maxlen=255,
    )

    def execute(self, context):
        global _temp_collections
        collections = []
        try:
            with bpy.data.libraries.load(self.filepath, link=True) as (data_from, data_to):
                collections = data_from.collections
        except Exception as e:
            self.report({'ERROR'}, f"Failed to read file: {e}")
            return {'CANCELLED'}
        
        if not collections:
            self.report({'ERROR'}, "No collections found in selected file.")
            return {'CANCELLED'}
        
        # Filter out collections that look like overrides or helpers if necessary?
        # For now, show all.
        collections.sort()
        
        if len(collections) == 1:
            return bpy.ops.scene.update_character_process(filepath=self.filepath, collection_name=collections[0])
        else:
            # Pop up dialog to choose
            _temp_collections = collections
            # We call invoke_props_dialog via the operator
            bpy.ops.scene.update_character_choose_collection('INVOKE_DEFAULT', filepath=self.filepath)
            return {'FINISHED'}

def register():
    bpy.utils.register_class(SCENE_OT_choose_collection_popup)
    bpy.utils.register_class(SCENE_OT_update_character_process)
    bpy.utils.register_class(SCENE_OT_update_character)

def unregister():
    bpy.utils.unregister_class(SCENE_OT_choose_collection_popup)
    bpy.utils.unregister_class(SCENE_OT_update_character_process)
    bpy.utils.unregister_class(SCENE_OT_update_character)


try:
    register()
except Exception:
    pass # Already registered

# helper for testing
bpy.ops.scene.update_character('INVOKE_DEFAULT')
