# Tooltip: Offset bitmaps in materials using a mapping node with a UI to control location, rotation, and scale
import bpy
import os
from bpy.props import FloatVectorProperty, EnumProperty, BoolProperty, CollectionProperty, StringProperty, PointerProperty

# Path to material mod nodegroups
MATERIAL_MODS_PATH = r"H:\000_Projects\Goliath\01-3_Marketing\03_Animation\Runner_Vignettes\01_Assets\2D\Shader Nodegroups"

# Channel mapping - maps nodegroup prefix to shader input name
CHANNEL_MAPPING = {
    'BaseColor': 'Base Color',
    'Roughness': 'Roughness',
    'Metallic': 'Metallic',
    'Normal': 'Normal',
    'Emission': 'Emission',
    'Alpha': 'Alpha',
    'Specular': 'Specular',
}


class MaterialModItem(bpy.types.PropertyGroup):
    """Property group for material mod nodegroups"""
    name: StringProperty(name="Name")
    blend_file: StringProperty(name="Blend File")
    enabled: BoolProperty(name="Enabled", default=False)



class OffsetBitmapSettings(bpy.types.PropertyGroup):
    def update_preset(self, context):
        if self.preset_toggle:
            self.location = (0.5, 0.5, 0.0)
            self.rotation = (0.0, 0.0, 0.0)
            self.scale = (0.5, 0.5, 1.0)
        else:
            self.location = (0.0, 0.0, 0.0)
            self.rotation = (0.0, 0.0, 0.0)
            self.scale = (1.0, 1.0, 1.0)

    material_include_filter: StringProperty(
        name="Include Filter",
        description="Material names must contain one of these (semicolon-delimited). Leave empty to include all",
        default="MaterialSG"
    )

    material_exclude_filter: StringProperty(
        name="Exclude Filter",
        description="Material names containing any of these will be excluded (semicolon-delimited)",
        default="graphics;atlas"
    )

    mapping_type: EnumProperty(
        name="Type",
        description="Mapping type",
        items=[('POINT',"Point",""),('TEXTURE',"Texture",""),('VECTOR',"Vector",""),('NORMAL',"Normal","")],
        default='POINT'
    )

    location: FloatVectorProperty(
        name="Location",
        description="Location offset",
        default=(0.0, 0.0, 0.0),
        subtype='TRANSLATION'
    )

    rotation: FloatVectorProperty(
        name="Rotation",
        description="Rotation",
        default=(0.0, 0.0, 0.0),
        subtype='EULER'
    )

    scale: FloatVectorProperty(
        name="Scale",
        description="Scale",
        default=(1.0, 1.0, 1.0),
        subtype='XYZ'
    )

    preset_toggle: BoolProperty(
        name="Use Preset",
        description="Toggle between default (0,0,0 / 1,1,1) and preset (.5,.5,0 / .5,.5,1)",
        default=False,
        update=update_preset
    )


# --- Helpers (dialog-independent) ---

def _matches_filter(material_name: str, include_filter: str, exclude_filter: str) -> bool:
    mat_name_lower = material_name.lower()
    if exclude_filter:
        exclude_terms = [t.strip().lower() for t in exclude_filter.split(';') if t.strip()]
        for term in exclude_terms:
            if term in mat_name_lower:
                return False
    if include_filter:
        include_terms = [t.strip() for t in include_filter.split(';') if t.strip()]
        for term in include_terms:
            if term in material_name:
                return True
        return False
    return True



def _get_current_ui_settings(context):
    """Return current UI settings from Scene settings PropertyGroup."""
    settings = getattr(context.scene, 'offset_bitmap_settings', None)
    if settings:
        return (
            settings.material_include_filter,
            settings.material_exclude_filter,
            settings.mapping_type,
            tuple(settings.location),
            tuple(settings.rotation),
            tuple(settings.scale),
        )
    # Fallback defaults if settings not present
    return '', '', 'POINT', (0.0, 0.0, 0.0), (0.0, 0.0, 0.0), (1.0, 1.0, 1.0)


