# Tooltip: Copy background images (and all settings) from the active camera to all other selected cameras

import bpy

def copy_image_user(src_user, dst_user):
    """Copy writeable ImageUser properties."""
    dst_user.frame_current = src_user.frame_current
    dst_user.frame_duration = src_user.frame_duration
    dst_user.frame_offset = src_user.frame_offset
    dst_user.frame_start = src_user.frame_start
    dst_user.tile = src_user.tile
    dst_user.use_auto_refresh = src_user.use_auto_refresh
    dst_user.use_cyclic = src_user.use_cyclic

def copy_clip_user(src_user, dst_user):
    """Copy writeable MovieClipUser properties."""
    try:
        dst_user.proxy_render_size = src_user.proxy_render_size
        dst_user.use_render_undistorted = src_user.use_render_undistorted
    except AttributeError:
        pass  # Not all versions expose these

def copy_background_image(src_bg, dst_bg):
    """Copy all settings from one CameraBackgroundImage to another."""
    # Source type
    dst_bg.source = src_bg.source

    # Image or clip reference
    dst_bg.image = src_bg.image
    dst_bg.clip = src_bg.clip
    dst_bg.use_camera_clip = src_bg.use_camera_clip

    # Display settings
    dst_bg.alpha = src_bg.alpha
    dst_bg.display_depth = src_bg.display_depth
    dst_bg.frame_method = src_bg.frame_method
    dst_bg.show_background_image = src_bg.show_background_image
    dst_bg.show_expanded = src_bg.show_expanded
    dst_bg.show_on_foreground = src_bg.show_on_foreground

    # Transform
    dst_bg.offset = src_bg.offset.copy()
    dst_bg.rotation = src_bg.rotation
    dst_bg.scale = src_bg.scale
    dst_bg.use_flip_x = src_bg.use_flip_x
    dst_bg.use_flip_y = src_bg.use_flip_y

    # Image user settings (sequence playback etc.)
    copy_image_user(src_bg.image_user, dst_bg.image_user)

    # Clip user settings
    copy_clip_user(src_bg.clip_user, dst_bg.clip_user)

def main():
    active_obj = bpy.context.active_object

    if not active_obj or active_obj.type != 'CAMERA':
        print("✗ Active object is not a camera.")
        return

    src_cam = active_obj.data
    src_bgs = src_cam.background_images

    if len(src_bgs) == 0:
        print(f"✗ Active camera '{active_obj.name}' has no background images to copy.")
        return

    # Gather selected cameras (excluding the active one)
    targets = [
        obj for obj in bpy.context.selected_objects
        if obj.type == 'CAMERA' and obj is not active_obj
    ]

    if not targets:
        print("✗ No other cameras selected. Select target cameras and make the source camera active.")
        return

    copied = 0
    for obj in targets:
        dst_cam = obj.data

        # Clear existing background images on target
        dst_cam.background_images.clear()

        # Enable background images display
        dst_cam.show_background_images = src_cam.show_background_images

        # Copy each background image
        for src_bg in src_bgs:
            dst_bg = dst_cam.background_images.new()
            copy_background_image(src_bg, dst_bg)

        copied += 1
        print(f"  → Copied {len(src_bgs)} background image(s) to '{obj.name}'")

    print(f"✓ Copied background images from '{active_obj.name}' to {copied} camera(s).")

main()
