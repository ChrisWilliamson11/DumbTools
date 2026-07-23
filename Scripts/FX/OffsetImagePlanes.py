# Tooltip: Offset the start frame of animated textures on selected image planes
import bpy
import re

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

class DUMBTOOLS_OT_offset_image_plane_texture(bpy.types.Operator):
    """Offset the start frame of animated textures on selected objects"""
    bl_idname = "dumbtools.offset_image_plane_texture"
    bl_label = "Offset Image Plane Texture"
    bl_options = {'REGISTER', 'UNDO'}

    offset_amount: bpy.props.IntProperty(
        name="Offset Amount",
        description="Offset in frames to add to the texture animation start frame",
        default=0,
    )

    @classmethod
    def poll(cls, context):
        return context.active_object is not None and len(context.selected_objects) > 0

    def invoke(self, context, event):
        scene = context.scene
        # Restore persisted setting
        self.offset_amount = getattr(scene, 'oipt_offset_amount', 0)
        return context.window_manager.invoke_props_dialog(self, width=350)

    def draw(self, context):
        layout = self.layout
        layout.prop(self, "offset_amount")

    def execute(self, context):
        selected_objects = context.selected_objects
        
        if not selected_objects:
            self.report({'WARNING'}, "No objects selected.")
            return {'CANCELLED'}
            
        delta = self.offset_amount
        if delta == 0:
            self.report({'INFO'}, "Offset is 0. No changes made.")
            return {'CANCELLED'}
            
        shifted_actions = set()
        shifted_materials = set()
        
        total_adjusted = 0
        
        for obj in selected_objects:
            if not hasattr(obj, 'material_slots'):
                continue
                
            adjusted = False
            for slot in obj.material_slots:
                mat = slot.material
                if not mat or not mat.node_tree: continue
                
                if mat in shifted_materials:
                    continue
                shifted_materials.add(mat)
                
                nt = mat.node_tree
                shifted_nodes = set()
                
                # Check for action on the material node tree
                if nt.animation_data and nt.animation_data.action:
                    act = nt.animation_data.action
                    if act not in shifted_actions:
                        shifted_actions.add(act)
                        # We shift the 'image_user.frame_offset' fcurves
                        for fc in iter_fcurves(act):
                            if 'image_user.frame_offset' in fc.data_path:
                                for kp in fc.keyframe_points:
                                    kp.co[0] += delta
                                fc.update()
                                adjusted = True
                                
                                match = re.search(r'nodes\["([^"]+)"\]', fc.data_path)
                                if match:
                                    shifted_nodes.add(match.group(1))
                
                # Update image nodes that do not have their frame_offset animated
                for node in nt.nodes:
                    if getattr(node, 'type', '') == 'TEX_IMAGE' and hasattr(node, 'image_user'):
                        if node.name not in shifted_nodes:
                            try:
                                node.image_user.frame_start += delta
                                adjusted = True
                            except Exception as e:
                                pass
                            
            if adjusted:
                total_adjusted += 1
                
        # Persist setting
        context.scene.oipt_offset_amount = self.offset_amount
        
        if total_adjusted == 0:
            self.report({'WARNING'}, "No animatable texture properties found in selection.")
            return {'CANCELLED'}
            
        self.report({'INFO'}, f"Offset image plane texture by {delta} for {total_adjusted} object(s).")
        return {'FINISHED'}

# Scene-level storage
_SCENE_PROPS = [
    ('oipt_offset_amount', bpy.props.IntProperty(name="OIPT Offset Amount", default=0)),
]

def register():
    try:
        bpy.utils.register_class(DUMBTOOLS_OT_offset_image_plane_texture)
    except ValueError:
        bpy.utils.unregister_class(DUMBTOOLS_OT_offset_image_plane_texture)
        bpy.utils.register_class(DUMBTOOLS_OT_offset_image_plane_texture)
    for prop_name, prop_value in _SCENE_PROPS:
        setattr(bpy.types.Scene, prop_name, prop_value)

def unregister():
    try:
        bpy.utils.unregister_class(DUMBTOOLS_OT_offset_image_plane_texture)
    except RuntimeError:
        pass
    for prop_name, _ in _SCENE_PROPS:
        if hasattr(bpy.types.Scene, prop_name):
            delattr(bpy.types.Scene, prop_name)

register()
bpy.ops.dumbtools.offset_image_plane_texture('INVOKE_DEFAULT')