def _apply_offset_to_material(material, mapping_type: str, location, rotation, scale) -> int:
    nodes = material.node_tree.nodes
    links = material.node_tree.links

    image_nodes = [node for node in nodes if node.type == 'TEX_IMAGE']
    if not image_nodes:
        return 0

    # Create or find texture coordinate node
    tex_coord = None
    for node in nodes:
        if node.type == 'TEX_COORD':
            tex_coord = node
            break
    if not tex_coord:
        tex_coord = nodes.new('ShaderNodeTexCoord')
        tex_coord.location = (-800, 0)

    updated = 0

    for img_node in image_nodes:
        # If there's an existing Mapping feeding this image, update it in place
        existing_mapping = None
        if img_node.inputs['Vector'].is_linked:
            for link in list(img_node.inputs['Vector'].links):
                src = link.from_node
                if src and src.type == 'MAPPING':
                    existing_mapping = src
                    break

        if existing_mapping:
            existing_mapping.vector_type = mapping_type
            existing_mapping.inputs['Location'].default_value = location
            existing_mapping.inputs['Rotation'].default_value = rotation
            existing_mapping.inputs['Scale'].default_value = scale
            updated += 1
            continue

        # Otherwise, create a new Mapping and insert it
        mapping = nodes.new('ShaderNodeMapping')
        mapping.location = (-600, 0)
        mapping.vector_type = mapping_type
        mapping.inputs['Location'].default_value = location
        mapping.inputs['Rotation'].default_value = rotation
        mapping.inputs['Scale'].default_value = scale

        # Connect texture coordinate to mapping
        links.new(tex_coord.outputs['UV'], mapping.inputs['Vector'])

        # Rewire the image node input to our new mapping
        if img_node.inputs['Vector'].is_linked:
            for link in list(img_node.inputs['Vector'].links):
                links.remove(link)
        links.new(mapping.outputs['Vector'], img_node.inputs['Vector'])
        updated += 1

    return updated


def apply_offset_to_all_materials(include_filter: str, exclude_filter: str, mapping_type: str, location, rotation, scale) -> int:
    updated_total = 0
    for mat in bpy.data.materials:
        if not mat.use_nodes:
            continue
        if not _matches_filter(mat.name, include_filter, exclude_filter):
            continue
        updated_total += _apply_offset_to_material(mat, mapping_type, location, rotation, scale)
    return updated_total


def process_decal_materials_core(add_fix: bool = True, include_filter: str = '', exclude_filter: str = '') -> int:
    """Add or remove CameraOnly node group on all materials."""
    nodegroup_path = r"H:\000_Projects\Goliath\01-3_Marketing\03_Animation\Runner_Vignettes\01_Assets\3D\Nodegroups\CameraOnly.blend"
    nodegroup_name = "CameraOnly"

    # Append the node group if needed
    if add_fix and nodegroup_name not in bpy.data.node_groups:
        with bpy.data.libraries.load(nodegroup_path, link=False) as (data_from, data_to):
            if nodegroup_name in data_from.node_groups:
                data_to.node_groups = [nodegroup_name]

    count = 0
    for mat in bpy.data.materials:
        if not mat.use_nodes:
            continue
        if not _matches_filter(mat.name, include_filter, exclude_filter):
            continue

        nodes = mat.node_tree.nodes
        links = mat.node_tree.links

        # Find the material output node
        output_node = None
        for node in nodes:
            if node.type == 'OUTPUT_MATERIAL':
                output_node = node
                break
        if not output_node:
            continue

        if add_fix:
            if nodegroup_name not in bpy.data.node_groups:
                continue

            # Skip if already present
            camera_only_node = None
            for node in nodes:
                if node.type == 'GROUP' and node.node_tree and node.node_tree.name == nodegroup_name:
                    camera_only_node = node
                    break
            if camera_only_node:
                continue

            shader_input = output_node.inputs.get('Surface')
            if not shader_input or not shader_input.is_linked:
                continue

            shader_link = shader_input.links[0]
            shader_socket = shader_link.from_socket

            camera_only_node = nodes.new('ShaderNodeGroup')
            camera_only_node.node_tree = bpy.data.node_groups[nodegroup_name]
            camera_only_node.location = (output_node.location.x - 300, output_node.location.y)

            links.remove(shader_link)
            links.new(shader_socket, camera_only_node.inputs[0])
            links.new(camera_only_node.outputs[0], shader_input)

            count += 1
        else:
            camera_only_node = None
            for node in nodes:
                if node.type == 'GROUP' and node.node_tree and node.node_tree.name == nodegroup_name:
                    camera_only_node = node
                    break
            if not camera_only_node:
                continue

            if not camera_only_node.inputs[0].is_linked:
                nodes.remove(camera_only_node)
                continue

            shader_link = camera_only_node.inputs[0].links[0]
            shader_socket = shader_link.from_socket

            nodes.remove(camera_only_node)
            links.new(shader_socket, output_node.inputs['Surface'])

            count += 1

    return count


