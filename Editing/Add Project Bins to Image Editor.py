# Tooltip: An attempt at creating 'Project Bins' like Premiere etc in blenders UI
import bpy
from bpy.props import BoolProperty, CollectionProperty, StringProperty, EnumProperty
from bpy.types import PropertyGroup, Panel, Operator
import os


# Define a property group for media items
class MediaItem(PropertyGroup):
    name: StringProperty(name="Name")
    expanded: BoolProperty(name="Expanded", default=False)
    type: StringProperty(name="Type")  # "Image" or "Video"
    bin_name: StringProperty(name="Bin Name")
    selected: BoolProperty(name="Selected", default=False)
    media_type: EnumProperty(
        name="Media Type",
        items=[
            ('IMAGE', "Image", ""),
            ('IMAGE_SEQUENCE', "Image Sequence", ""),
            ('MOVIE', "Movie", ""),
        ]
    )


# Define an operator to initialize bins and categorize media
class MEDIA_OT_initialize(Operator):
    bl_idname = "media.initialize"
    bl_label = "Initialize Media Bins"

    def execute(self, context):
        # Clear existing items
        context.scene.media_items.clear()

        # Create initial bins
        image_bin = context.scene.media_items.add()
        image_bin.name = "Images"
        image_bin.type = "Bin"

        video_bin = context.scene.media_items.add()
        video_bin.name = "Video"
        video_bin.type = "Bin"

        # Add images to the Images bin, distinguish between single images and image sequences
        for image in bpy.data.images:
            filepath = bpy.path.abspath(image.filepath)
            print(f"Checking image: {image.name} with filepath: {filepath}")
            if image.source == 'MOVIE' and filepath:
                print(f"Adding {image.name} to Video bin")
                item = context.scene.media_items.add()
                item.name = image.name
                item.type = "Video"
                item.bin_name = "Video"
                item.media_type = 'MOVIE'

            elif image.source == 'FILE' and filepath:
                print(f"Adding {image.name} to Images bin")
                item = context.scene.media_items.add()
                item.name = image.name
                item.type = "Image"
                item.bin_name = "Images"
                item.media_type = 'IMAGE'

            elif image.source == 'SEQUENCE':
                print(f"Adding {image.name} to Video bin (sequence)")
                item = context.scene.media_items.add()
                item.name = image.name
                item.type = "Video"
                item.bin_name = "Video"
                item.media_type = 'IMAGE_SEQUENCE'
            else:
                print(f"Skipping {image.name}")

        # Add VSE strips
        for scene in bpy.data.scenes:
            if scene.sequence_editor:
                for strip in scene.sequence_editor.sequences_all:
                    if strip.type == 'MOVIE':
                        print(f"Adding VSE movie strip {strip.name} to Video bin")
                        item = context.scene.media_items.add()
                        item.name = strip.name
                        item.type = "Video"
                        item.bin_name = "Video"
                        item.media_type = 'MOVIE'
                    elif strip.type == 'IMAGE':
                        print(f"Adding VSE image strip {strip.name} to Images bin")
                        item = context.scene.media_items.add()
                        item.name = strip.name
                        item.type = "Image"
                        item.bin_name = "Images"
                        item.media_type = 'IMAGE'
                    elif strip.type == 'IMAGE_SEQUENCE':
                        print(f"Adding VSE image sequence strip {strip.name} to Video bin")
                        item = context.scene.media_items.add()
                        item.name = strip.name
                        item.type = "Video"
                        item.bin_name = "Video"
                        item.media_type = 'IMAGE_SEQUENCE'

        return {'FINISHED'}


