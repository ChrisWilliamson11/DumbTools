# Tooltip: Align NLA strips to the bottom (base) layer by offsetting the selected bone and IK bones in world space X&Y
import bpy
from bpy.types import Operator
from mathutils import Vector


class OT_AlignNLAStripsToBase(Operator):
    """Align NLA strips to the base layer by offsetting bone positions in world space X&Y"""

    bl_idname = "nla.align_strips_to_base"
    bl_label = "Align NLA Strips to Base"
    bl_options = {"REGISTER", "UNDO"}

    def execute(self, context):
        obj = context.active_object

        # Validate selection
        if not obj or obj.type != "ARMATURE":
            self.report({"ERROR"}, "Please select an armature object")
            return {"CANCELLED"}

        if context.mode != "POSE":
            self.report({"ERROR"}, "Please switch to Pose Mode")
            return {"CANCELLED"}

        selected_bone = context.active_pose_bone
        if not selected_bone:
            self.report({"ERROR"}, "Please select a bone in Pose Mode")
            return {"CANCELLED"}

        if not obj.animation_data or not obj.animation_data.nla_tracks:
            self.report({"ERROR"}, "No NLA tracks found on this object")
            return {"CANCELLED"}

        # Get all tracks (bottom track is the alignment target)
        tracks = [track for track in obj.animation_data.nla_tracks]
        if len(tracks) < 2:
            self.report({"WARNING"}, "Need at least 2 NLA tracks to align")
            return {"CANCELLED"}

        # Bottom track is the alignment target
        base_track = tracks[0]
        tracks_to_align = tracks[1:]

        # IK bones to also offset
        ik_bone_names = ["foot_ik.L", "foot_ik.R", "hand_ik.L", "hand_ik.R"]

        # Get the selected bone name
        selected_bone_name = selected_bone.name

        print(f"\n=== Aligning NLA Strips to Base ===")
        print(f"Selected bone: {selected_bone_name}")
        print(f"Base track: {base_track.name}")
        print(f"Tracks to align: {[t.name for t in tracks_to_align]}")

        # Store original frame and track mute states
        original_frame = context.scene.frame_current
        original_mute_states = {
            track: track.mute for track in obj.animation_data.nla_tracks
        }

        try:
            # Get base position from the first strip in base track
            base_strips = [strip for strip in base_track.strips]
            if not base_strips:
                self.report({"ERROR"}, "Base track has no strips")
                return {"CANCELLED"}

            base_strip = base_strips[0]

            # Mute all tracks except base
            for track in obj.animation_data.nla_tracks:
                track.mute = True
            base_track.mute = False

            # Get base position at the start of the base strip
            context.scene.frame_set(int(base_strip.frame_start))
            context.view_layer.update()

            if selected_bone_name not in obj.pose.bones:
                self.report({"ERROR"}, f"Bone '{selected_bone_name}' not found")
                return {"CANCELLED"}

            base_bone = obj.pose.bones[selected_bone_name]
            base_position = obj.matrix_world @ base_bone.matrix @ Vector((0, 0, 0))
            base_xy = Vector((base_position.x, base_position.y))

            print(f"Base position XY: {base_xy}")

            # Process each track to align
            for track in tracks_to_align:
                # Get all strips in this track
                strips = [strip for strip in track.strips]
                if not strips:
                    print(f"Skipping track with no strips: {track.name}")
                    continue

                # Mute all tracks, unmute only current track
                for t in obj.animation_data.nla_tracks:
                    t.mute = True
                track.mute = False

                # For each strip in this track
                for strip in strips:
                    if not strip.action:
                        continue

                    # Get position at the start of this strip
                    context.scene.frame_set(int(strip.frame_start))
                    context.view_layer.update()

                    current_bone = obj.pose.bones[selected_bone_name]
                    current_position = (
                        obj.matrix_world @ current_bone.matrix @ Vector((0, 0, 0))
                    )
                    current_xy = Vector((current_position.x, current_position.y))

                    # Calculate offset needed
                    offset_xy = base_xy - current_xy

                    print(f"\nStrip: {strip.name} (Action: {strip.action.name})")
                    print(f"  Current XY: {current_xy}")
                    print(f"  Offset XY: {offset_xy}")

                    # Apply offset to the action's fcurves for selected bone and IK bones
                    bones_to_offset = [selected_bone_name] + [
                        name for name in ik_bone_names if name in obj.pose.bones
                    ]

                    for bone_name in bones_to_offset:
                        # Find location X and Y fcurves for this bone
                        for fcurve in strip.action.fcurves:
                            # Check if this fcurve is for the bone's location
                            if (
                                f'pose.bones["{bone_name}"]' in fcurve.data_path
                                and fcurve.data_path.endswith(".location")
                            ):
                                # array_index 0 = X, 1 = Y, 2 = Z
                                if fcurve.array_index == 0:  # X
                                    # Offset all keyframes
                                    for keyframe in fcurve.keyframe_points:
                                        keyframe.co.y += offset_xy.x
                                        keyframe.handle_left.y += offset_xy.x
                                        keyframe.handle_right.y += offset_xy.x
                                    fcurve.update()
                                    print(f"    Offset {bone_name} X by {offset_xy.x}")

                                elif fcurve.array_index == 1:  # Y
                                    # Offset all keyframes
                                    for keyframe in fcurve.keyframe_points:
                                        keyframe.co.y += offset_xy.y
                                        keyframe.handle_left.y += offset_xy.y
                                        keyframe.handle_right.y += offset_xy.y
                                    fcurve.update()
                                    print(f"    Offset {bone_name} Y by {offset_xy.y}")

            self.report({"INFO"}, f"Aligned {len(tracks_to_align)} track(s) to base")

        finally:
            # Restore original frame and mute states
            context.scene.frame_set(original_frame)
            for track, mute_state in original_mute_states.items():
                track.mute = mute_state
            context.view_layer.update()

        return {"FINISHED"}


def register():
    bpy.utils.register_class(OT_AlignNLAStripsToBase)


def unregister():
    bpy.utils.unregister_class(OT_AlignNLAStripsToBase)


register()
bpy.ops.nla.align_strips_to_base()