class OffsetBitmapsOperator(bpy.types.Operator):
    """Offset Bitmaps in Materials"""
    bl_idname = "material.offset_bitmaps"
    bl_label = "Offset Bitmaps in Materials"
    bl_options = {'REGISTER', 'UNDO'}

    # Material mods collection
    material_mods: CollectionProperty(type=MaterialModItem)

    # Mapping node properties
    mapping_type: EnumProperty(
        name="Type",
        description="Mapping type",
        items=[
            ('POINT', "Point", ""),
            ('TEXTURE', "Texture", ""),
            ('VECTOR', "Vector", ""),
            ('NORMAL', "Normal", ""),
        ],
        default='POINT'
    )

    location: FloatVectorProperty(
        name="Location",
        description="Location offset",
        default=(0.0, 0.0, 0.0),
        subtype='TRANSLATION'
    )

    rotation: FloatVectorProperty(
        name="Rotation",
        description="Rotation",
        default=(0.0, 0.0, 0.0),
        subtype='EULER'
    )

    scale: FloatVectorProperty(
        name="Scale",
        description="Scale",
        default=(1.0, 1.0, 1.0),
        subtype='XYZ'
    )

    def update_preset_toggle(self, context):
        """Callback when preset toggle is changed"""
        if self.preset_toggle:
            # Apply preset values
            self.location = (0.5, 0.5, 0.0)
            self.rotation = (0.0, 0.0, 0.0)
            self.scale = (0.5, 0.5, 1.0)
        else:
            # Apply default values
            self.location = (0.0, 0.0, 0.0)
            self.rotation = (0.0, 0.0, 0.0)
            self.scale = (1.0, 1.0, 1.0)

    preset_toggle: BoolProperty(
        name="Use Preset",
        description="Toggle between default (0,0,0 / 1,1,1) and preset (.5,.5,0 / .5,.5,1)",
        default=False,
        update=update_preset_toggle
    )



    material_include_filter: StringProperty(
        name="Include Filter",
        description="Material names must contain one of these (semicolon-delimited). Leave empty to include all",
        default="MaterialSG"
    )

    material_exclude_filter: StringProperty(
        name="Exclude Filter",
        description="Material names containing any of these will be excluded (semicolon-delimited)",
        default="graphics;atlas"
    )

    def update_fix_decal(self, context):
        """Ensure only one decal option is active"""
        if self.fix_decal_materials:
            self.remove_decal_fix = False

    def update_remove_decal(self, context):
        """Ensure only one decal option is active"""
        if self.remove_decal_fix:
            self.fix_decal_materials = False

    fix_decal_materials: BoolProperty(
        name="Fix Decal Materials",
        description="Add CameraOnly node group to materials with 'graphics' in the name",
        default=False,
        update=update_fix_decal
    )

    remove_decal_fix: BoolProperty(
        name="Remove Decal Fix",
        description="Remove CameraOnly node group from graphics materials",
        default=False,
        update=update_remove_decal
    )

    def draw(self, context):
        layout = self.layout

        # Material filtering section at top
        settings = context.scene.offset_bitmap_settings
        layout.label(text="Material Filtering:")
        layout.prop(settings, "material_include_filter")
        layout.prop(settings, "material_exclude_filter")
        row = layout.row(align=True)
        row.operator("material.swap_filters", text="Swap Include/Exclude", icon='ARROW_LEFTRIGHT')

        layout.separator()

        # Offset Bitmaps section
        layout.label(text="Offset Bitmaps:")
        layout.prop(settings, "mapping_type")

        layout.label(text="Location:")
        layout.prop(settings, "location", text="")

        layout.label(text="Rotation:")
        layout.prop(settings, "rotation", text="")

        layout.label(text="Scale:")
        layout.prop(settings, "scale", text="")

        # Toggle button for preset
        row = layout.row()
        row.prop(settings, "preset_toggle", text="Toggle Preset (.5,.5,0 / .5,.5,1)", toggle=True)

        # Apply offset button
        layout.operator("material.apply_offset_bitmaps", text="Apply Offset")

        layout.separator()

        # Decal fix section
        layout.label(text="Decal Materials:")
        row = layout.row(align=True)
        row.operator("material.add_decal_fix", text="Add Decal Fix")
        row.operator("material.remove_decal_fix", text="Remove Decal Fix")

        layout.separator()

        # Material mods section
        layout.label(text="Add Material Mods:")
        scene_mods = context.scene.offset_bitmaps_mods
        if len(scene_mods) == 0:
            layout.label(text="No material mods found", icon='INFO')
        else:
            for mod in scene_mods:
                layout.prop(mod, "enabled", text=mod.name)

        if len(scene_mods) > 0:
            row = layout.row(align=True)
            row.operator("material.add_material_mods", text="Add to Materials")
            row.operator("material.remove_material_mods", text="Remove from Materials")

        # Settings are bound directly to Scene offset_bitmap_settings


    def material_matches_filter(self, material_name):
        """Check if material name matches include/exclude filters"""
        mat_name_lower = material_name.lower()

        # Check exclude filter first
        if self.material_exclude_filter:
            exclude_terms = [t.strip().lower() for t in self.material_exclude_filter.split(';') if t.strip()]
            for term in exclude_terms:
                if term in mat_name_lower:
                    return False

        # Check include filter
        if self.material_include_filter:
            include_terms = [t.strip() for t in self.material_include_filter.split(';') if t.strip()]
            for term in include_terms:
                if term in material_name:
                    return True
            return False

        # If no include filter, include by default (unless excluded)
        return True



    def process_decal_materials(self, add_fix=True):
        """Add or remove CameraOnly node group to/from graphics/atlas materials"""
        import os

        nodegroup_path = r"H:\000_Projects\Goliath\01-3_Marketing\03_Animation\Runner_Vignettes\01_Assets\3D\Nodegroups\CameraOnly.blend"
        nodegroup_name = "CameraOnly"

        if add_fix:
            # Append the node group if it doesn't exist
            if nodegroup_name not in bpy.data.node_groups:
                with bpy.data.libraries.load(nodegroup_path, link=False) as (data_from, data_to):
                    if nodegroup_name in data_from.node_groups:
                        data_to.node_groups = [nodegroup_name]

        count = 0
        for mat in bpy.data.materials:
            if not mat.use_nodes:
                continue

            # Process all materials (no hardcoded exclusion)

            nodes = mat.node_tree.nodes
            links = mat.node_tree.links

            # Find the material output node
            output_node = None
            for node in nodes:
                if node.type == 'OUTPUT_MATERIAL':
                    output_node = node
                    break

            if not output_node:
                continue

            if self.fix_decal_materials:
                # Add CameraOnly node group
                if nodegroup_name not in bpy.data.node_groups:
                    continue

                # Check if CameraOnly already exists
                camera_only_node = None
                for node in nodes:
                    if node.type == 'GROUP' and node.node_tree and node.node_tree.name == nodegroup_name:
                        camera_only_node = node
                        break

                if camera_only_node:
                    continue  # Already has the node group

                # Find what's currently connected to the output
                shader_input = output_node.inputs.get('Surface')
                if not shader_input or not shader_input.is_linked:
                    continue

                # Get the shader node connected to output
                shader_link = shader_input.links[0]
                shader_node = shader_link.from_node
                shader_socket = shader_link.from_socket

                # Create the CameraOnly node group
                camera_only_node = nodes.new('ShaderNodeGroup')
                camera_only_node.node_tree = bpy.data.node_groups[nodegroup_name]
                camera_only_node.location = (output_node.location.x - 300, output_node.location.y)

                # Remove the old connection
                links.remove(shader_link)

                # Connect shader -> CameraOnly -> output
                links.new(shader_socket, camera_only_node.inputs[0])
                links.new(camera_only_node.outputs[0], shader_input)

                count += 1

            elif self.remove_decal_fix:
                # Remove CameraOnly node group
                camera_only_node = None
                for node in nodes:
                    if node.type == 'GROUP' and node.node_tree and node.node_tree.name == nodegroup_name:
                        camera_only_node = node
                        break

                if not camera_only_node:
                    continue  # Doesn't have the node group

                # Find what's connected to the CameraOnly input
                if not camera_only_node.inputs[0].is_linked:
                    nodes.remove(camera_only_node)
                    continue

                shader_link = camera_only_node.inputs[0].links[0]
                shader_socket = shader_link.from_socket

                # Remove CameraOnly node
                nodes.remove(camera_only_node)

                # Reconnect shader directly to output
                links.new(shader_socket, output_node.inputs['Surface'])

                count += 1

        return count

    def process_material(self, material):
        """Process a single material to add mapping nodes to color bitmaps"""
        nodes = material.node_tree.nodes
        links = material.node_tree.links

        # Check if material matches filters
        if not self.material_matches_filter(material.name):
            # print(f"Material {material.name} - filtered out")
            return False

        image_nodes = [node for node in nodes if node.type == 'TEX_IMAGE']

        if not image_nodes:
            # print(f"Material {material.name} - no image nodes")
            return False

        # print(f"Material {material.name} - processing with {len(image_nodes)} image nodes")

        # Create or find texture coordinate node
        tex_coord = None
        for node in nodes:
            if node.type == 'TEX_COORD':
                tex_coord = node
                break

        if not tex_coord:
            tex_coord = nodes.new('ShaderNodeTexCoord')
            tex_coord.location = (-800, 0)

        # Create mapping node
        mapping = nodes.new('ShaderNodeMapping')
        mapping.location = (-600, 0)

        # Set mapping properties
        mapping.vector_type = self.mapping_type
        mapping.inputs['Location'].default_value = self.location
        mapping.inputs['Rotation'].default_value = self.rotation
        mapping.inputs['Scale'].default_value = self.scale

        # Connect texture coordinate to mapping
        links.new(tex_coord.outputs['UV'], mapping.inputs['Vector'])

        # Connect mapping to all image texture nodes
        for img_node in image_nodes:
            # Check if the vector input is already connected
            if img_node.inputs['Vector'].is_linked:
                # Remove existing link
                for link in img_node.inputs['Vector'].links:
                    links.remove(link)

            # Connect mapping to image node
            links.new(mapping.outputs['Vector'], img_node.inputs['Vector'])

        return True

    def execute(self, context):
        # Store filter settings in scene for other operators
        context.scene['offset_bitmaps_include_filter'] = self.material_include_filter
        context.scene['offset_bitmaps_exclude_filter'] = self.material_exclude_filter
        return {'FINISHED'}

    def invoke(self, context, event):
        # Scan for material mods and store in scene
        self.scan_material_mods(context)
        return context.window_manager.invoke_props_dialog(self, width=400)

    def scan_material_mods(self, context):
        """Scan the material mods folder for nodegroups"""
        # Clear scene collection
        context.scene.offset_bitmaps_mods.clear()

        if not os.path.exists(MATERIAL_MODS_PATH):
            return

        # Scan all .blend files in the folder
        for filename in os.listdir(MATERIAL_MODS_PATH):
            if not filename.endswith('.blend'):
                continue

            blend_path = os.path.join(MATERIAL_MODS_PATH, filename)

            # Load the blend file and check for node groups
            try:
                with bpy.data.libraries.load(blend_path, link=False) as (data_from, data_to):
                    for ng_name in data_from.node_groups:
                        # Only add if the prefix matches a known channel or is a 'shader' mod
                        if '_' in ng_name:
                            channel_prefix = ng_name.split('_')[0]
                            if channel_prefix in CHANNEL_MAPPING or channel_prefix.lower() == 'shader':
                                mod = context.scene.offset_bitmaps_mods.add()
                                mod.name = ng_name
                                mod.blend_file = blend_path
                                mod.enabled = False
            except Exception:
                pass  # Skip files that can't be loaded