# Define an operator to add selected media to VSE
class MEDIA_OT_add_to_sequence(Operator):
    bl_idname = "media.add_to_sequence"
    bl_label = "Add to Sequence"

    def execute(self, context):
        scene = context.scene
        current_frame = scene.frame_current

        # Find the first available empty track
        def find_first_empty_channel(start_frame, end_frame):
            channel = 1
            while True:
                overlaps = False
                for strip in scene.sequence_editor.sequences_all:
                    if strip.channel == channel and not (strip.frame_final_end <= start_frame or strip.frame_final_start >= end_frame):
                        overlaps = True
                        break
                if not overlaps:
                    return channel
                channel += 1

        for item in scene.media_items:
            if item.selected:
                print(f"Adding {item.name} to VSE at frame {current_frame}")
                if item.media_type == "IMAGE":
                    image = bpy.data.images.get(item.name)
                    if image:
                        channel = find_first_empty_channel(current_frame, current_frame + image.frame_duration)
                        strip = scene.sequence_editor.sequences.new_image(
                            name=item.name,
                            filepath=bpy.path.abspath(image.filepath),
                            channel=channel,
                            frame_start=current_frame
                        )
                elif item.media_type == "MOVIE":
                    image = bpy.data.images.get(item.name)
                    if image:
                        channel = find_first_empty_channel(current_frame, current_frame + image.frame_duration)
                        strip = scene.sequence_editor.sequences.new_movie(
                            name=item.name,
                            filepath=bpy.path.abspath(image.filepath),
                            channel=channel,
                            frame_start=current_frame
                        )
                elif item.media_type == "IMAGE_SEQUENCE":
                    image = bpy.data.images.get(item.name)
                    if image:
                        directory = os.path.dirname(bpy.path.abspath(image.filepath))
                        frames = [{"name": bpy.path.basename(image.filepath)}]
                        channel = find_first_empty_channel(current_frame, current_frame + len(frames))

                        # Ensure the context is set to the sequencer
                        bpy.context.area.type = 'SEQUENCE_EDITOR'
                        bpy.ops.sequencer.image_strip_add(
                            directory=directory,
                            files=frames,
                            show_multiview=False,
                            frame_start=current_frame,
                            frame_end=current_frame + len(frames),
                            channel=channel,
                            fit_method='FIT',
                            set_view_transform=False
                        )
                        bpy.context.area.type = 'IMAGE_EDITOR'

                item.selected = False

        return {'FINISHED'}


# Define the panel
class MEDIA_PT_panel(Panel):
    bl_space_type = 'IMAGE_EDITOR'
    bl_region_type = 'UI'
    bl_category = 'Media'
    bl_label = 'Media Panel'

    def draw(self, context):
        layout = self.layout

        for item in context.scene.media_items:
            if item.type == "Bin":
                box = layout.box()
                row = box.row()
                row.prop(item, "expanded", text="", icon="TRIA_DOWN" if item.expanded else "TRIA_RIGHT", emboss=False)
                row.label(text=item.name)

                if item.expanded:
                    for sub_item in context.scene.media_items:
                        if sub_item.bin_name == item.name:
                            sub_row = box.row()
                            sub_row.prop(sub_item, "selected", text="")
                            sub_row.label(text=sub_item.name)

        row = layout.row()
        row.operator("media.initialize", text="Initialize Media Bins", icon='FILE_REFRESH')

        row = layout.row()
        row.operator("media.add_to_sequence", text="Add to Sequence", icon='SEQUENCE')


def register():
    bpy.utils.register_class(MediaItem)
    bpy.utils.register_class(MEDIA_OT_initialize)
    bpy.utils.register_class(MEDIA_OT_add_to_sequence)
    bpy.utils.register_class(MEDIA_PT_panel)

    bpy.types.Scene.media_items = CollectionProperty(type=MediaItem)


def unregister():
    bpy.utils.unregister_class(MediaItem)
    bpy.utils.unregister_class(MEDIA_OT_initialize)
    bpy.utils.unregister_class(MEDIA_OT_add_to_sequence)
    bpy.utils.unregister_class(MEDIA_PT_panel)

    del bpy.types.Scene.media_items


register()
