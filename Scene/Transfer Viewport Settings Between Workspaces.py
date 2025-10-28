import bpy

viewport_settings = {}
last_workspace_name = None
_msgbus_owner = None


def get_viewport_settings(area):
    # Capture settings from the specified 3D viewport area
    settings = None
    if area.type == "VIEW_3D":
        for space in area.spaces:
            if space.type == "VIEW_3D":
                settings = {
                    "shading_type": space.shading.type,
                    "overlay_show_overlays": space.overlay.show_overlays,
                    "view_perspective": space.region_3d.view_perspective,
                    "view_location": space.region_3d.view_location.copy(),
                    "view_rotation": space.region_3d.view_rotation.copy(),
                    "view_distance": space.region_3d.view_distance,
                    "local_view": space.local_view,
                    "local_view_objects": [
                        obj.name for obj in space.local_view.state.objects
                    ]
                    if space.local_view
                    else [],
                    "overlay_show_wireframes": space.overlay.show_wireframes,
                    "overlay_wireframe_threshold": space.overlay.wireframe_threshold,
                    "overlay_show_outline_selected": space.overlay.show_outline_selected,
                    "overlay_show_floor": space.overlay.show_floor,
                    "overlay_show_axis_x": space.overlay.show_axis_x,
                    "overlay_show_axis_y": space.overlay.show_axis_y,
                    "overlay_show_axis_z": space.overlay.show_axis_z,
                    "overlay_show_cursor": space.overlay.show_cursor,
                    "overlay_show_text": space.overlay.show_text,
                    "overlay_show_extras": space.overlay.show_extras,
                    "overlay_show_relationship_lines": space.overlay.show_relationship_lines,
                    "overlay_show_bones": space.overlay.show_bones,
                    "overlay_show_face_orientation": space.overlay.show_face_orientation,
                    "shading_show_xray": space.shading.show_xray,
                    "shading_show_xray_wireframe": space.shading.show_xray_wireframe,
                    "shading_xray_alpha": space.shading.xray_alpha,
                    "shading_xray_alpha_wireframe": space.shading.xray_alpha_wireframe,
                    "show_gizmo": space.show_gizmo,
                    "show_gizmo_navigate": space.show_gizmo_navigate,
                    "show_gizmo_tool": space.show_gizmo_tool,
                    "show_gizmo_context": space.show_gizmo_context,
                    "show_gizmo_object_translate": space.show_gizmo_object_translate,
                    "show_gizmo_object_rotate": space.show_gizmo_object_rotate,
                    "show_gizmo_object_scale": space.show_gizmo_object_scale,
                    "show_gizmo_empty_image": space.show_gizmo_empty_image,
                    "show_gizmo_empty_force_field": space.show_gizmo_empty_force_field,
                    "show_gizmo_light_size": space.show_gizmo_light_size,
                    "show_gizmo_light_look_at": space.show_gizmo_light_look_at,
                    "show_gizmo_camera_lens": space.show_gizmo_camera_lens,
                    "show_gizmo_camera_dof_distance": space.show_gizmo_camera_dof_distance,
                    "shading_light": space.shading.light,
                    "shading_wireframe_color_type": space.shading.wireframe_color_type,
                    "shading_color_type": space.shading.color_type,
                    "shading_background_type": space.shading.background_type,
                    "shading_show_backface_culling": space.shading.show_backface_culling,
                    "shading_show_xray": space.shading.show_xray,
                    "shading_show_shadows": space.shading.show_shadows,
                    "shading_show_cavity": space.shading.show_cavity,
                    "shading_use_dof": space.shading.use_dof,
                }
                if space.region_3d.view_perspective == "CAMERA":
                    settings["camera"] = space.camera.name if space.camera else None
                break

    # print("Captured viewport settings:", settings)
    return settings