class ApplyOffsetBitmapsOperator(bpy.types.Operator):
    """Apply offset bitmaps to materials"""
    bl_idname = "material.apply_offset_bitmaps"
    bl_label = "Apply Offset Bitmaps"
    bl_options = {'REGISTER', 'UNDO'}

    def execute(self, context):
        # Prefer live dialog values; fallback to Scene-mirrored
        include_filter, exclude_filter, mapping_type, location, rotation, scale = _get_current_ui_settings(context)

        updated_count = apply_offset_to_all_materials(
            include_filter, exclude_filter, mapping_type, location, rotation, scale
        )
        self.report({'INFO'}, f"Updated {updated_count} image texture(s)")
        return {'FINISHED'}


class AddDecalFixOperator(bpy.types.Operator):
    """Add CameraOnly node group to materials"""
    bl_idname = "material.add_decal_fix"
    bl_label = "Add Decal Fix"
    bl_options = {'REGISTER', 'UNDO'}

    def execute(self, context):
        include_filter, exclude_filter, _mt, _loc, _rot, _scale = _get_current_ui_settings(context)
        decal_count = process_decal_materials_core(add_fix=True, include_filter=include_filter, exclude_filter=exclude_filter)
        self.report({'INFO'}, f"Fixed {decal_count} decal material(s)")
        return {'FINISHED'}


