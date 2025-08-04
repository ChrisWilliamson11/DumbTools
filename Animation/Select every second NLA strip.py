# Tooltip: Deselect every second NLA strip from the currently selected strips in the active object
import bpy

def deselect_every_second_strip():
    # Get the active object
    obj = bpy.context.object
    if not obj:
        print("No active object found.")
        return
    
    # Get the NLA tracks of the object
    tracks = obj.animation_data.nla_tracks
    selected_strips = []

    # Collect selected NLA strips
    for track in tracks:
        for strip in track.strips:
            if strip.select:
                selected_strips.append(strip)

    # Sort strips by their starting frame (frame_start)
    selected_strips.sort(key=lambda s: s.frame_start)

    # Deselect every second strip
    for i, strip in enumerate(selected_strips):
        if i % 2 == 1:  # Every second strip
            strip.select = False

# Run the function
deselect_every_second_strip()