def apply_viewport_settings(area, settings):
    """Apply captured settings to the given viewport area."""
    if area.type == "VIEW_3D":
        for space in area.spaces:
            if space.type == "VIEW_3D":
                # Apply the settings
                space.shading.type = settings.get("shading_type", "SOLID")
                space.overlay.show_overlays = settings.get(
                    "overlay_show_overlays", True
                )
                space.overlay.show_wireframes = settings.get(
                    "overlay_show_wireframes", True
                )
                space.overlay.wireframe_threshold = settings.get(
                    "overlay_wireframe_threshold", 1.0
                )
                space.overlay.show_outline_selected = settings.get(
                    "overlay_show_outline_selected", True
                )
                space.overlay.show_floor = settings.get("overlay_show_floor", True)
                space.overlay.show_axis_x = settings.get("overlay_show_axis_x", True)
                space.overlay.show_axis_y = settings.get("overlay_show_axis_y", True)
                space.overlay.show_axis_z = settings.get("overlay_show_axis_z", True)
                space.overlay.show_cursor = settings.get("overlay_show_cursor", True)
                space.overlay.show_text = settings.get("overlay_show_text", True)
                space.overlay.show_extras = settings.get("overlay_show_extras", True)
                space.overlay.show_relationship_lines = settings.get(
                    "overlay_show_relationship_lines", True
                )
                space.overlay.show_bones = settings.get("overlay_show_bones", True)
                space.overlay.show_face_orientation = settings.get(
                    "overlay_show_face_orientation", False
                )
                space.shading.show_xray = settings.get("shading_show_xray", False)
                space.shading.show_xray_wireframe = settings.get(
                    "shading_show_xray_wireframe", False
                )
                space.shading.xray_alpha = settings.get("shading_xray_alpha", 0.5)
                space.shading.xray_alpha_wireframe = settings.get(
                    "shading_xray_alpha_wireframe", 0.5
                )
                space.show_gizmo = settings.get("show_gizmo", True)
                space.show_gizmo_navigate = settings.get("show_gizmo_navigate", True)
                space.show_gizmo_tool = settings.get("show_gizmo_tool", True)
                space.show_gizmo_context = settings.get("show_gizmo_context", True)
                space.show_gizmo_object_translate = settings.get(
                    "show_gizmo_object_translate", True
                )
                space.show_gizmo_object_rotate = settings.get(
                    "show_gizmo_object_rotate", True
                )
                space.show_gizmo_object_scale = settings.get(
                    "show_gizmo_object_scale", True
                )
                space.show_gizmo_empty_image = settings.get(
                    "show_gizmo_empty_image", True
                )
                space.show_gizmo_empty_force_field = settings.get(
                    "show_gizmo_empty_force_field", True
                )
                space.show_gizmo_light_size = settings.get(
                    "show_gizmo_light_size", True
                )
                space.show_gizmo_light_look_at = settings.get(
                    "show_gizmo_light_look_at", True
                )
                space.show_gizmo_camera_lens = settings.get(
                    "show_gizmo_camera_lens", True
                )
                space.show_gizmo_camera_dof_distance = settings.get(
                    "show_gizmo_camera_dof_distance", True
                )
                space.shading.light = settings.get("shading_light", "FLAT")
                space.shading.wireframe_color_type = settings.get(
                    "shading_wireframe_color_type", "SINGLE"
                )
                space.shading.color_type = settings.get(
                    "shading_color_type", "MATERIAL"
                )
                space.shading.background_type = settings.get(
                    "shading_background_type", "THEME"
                )
                space.shading.show_backface_culling = settings.get(
                    "shading_show_backface_culling", False
                )
                space.shading.show_xray = settings.get("shading_show_xray", False)
                space.shading.show_shadows = settings.get("shading_show_shadows", True)
                space.shading.show_cavity = settings.get("shading_show_cavity", True)
                space.shading.use_dof = settings.get("shading_use_dof", True)

                # Local view settings
                if settings.get("local_view"):
                    # Restore local view with the objects specified
                    local_objects = [
                        bpy.data.objects[obj_name]
                        for obj_name in settings.get("local_view_objects", [])
                    ]
                    bpy.ops.view3d.localview(frame_selected=False)
                    for obj in local_objects:
                        obj.select_set(True)
                elif space.local_view:
                    # Exit local view if it's currently active but not in the settings
                    bpy.ops.view3d.localview(frame_selected=False)

                # Camera/Viewpoint settings
                space.region_3d.view_perspective = settings.get(
                    "view_perspective", "PERSP"
                )
                if settings.get("view_perspective") == "CAMERA":
                    space.camera = bpy.data.objects.get(settings.get("camera"))
                else:
                    space.region_3d.view_location = settings.get(
                        "view_location", space.region_3d.view_location
                    )
                    space.region_3d.view_rotation = settings.get(
                        "view_rotation", space.region_3d.view_rotation
                    )
                    space.region_3d.view_distance = settings.get(
                        "view_distance", space.region_3d.view_distance
                    )


def workspace_changed(*args):
    global last_workspace_name

    global viewport_settings
    print("Workspace changed:", bpy.context.workspace.name)

    current_workspace_name = bpy.context.workspace.name
    if last_workspace_name and last_workspace_name != current_workspace_name:
        # Retrieve the old workspace
        old_workspace = bpy.data.workspaces.get(last_workspace_name)
        if old_workspace:
            # Capture settings from all 3D viewports in the old workspace
            settings_list = [
                get_viewport_settings(area)
                for area in old_workspace.screens[0].areas
                if area.type == "VIEW_3D"
            ]
            viewport_settings[last_workspace_name] = settings_list

        # Apply settings to all 3D viewports in the new workspace
        new_workspace = bpy.data.workspaces[current_workspace_name]
        old_settings_list = viewport_settings.get(last_workspace_name, [])
        if old_settings_list:
            old_settings = old_settings_list[
                0
            ]  # Use the first set of settings as an example
            for area in new_workspace.screens[0].areas:
                if area.type == "VIEW_3D":
                    apply_viewport_settings(area, old_settings)

    # Update the last workspace name
    last_workspace_name = current_workspace_name


def register():
    global _msgbus_owner, last_workspace_name

    # Subscribe to the workspace property of the window
    subscribe_to = bpy.types.Window, "workspace"

    # Create a unique owner for this subscription
    _msgbus_owner = object()

    # Add the subscription
    bpy.msgbus.subscribe_rna(
        key=subscribe_to,
        owner=_msgbus_owner,
        args=(_msgbus_owner,),
        notify=workspace_changed,
    )

    # Initialize the last workspace name
    last_workspace_name = bpy.context.workspace.name


def unregister():
    global _msgbus_owner

    # Clean up the msgbus subscription
    if _msgbus_owner is not None:
        bpy.msgbus.clear_by_owner(_msgbus_owner)
        _msgbus_owner = None