class RemoveDecalFixOperator(bpy.types.Operator):
    """Remove CameraOnly node group from materials"""
    bl_idname = "material.remove_decal_fix"
    bl_label = "Remove Decal Fix"
    bl_options = {'REGISTER', 'UNDO'}

    def execute(self, context):
        include_filter, exclude_filter, _mt, _loc, _rot, _scale = _get_current_ui_settings(context)
        decal_count = process_decal_materials_core(add_fix=False, include_filter=include_filter, exclude_filter=exclude_filter)
        self.report({'INFO'}, f"Removed fix from {decal_count} decal material(s)")
        return {'FINISHED'}



class SwapIncludeExcludeOperator(bpy.types.Operator):
    """Swap Include and Exclude filter text"""
    bl_idname = "material.swap_filters"
    bl_label = "Swap Include/Exclude"
    bl_options = {'REGISTER', 'UNDO'}

    def execute(self, context):
        settings = getattr(context.scene, 'offset_bitmap_settings', None)
        if settings:
            inc = settings.material_include_filter
            exc = settings.material_exclude_filter
            settings.material_include_filter = exc
            settings.material_exclude_filter = inc
        return {'FINISHED'}






class AddMaterialModsOperator(bpy.types.Operator):
    """Add selected material mods to materials"""
    bl_idname = "material.add_material_mods"
    bl_label = "Add Material Mods"
    bl_options = {'REGISTER', 'UNDO', 'INTERNAL'}

    def execute(self, context):
        # Get material mods from scene
        if not hasattr(context.scene, 'offset_bitmaps_mods'):
            self.report({'ERROR'}, "No material mods data found")
            return {'CANCELLED'}

        mods_data = context.scene.offset_bitmaps_mods
        enabled_mods = [mod for mod in mods_data if mod.enabled]

        if not enabled_mods:
            self.report({'WARNING'}, "No material mods selected")
            return {'CANCELLED'}

        # Append all enabled nodegroups
        for mod in enabled_mods:
            if mod.name not in bpy.data.node_groups:
                try:
                    with bpy.data.libraries.load(mod.blend_file, link=False) as (data_from, data_to):
                        if mod.name in data_from.node_groups:
                            data_to.node_groups = [mod.name]
                except Exception:
                    self.report({'WARNING'}, f"Could not load {mod.name}")
                    continue

        # Get filter settings from Scene settings
        settings = getattr(context.scene, 'offset_bitmap_settings', None)
        include_filter = settings.material_include_filter if settings else ''
        exclude_filter = settings.material_exclude_filter if settings else ''

        # Process selected objects
        count = 0
        for obj in context.selected_objects:
            if obj.type != 'MESH':
                continue

            for mat_slot in obj.material_slots:
                if not mat_slot.material or not mat_slot.material.use_nodes:
                    continue

                mat = mat_slot.material

                # Check if material matches filters
                if not self.material_matches_filter(mat.name, include_filter, exclude_filter):
                    continue

                # Add each enabled mod
                for mod in enabled_mods:
                    if mod.name not in bpy.data.node_groups:
                        continue

                    if self.add_mod_to_material(mat, mod.name):
                        count += 1

        self.report({'INFO'}, f"Added material mods to {count} material(s)")
        return {'FINISHED'}

    def material_matches_filter(self, material_name, include_filter, exclude_filter):
        """Check if material name matches include/exclude filters"""
        mat_name_lower = material_name.lower()

        # Check exclude filter first
        if exclude_filter:
            exclude_terms = [t.strip().lower() for t in exclude_filter.split(';') if t.strip()]
            for term in exclude_terms:
                if term in mat_name_lower:
                    return False

        # Check include filter
        if include_filter:
            include_terms = [t.strip() for t in include_filter.split(';') if t.strip()]
            for term in include_terms:
                if term in material_name:
                    return True
            return False

        # If no include filter, include by default (unless excluded)
        return True

    def add_mod_to_material(self, material, nodegroup_name):
        """Add a material mod nodegroup to a material.
        - If the nodegroup name starts with 'shader_', insert it before the Material Output:
          group's SHADER output -> Material Output Surface; previous Surface source -> group's SHADER input.
        - Otherwise, connect it to the mapped shader input from CHANNEL_MAPPING (as before).
        """
        nodes = material.node_tree.nodes
        links = material.node_tree.links

        # Parse the channel from the nodegroup name (e.g., "BaseColor_DiffuseImperfections" or "shader_Mask")
        if '_' not in nodegroup_name:
            return False

        channel_prefix = nodegroup_name.split('_')[0]

        # Special case: 'shader' prefix -> insert before Material Output
        if channel_prefix.lower() == 'shader':
            # Already present?
            for n in nodes:
                if n.type == 'GROUP' and n.node_tree and n.node_tree.name == nodegroup_name:
                    return False

            if nodegroup_name not in bpy.data.node_groups:
                return False

            # Find active Material Output
            output = None
            for n in nodes:
                if n.type == 'OUTPUT_MATERIAL' and getattr(n, 'is_active_output', False):
                    output = n; break
            if not output:
                for n in nodes:
                    if n.type == 'OUTPUT_MATERIAL':
                        output = n; break
            if not output:
                return False

            surface_input = output.inputs.get('Surface', None)
            if not surface_input:
                return False

            # Create the nodegroup
            mod_node = nodes.new('ShaderNodeGroup')
            mod_node.node_tree = bpy.data.node_groups[nodegroup_name]
            mod_node.location = (output.location.x - 240, output.location.y)

            # Helper to pick SHADER sockets if available
            def pick_output_socket(node):
                for s in node.outputs:
                    if s.type == 'SHADER':
                        return s
                return node.outputs[0] if node.outputs else None

            def pick_input_socket(node):
                for s in node.inputs:
                    if s.type == 'SHADER':
                        return s
                return node.inputs[0] if node.inputs else None

            mod_out = pick_output_socket(mod_node)
            mod_in = pick_input_socket(mod_node)

            # Rewire: previous Surface source -> mod input; mod output -> Surface
            prev_from_socket = None
            if surface_input.is_linked:
                old_link = surface_input.links[0]
                prev_from_socket = old_link.from_socket
                links.remove(old_link)

            if prev_from_socket and mod_in:
                try:
                    links.new(prev_from_socket, mod_in)
                except Exception:
                    pass

            if mod_out:
                links.new(mod_out, surface_input)
                return True
            # Fallback if no outputs
            return False

        # Default path: channel-based mapping into shader input
        shader_input_name = CHANNEL_MAPPING.get(channel_prefix)
        if not shader_input_name:
            return False

        # Find a shader node to accept the input
        shader_node = None
        for node in nodes:
            if node.type == 'BSDF_PRINCIPLED':
                shader_node = node
                break
        if not shader_node:
            for node in nodes:
                if node.type.startswith('BSDF_'):
                    shader_node = node
                    break
        if not shader_node:
            for node in nodes:
                if node.type == 'GROUP' and node.node_tree:
                    if shader_input_name in node.inputs:
                        shader_node = node
                        break
        if not shader_node:
            return False
        if shader_input_name not in shader_node.inputs:
            return False

        # Already present?
        for node in nodes:
            if node.type == 'GROUP' and node.node_tree and node.node_tree.name == nodegroup_name:
                return False

        # Create and connect
        mod_node = nodes.new('ShaderNodeGroup')
        mod_node.node_tree = bpy.data.node_groups[nodegroup_name]
        mod_node.location = (shader_node.location.x - 300, shader_node.location.y)

        shader_input = shader_node.inputs[shader_input_name]
        if shader_input.is_linked:
            existing_link = shader_input.links[0]
            existing_socket = existing_link.from_socket
            links.remove(existing_link)
            if mod_node.inputs:
                links.new(existing_socket, mod_node.inputs[0])
        if mod_node.outputs:
            links.new(mod_node.outputs[0], shader_input)
        return True


