# Tooltip: Adjust the timing of a selected Bullet Hit hierarchy to start at the current frame
import bpy

def iter_fcurves(action):
    if not action: return
    if hasattr(action, "fcurves") and action.fcurves:
        for fc in action.fcurves: yield fc
    if hasattr(action, "layers"):
        for layer in action.layers:
            if hasattr(layer, "strips"):
                for strip in layer.strips:
                    if hasattr(strip, "channelbags"):
                        for bag in strip.channelbags:
                            if hasattr(bag, "fcurves"):
                                for fc in bag.fcurves: yield fc
                    if hasattr(strip, "fcurves"):
                        for fc in strip.fcurves: yield fc
                    elif hasattr(strip, "channels"):
                         for fc in strip.channels: yield fc

def shift_action(action, delta):
    if not action: return
    for fc in iter_fcurves(action):
        for kp in fc.keyframe_points:
            kp.co[0] += delta
        fc.update()

def get_descendants(obj):
    descendants = []
    for child in obj.children:
        descendants.append(child)
        descendants.extend(get_descendants(child))
    return descendants

def get_start_frame(objs):
    candidates = []
    
    for obj in objs:
        # VDB
        if obj.type == 'VOLUME' and obj.data:
            try: candidates.append(obj.data.frame_start)
            except: pass
            
        # Alembic
        if obj.type in ('MESH', 'POINTCLOUD'):
            abc_mod = next((m for m in obj.modifiers if m.type == 'MESH_SEQUENCE_CACHE'), None)
            if abc_mod and abc_mod.cache_file:
                if abc_mod.cache_file.animation_data and abc_mod.cache_file.animation_data.action:
                    for fc in iter_fcurves(abc_mod.cache_file.animation_data.action):
                        if fc.data_path == "frame" or fc.data_path.endswith(".frame"):
                            if fc.keyframe_points:
                                candidates.append(fc.keyframe_points[0].co[0])
                else:
                    try: candidates.append(abc_mod.cache_file.frame_offset)
                    except: pass
                    
        # Object Actions
        if obj.animation_data and obj.animation_data.action:
            for fc in iter_fcurves(obj.animation_data.action):
                if fc.keyframe_points:
                    candidates.append(fc.keyframe_points[0].co[0])
                    
        if obj.data and getattr(obj.data, 'animation_data', None) and obj.data.animation_data.action:
            for fc in iter_fcurves(obj.data.animation_data.action):
                if fc.keyframe_points:
                    candidates.append(fc.keyframe_points[0].co[0])
                    
        # Materials
        if hasattr(obj, 'material_slots'):
            for slot in obj.material_slots:
                mat = slot.material
                if not mat or not mat.node_tree: continue
                nt = mat.node_tree
                
                if nt.animation_data and nt.animation_data.action:
                    for fc in iter_fcurves(nt.animation_data.action):
                        if 'image_user.frame_offset' in fc.data_path and fc.keyframe_points:
                            candidates.append(fc.keyframe_points[0].co[0])
                            
                for node in nt.nodes:
                    if getattr(node, 'type', '') == 'TEX_IMAGE' and hasattr(node, 'image_user') and getattr(node, 'image', None):
                        if node.image.source == 'SEQUENCE':
                            fs = getattr(node.image_user, 'frame_start', None)
                            if fs is not None:
                                candidates.append(fs)
                            
    if not candidates:
        return None
        
    return min(candidates)


