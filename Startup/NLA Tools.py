import bpy

class SelectStripsOperator(bpy.types.Operator):
    """Select All NLA Strips That Start After Current Frame"""
    bl_idname = "nla.select_later_strips"
    bl_label = "Select NLA Strips After Current Frame"
    bl_options = {'REGISTER', 'UNDO'}

    def execute(self, context):
        scene = context.scene
        current_frame = scene.frame_current

        # Access all objects in the scene with NLA tracks
        for obj in scene.objects:
            if obj.animation_data and obj.animation_data.nla_tracks:
                for track in obj.animation_data.nla_tracks:
                    for strip in track.strips:
                        if strip.frame_start > current_frame:
                            strip.select = True
                        else:
                            strip.select = False

        self.report({'INFO'}, "NLA Strips selection updated.")
        return {'FINISHED'}

class NLAGoToNextStrip(bpy.types.Operator):
    """Go to the next NLA strip"""
    bl_idname = "nla.go_to_next_strip"
    bl_label = "Go to Next NLA Strip"

    @classmethod
    def poll(cls, context):
        return context.active_object is not None and context.active_object.animation_data is not None

    def execute(self, context):
        current_frame = context.scene.frame_current
        strips = [strip for track in context.active_object.animation_data.nla_tracks for strip in track.strips]
        strips.sort(key=lambda strip: int(round(strip.frame_start)))

        for strip in strips:
            rounded_strip_start = int(round(strip.frame_start))
            if current_frame < rounded_strip_start:
                context.scene.frame_set(rounded_strip_start)
                break

        return {'FINISHED'}

class NLAGoToPreviousStrip(bpy.types.Operator):
    """Go to the previous NLA strip"""
    bl_idname = "nla.go_to_previous_strip"
    bl_label = "Go to Previous NLA Strip"

    @classmethod
    def poll(cls, context):
        return context.active_object is not None and context.active_object.animation_data is not None

    def execute(self, context):
        current_frame = context.scene.frame_current
        strips = [strip for track in context.active_object.animation_data.nla_tracks for strip in track.strips]
        strips.sort(key=lambda strip: strip.frame_start, reverse=True)

        for strip in strips:
            if strip.frame_start < current_frame:
                context.scene.frame_set(int(strip.frame_start))
                break
        return {'FINISHED'}

class SetStripToCurrentFrame(bpy.types.Operator):
    """Set selected NLA strips to start at the current frame"""
    bl_idname = "nla.set_strip_to_current_frame"
    bl_label = "Set Strip to Current Frame"
    bl_options = {'REGISTER', 'UNDO'}

    def execute(self, context):
        current_frame = context.scene.frame_current
        strips = [strip for track in context.object.animation_data.nla_tracks for strip in track.strips if strip.select]
        
        if not strips:
            self.report({'WARNING'}, "No strips selected")
            return {'CANCELLED'}
        
        # Find the earliest strip among the selected
        first_strip = min(strips, key=lambda s: s.frame_start)
        offset = current_frame - first_strip.frame_start

        # Move all selected strips by the calculated offset
        for strip in strips:
            strip.frame_start += offset
            strip.frame_end += offset

        return {'FINISHED'}

class NLADumbToolsMenu(bpy.types.Menu):
    bl_label = "Dumbtools"
    bl_idname = "NLA_MT_NLAdumbtools"

    def draw(self, context):
        layout = self.layout
        layout.operator("nla.select_later_strips", text="Select NLA Strips After Current Frame")
        layout.operator("nla.go_to_next_strip", text="Go to Next Strip")
        layout.operator("nla.go_to_previous_strip", text="Go to Previous Strip")
        layout.operator("nla.set_strip_to_current_frame", text="Set Strip to Current Frame")

def nla_menu_func(self, context):
    self.layout.menu("NLA_MT_NLAdumbtools")

def register():
    bpy.utils.register_class(SelectStripsOperator)
    bpy.utils.register_class(NLAGoToNextStrip)
    bpy.utils.register_class(NLAGoToPreviousStrip)
    bpy.utils.register_class(SetStripToCurrentFrame)
    bpy.utils.register_class(NLADumbToolsMenu)
    bpy.types.NLA_MT_editor_menus.append(nla_menu_func)

def unregister():
    bpy.utils.unregister_class(SelectStripsOperator)
    bpy.utils.unregister_class(NLAGoToNextStrip)
    bpy.utils.unregister_class(NLAGoToPreviousStrip)
    bpy.utils.unregister_class(SetStripToCurrentFrame)
    bpy.utils.unregister_class(NLADumbToolsMenu)
    bpy.types.NLA_MT_editor_menus.remove(nla_menu_func)



register()