class RemoveMaterialModsOperator(bpy.types.Operator):
    """Remove selected material mods from materials"""
    bl_idname = "material.remove_material_mods"
    bl_label = "Remove Material Mods"
    bl_options = {'REGISTER', 'UNDO', 'INTERNAL'}

    def execute(self, context):
        # Get material mods from scene
        if not hasattr(context.scene, 'offset_bitmaps_mods'):
            self.report({'ERROR'}, "No material mods data found")
            return {'CANCELLED'}

        mods_data = context.scene.offset_bitmaps_mods
        enabled_mods = [mod for mod in mods_data if mod.enabled]

        if not enabled_mods:
            self.report({'WARNING'}, "No material mods selected")
            return {'CANCELLED'}

        # Get filters
        settings = getattr(context.scene, 'offset_bitmap_settings', None)
        include_filter = settings.material_include_filter if settings else ''
        exclude_filter = settings.material_exclude_filter if settings else ''

        # Process selected objects
        count = 0
        for obj in context.selected_objects:
            if obj.type != 'MESH':
                continue

            for mat_slot in obj.material_slots:
                if not mat_slot.material or not mat_slot.material.use_nodes:
                    continue

                mat = mat_slot.material

                # Respect filters
                if not _matches_filter(mat.name, include_filter, exclude_filter):
                    continue

                # Remove each enabled mod
                for mod in enabled_mods:
                    if self.remove_mod_from_material(mat, mod.name):
                        count += 1

        self.report({'INFO'}, f"Removed material mods from {count} material(s)")
        return {'FINISHED'}

    def remove_mod_from_material(self, material, nodegroup_name):
        """Remove a material mod nodegroup from a material"""
        nodes = material.node_tree.nodes
        links = material.node_tree.links

        # Find the nodegroup
        mod_node = None
        for node in nodes:
            if node.type == 'GROUP' and node.node_tree and node.node_tree.name == nodegroup_name:
                mod_node = node
                break

        if not mod_node:
            return False

        # Get what's connected to the mod's input and output
        input_socket = None
        output_socket = None

        if mod_node.inputs[0].is_linked:
            input_socket = mod_node.inputs[0].links[0].from_socket

        if mod_node.outputs[0].is_linked:
            output_link = mod_node.outputs[0].links[0]
            output_socket = output_link.to_socket
            links.remove(output_link)

        # Remove the mod node
        nodes.remove(mod_node)

        # Reconnect input to output (dissolve the node)
        if input_socket and output_socket:
            links.new(input_socket, output_socket)

        return True


