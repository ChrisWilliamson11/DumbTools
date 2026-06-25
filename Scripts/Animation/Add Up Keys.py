import bpy

def iter_fcurves(action):
    """
    Yields fcurves from an Action, handling both Legacy Blender and Blender 5+ Layered Animation.
    """
    if not action:
        return
    # Legacy: Direct fcurves list
    if hasattr(action, "fcurves") and action.fcurves:
        for fc in action.fcurves:
            yield fc
    # Blender 5+: Layers and Strips
    if hasattr(action, "layers"):
        for layer in action.layers:
            if hasattr(layer, "strips"):
                for strip in layer.strips:
                    if hasattr(strip, "channelbags"):
                         for bag in strip.channelbags:
                             if hasattr(bag, "fcurves"):
                                 for fc in bag.fcurves:
                                     yield fc
                    # Fallback for other structures (legacy transition or direct strips)
                    if hasattr(strip, "fcurves"):
                        for fc in strip.fcurves:
                            yield fc
                    elif hasattr(strip, "channels"):
                         for fc in strip.channels:
                             yield fc

def get_selected_entities_fcurves(context):
    fcurves = []
    
    if context.mode == 'POSE' and context.selected_pose_bones:
        obj_to_bones = {}
        for bone in context.selected_pose_bones:
            obj = bone.id_data
            if obj not in obj_to_bones:
                obj_to_bones[obj] = set()
            obj_to_bones[obj].add(bone.name)
            
        for obj, bone_names in obj_to_bones.items():
            if obj.animation_data and obj.animation_data.action:
                act = obj.animation_data.action
                for fc in iter_fcurves(act):
                    dp = getattr(fc, "data_path", "")
                    for bone_name in bone_names:
                        prefix1 = f'pose.bones["{bone_name}"]'
                        prefix2 = f"pose.bones['{bone_name}']"
                        if dp.startswith(prefix1) or dp.startswith(prefix2):
                            fcurves.append(fc)
                            break
    else:
        for obj in context.selected_objects:
            if obj.animation_data and obj.animation_data.action:
                act = obj.animation_data.action
                for fc in iter_fcurves(act):
                    fcurves.append(fc)
                    
    return fcurves

class ANIM_OT_add_up_keys(bpy.types.Operator):
    bl_idname = "animation.add_up_keys"
    bl_label = "Add Up Keys"
    bl_description = "Add a halfway position key between selected keys, raising Z by 0.5"
    bl_options = {'REGISTER', 'UNDO'}

    z_offset: bpy.props.FloatProperty(
        name="Z Offset",
        description="Amount to add to the Z axis",
        default=0.5
    )

    def draw(self, context):
        layout = self.layout
        layout.prop(self, "z_offset")

    @classmethod
    def poll(cls, context):
        return (context.mode == 'POSE' and context.selected_pose_bones) or context.selected_objects

    def execute(self, context):
        fcurves = get_selected_entities_fcurves(context)
        
        if not fcurves:
            self.report({'WARNING'}, "No animation data found for selection.")
            return {'CANCELLED'}
            
        keys_added = 0
        
        # We only want location fcurves
        for fc in fcurves:
            dp = getattr(fc, "data_path", "")
            if not dp.endswith("location"):
                continue
                
            # Find selected keys
            selected_keys = []
            for k in fc.keyframe_points:
                if getattr(k, "select_control_point", getattr(k, "select", False)):
                    selected_keys.append(k)
                    
            if len(selected_keys) < 2:
                continue
                
            # Sort by frame just in case
            selected_keys.sort(key=lambda k: k.co[0])
            
            # Find midpoints to insert
            insertions = []
            for i in range(len(selected_keys) - 1):
                k1 = selected_keys[i]
                k2 = selected_keys[i + 1]
                mid_frame = (k1.co[0] + k2.co[0]) / 2.0
                mid_val = fc.evaluate(mid_frame)
                
                if fc.array_index == 2: # Z axis
                    mid_val += self.z_offset
                    
                insertions.append((mid_frame, mid_val))
                
            for frame, val in insertions:
                new_k = fc.keyframe_points.insert(frame, val, options={'FAST'})
                new_k.select_control_point = True
                keys_added += 1
                
        for fc in fcurves:
            fc.update()
            
        if keys_added == 0:
            self.report({'INFO'}, "No keys added. Make sure you have multiple selected location keys.")
        else:
            self.report({'INFO'}, f"Added {keys_added} halfway keys.")
            
        return {'FINISHED'}

    def invoke(self, context, event):
        return context.window_manager.invoke_props_dialog(self)

def register():
    if not hasattr(bpy.types, "ANIM_OT_add_up_keys"):
        try:
            bpy.utils.register_class(ANIM_OT_add_up_keys)
        except ValueError:
            bpy.utils.unregister_class(ANIM_OT_add_up_keys)
            bpy.utils.register_class(ANIM_OT_add_up_keys)

def unregister():
    try:
        bpy.utils.unregister_class(ANIM_OT_add_up_keys)
    except ValueError:
        pass

register()
bpy.ops.animation.add_up_keys('INVOKE_DEFAULT')