class DUMBTOOLS_OT_adjust_hit_time(bpy.types.Operator):
    """Adjust the timing of the selected bullet hit hierarchy to start at the current frame"""
    bl_idname = "dumbtools.adjust_hit_time"
    bl_label = "Adjust Hit Time"
    bl_options = {'REGISTER', 'UNDO'}

    @classmethod
    def poll(cls, context):
        return context.active_object is not None

    def execute(self, context):
        # Only process top-level selected objects to avoid double processing
        selected_roots = [obj for obj in context.selected_objects if obj.parent not in context.selected_objects]
        
        if not selected_roots:
            self.report({'WARNING'}, "No valid objects selected.")
            return {'CANCELLED'}
            
        target_frame = context.scene.frame_current
        
        total_adjusted = 0
        
        for root in selected_roots:
            objs = [root] + get_descendants(root)
            start_frame = get_start_frame(objs)
            
            if start_frame is None:
                continue
                
            delta = target_frame - start_frame
            delta_int = int(round(delta))
            
            if delta == 0:
                continue
                
            # Shift everything by delta
            shifted_actions = set()
            shifted_materials = set()
            shifted_caches = set()
            
            for obj in objs:
                # Volume
                if obj.type == 'VOLUME' and obj.data:
                    try: obj.data.frame_start += delta_int
                    except: pass
                    
                # Alembic
                if obj.type in ('MESH', 'POINTCLOUD'):
                    abc_mod = next((m for m in obj.modifiers if m.type == 'MESH_SEQUENCE_CACHE'), None)
                    if abc_mod and abc_mod.cache_file:
                        cache = abc_mod.cache_file
                        if cache not in shifted_caches:
                            shifted_caches.add(cache)
                            shifted = False
                            if cache.animation_data and cache.animation_data.action:
                                act = cache.animation_data.action
                                if act not in shifted_actions:
                                    shifted_actions.add(act)
                                    for fc in iter_fcurves(act):
                                        if fc.data_path == "frame" or fc.data_path.endswith(".frame"):
                                            if fc.keyframe_points:
                                                for kp in fc.keyframe_points:
                                                    kp.co[0] += delta
                                                fc.update()
                                                shifted = True
                            if not shifted:
                                try: cache.frame_offset += delta_int
                                except: pass

                # Object Actions
                if obj.animation_data and obj.animation_data.action:
                    act = obj.animation_data.action
                    if act not in shifted_actions:
                        shifted_actions.add(act)
                        shift_action(act, delta)
                        
                if obj.data and getattr(obj.data, 'animation_data', None) and obj.data.animation_data.action:
                    act = obj.data.animation_data.action
                    if act not in shifted_actions:
                        shifted_actions.add(act)
                        shift_action(act, delta)
                        
                # Materials
                if hasattr(obj, 'material_slots'):
                    for slot in obj.material_slots:
                        mat = slot.material
                        if not mat or not mat.node_tree: continue
                        
                        if mat in shifted_materials:
                            continue
                        shifted_materials.add(mat)
                        
                        nt = mat.node_tree
                        if nt.animation_data and nt.animation_data.action:
                            act = nt.animation_data.action
                            if act not in shifted_actions:
                                shifted_actions.add(act)
                                shift_action(act, delta)
                        
                        for node in nt.nodes:
                            # Shift all texture nodes in case they were shifted by BulletHits
                            if getattr(node, 'type', '') == 'TEX_IMAGE' and hasattr(node, 'image_user'):
                                if getattr(node.image_user, 'frame_start', None) is not None:
                                    try:
                                        node.image_user.frame_start += delta_int
                                    except Exception:
                                        pass
                                        
            total_adjusted += 1
            
        if total_adjusted == 0:
            self.report({'WARNING'}, "No animatable time properties found in selection.")
            return {'CANCELLED'}
                                        
        self.report({'INFO'}, f"Adjusted hit time for {total_adjusted} object(s) to start at {target_frame}.")
        return {'FINISHED'}


def register():
    try:
        bpy.utils.register_class(DUMBTOOLS_OT_adjust_hit_time)
    except ValueError:
        bpy.utils.unregister_class(DUMBTOOLS_OT_adjust_hit_time)
        bpy.utils.register_class(DUMBTOOLS_OT_adjust_hit_time)

def unregister():
    try:
        bpy.utils.unregister_class(DUMBTOOLS_OT_adjust_hit_time)
    except RuntimeError:
        pass

register()
bpy.ops.dumbtools.adjust_hit_time('INVOKE_DEFAULT')