def register():
    bpy.utils.register_class(MaterialModItem)
    bpy.utils.register_class(OffsetBitmapSettings)
    bpy.utils.register_class(OffsetBitmapsOperator)
    bpy.utils.register_class(ApplyOffsetBitmapsOperator)
    bpy.utils.register_class(AddDecalFixOperator)
    bpy.utils.register_class(RemoveDecalFixOperator)
    bpy.utils.register_class(SwapIncludeExcludeOperator)
    bpy.utils.register_class(AddMaterialModsOperator)
    bpy.utils.register_class(RemoveMaterialModsOperator)

    # Register scene properties
    bpy.types.Scene.offset_bitmaps_mods = CollectionProperty(type=MaterialModItem)
    bpy.types.Scene.offset_bitmap_settings = PointerProperty(type=OffsetBitmapSettings)


def unregister():
    # Unregister scene properties
    del bpy.types.Scene.offset_bitmap_settings
    del bpy.types.Scene.offset_bitmaps_mods

    bpy.utils.unregister_class(RemoveMaterialModsOperator)
    bpy.utils.unregister_class(AddMaterialModsOperator)
    bpy.utils.unregister_class(SwapIncludeExcludeOperator)
    bpy.utils.unregister_class(RemoveDecalFixOperator)
    bpy.utils.unregister_class(AddDecalFixOperator)
    bpy.utils.unregister_class(ApplyOffsetBitmapsOperator)
    bpy.utils.unregister_class(OffsetBitmapsOperator)
    bpy.utils.unregister_class(OffsetBitmapSettings)
    bpy.utils.unregister_class(MaterialModItem)



register()

# Test call
bpy.ops.material.offset_bitmaps('INVOKE_DEFAULT')
