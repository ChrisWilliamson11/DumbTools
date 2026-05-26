import bpy
import json
import os
import math
from bpy_extras.io_utils import ImportHelper

class DUMBTOOLS_OT_usd_trail_import(bpy.types.Operator, ImportHelper):
    """Select a USD to import as an animated fading trail"""
    bl_idname = "dumbtools.usd_trail_import"
    bl_label = "Import USD as Trail"
    bl_options = {'REGISTER', 'UNDO'}

    filename_ext = ".usd"
    filter_glob: bpy.props.StringProperty(
        default="*.usd;*.usda;*.usdc",
        options={'HIDDEN'},
        maxlen=255,  
    )

    num_copies: bpy.props.IntProperty(
        name="Number of Copies",
        description="Number of trail copies to generate",
        default=5,
        min=1
    )
    
    time_offset: bpy.props.FloatProperty(
        name="Time Offset",
        description="Time offset increment per copy",
        default=-0.1
    )
    
    max_opacity: bpy.props.FloatProperty(
        name="Max Opacity",
        description="Maximum opacity for the head of the trail (1.0 = opaque, 0.0 = fully faded)",
        default=1.0,
        min=0.0,
        max=1.0
    )
    
    search_path: bpy.props.StringProperty(
        name="Material Search Path",
        description="Path segment to replace in the original material file paths",
        default=""
    )
    
    replace_path: bpy.props.StringProperty(
        name="Material Replace Path",
        description="New path segment to insert",
        default=""
    )
    
    overwrite_existing: bpy.props.BoolProperty(
        name="Overwrite Existing (Fix Proxies)",
        description="If a material exists, explicitly download the true one from the source",
        default=True
    )

    def draw(self, context):
        layout = self.layout
        box = layout.box()
        box.label(text="Trail Settings:")
        box.prop(self, "num_copies")
        box.prop(self, "time_offset")
        box.prop(self, "max_opacity")
        
        layout.separator()
        box = layout.box()
        box.label(text="Material Restore Settings:")
        box.prop(self, "search_path", text="Find")
        box.prop(self, "replace_path", text="Replace")
        box.prop(self, "overwrite_existing")

    def execute(self, context):
        file_name = os.path.basename(self.filepath)
        root_col = bpy.data.collections.new(f"Trail_{file_name}")
        context.scene.collection.children.link(root_col)
        
        controller = bpy.data.objects.new(f"Trail_Controller_{file_name}", None)
        root_col.objects.link(controller)
        controller["time_offset"] = self.time_offset
        controller["max_opacity"] = self.max_opacity
        
        first_copy_materials = {}
        missing_files = set()
        
        def get_or_append_material(mat_name, path):
            cache_key = (mat_name, path)
            if cache_key in first_copy_materials:
                return first_copy_materials[cache_key]
                
            existing_mat = bpy.data.materials.get(mat_name)
            
            if existing_mat and not self.overwrite_existing:
                first_copy_materials[cache_key] = existing_mat
                return existing_mat
                
            if existing_mat and existing_mat.get("_dt_restored"):
                first_copy_materials[cache_key] = existing_mat
                return existing_mat
                
            if not path or not os.path.exists(path):
                if path: missing_files.add(path)
                return existing_mat
                
            try:
                with bpy.data.libraries.load(path, link=False) as (data_from, data_to):
                    if mat_name in data_from.materials:
                        data_to.materials.append(mat_name)
                
                for m in data_to.materials:
                    if m is not None:
                        m["_dt_restored"] = True
                        first_copy_materials[cache_key] = m
                        
                        if existing_mat and existing_mat != m:
                            existing_mat.user_remap(m)
                            existing_mat.name = existing_mat.name + "_Ghost"
                            m.name = mat_name
                            
                        return m
            except Exception as e:
                print(f"USD Import Restore: Failed to load material {mat_name} from {path}. Error: {e}")
                
            return existing_mat

        def process_materials(objects, is_first_copy):
            for obj in objects:
                if "_dt_usd_materials" not in obj: continue
                try:
                    mat_data = json.loads(obj["_dt_usd_materials"])
                except Exception:
                    continue
                    
                if getattr(obj, "data", None) and hasattr(obj.data, "materials"):
                    max_slot_idx = max([int(k) for k in mat_data.keys()]) if mat_data else -1
                    while len(obj.material_slots) <= max_slot_idx:
                        obj.data.materials.append(None)
                        
                    poly_remap = {}
                    for current_idx, slot in enumerate(obj.material_slots):
                        mat = slot.material
                        if not mat: continue
                        if mat.get("_dt_restored"): continue
                            
                        mat_name = mat.name
                        base_name = mat_name[:-9] if mat_name.endswith("_USDProxy") else mat_name
                        
                        original_idx = None
                        for slot_idx_str, data in mat_data.items():
                            j_name = data.get("name")
                            if j_name and (base_name == j_name or base_name.startswith(j_name + ".")):
                                original_idx = int(slot_idx_str)
                                break
                                
                        if original_idx is not None:
                            if (mat.name == base_name or mat.name.startswith(base_name + ".")) and "_dt_restored" not in mat:
                                mat.name = base_name + "_USDProxy"
                            poly_remap[current_idx] = original_idx
                            
                    if poly_remap and hasattr(obj.data, "polygons") and len(obj.data.polygons) > 0:
                        poly_indices = [0] * len(obj.data.polygons)
                        obj.data.polygons.foreach_get("material_index", poly_indices)
                        changed = False
                        for idx in range(len(poly_indices)):
                            old_idx = poly_indices[idx]
                            if old_idx in poly_remap and poly_remap[old_idx] != old_idx:
                                poly_indices[idx] = poly_remap[old_idx]
                                changed = True
                        if changed:
                            obj.data.polygons.foreach_set("material_index", poly_indices)
                            obj.data.update()

            for obj in objects:
                if "_dt_usd_materials" not in obj: continue
                try:
                    mat_data = json.loads(obj["_dt_usd_materials"])
                except Exception:
                    continue
                    
                for slot_idx_str, data in mat_data.items():
                    slot_idx = int(slot_idx_str)
                    mat_name = data.get("name")
                    mat_path = data.get("path")
                    link_param = data.get("link_param", 'OBJECT')
                    
                    if mat_name is None:
                        mat = None
                    else:
                        if self.search_path and mat_path:
                            mat_path = mat_path.replace(self.search_path, self.replace_path)
                            
                        if is_first_copy:
                            mat = get_or_append_material(mat_name, mat_path)
                        else:
                            cache_key = (mat_name, mat_path)
                            mat = first_copy_materials.get(cache_key)
                    
                    if getattr(obj, "data", None) and hasattr(obj.data, "materials"):
                        while len(obj.material_slots) <= slot_idx:
                            obj.data.materials.append(None)
                    
                    if slot_idx < len(obj.material_slots):
                        obj.material_slots[slot_idx].material = mat
                        obj.material_slots[slot_idx].link = link_param
                
                del obj["_dt_usd_materials"]

        def insert_fade_group_to_materials():
            fade_group = bpy.data.node_groups.get("FadeGroup")
            if not fade_group:
                return
                
            for mat in first_copy_materials.values():
                if not mat or not mat.use_nodes:
                    continue
                
                if any(node.type == 'GROUP' and node.node_tree == fade_group for node in mat.node_tree.nodes):
                    continue
                    
                output_node = None
                for node in mat.node_tree.nodes:
                    if node.type == 'OUTPUT_MATERIAL':
                        output_node = node
                        break
                        
                if not output_node:
                    continue
                    
                surface_socket = output_node.inputs.get('Surface')
                if not surface_socket or not surface_socket.is_linked:
                    continue
                    
                incoming_link = surface_socket.links[0]
                source_node = incoming_link.from_node
                source_socket = incoming_link.from_socket
                
                mat.node_tree.links.remove(incoming_link)
                
                group_node = mat.node_tree.nodes.new(type='ShaderNodeGroup')
                group_node.node_tree = fade_group
                group_node.location = (output_node.location.x - 200, output_node.location.y)
                
                if len(group_node.inputs) > 0:
                    mat.node_tree.links.new(source_socket, group_node.inputs[0])
                
                if len(group_node.outputs) > 0:
                    mat.node_tree.links.new(group_node.outputs[0], surface_socket)

        original_active_layer_col = context.view_layer.active_layer_collection
        
        geo_group = bpy.data.node_groups.get("SetFadeAttribute")
        if not geo_group:
            self.report({'WARNING'}, "Geometry node group 'SetFadeAttribute' not found in scene.")
            
        fade_group = bpy.data.node_groups.get("FadeGroup")
        if not fade_group:
            self.report({'WARNING'}, "Shader node group 'FadeGroup' not found in scene.")
        
        for i in range(self.num_copies):
            sub_col = bpy.data.collections.new(f"Trail_Copy_{i}")
            root_col.children.link(sub_col)
            
            layer_col = self.find_layer_collection(context.view_layer.layer_collection, sub_col.name)
            if layer_col:
                context.view_layer.active_layer_collection = layer_col
            
            pre_caches = set(bpy.data.cache_files)
            
            try:
                bpy.ops.wm.usd_import(filepath=self.filepath)
            except Exception as e:
                self.report({'ERROR'}, f"Failed to import USD on copy {i}: {e}")
                continue
                
            imported_objects = context.selected_objects
            
            process_materials(imported_objects, is_first_copy=(i == 0))
            
            post_caches = set(bpy.data.cache_files)
            new_caches = post_caches - pre_caches
            
            for cache in new_caches:
                fcurve = cache.driver_add('frame_offset')
                driver = fcurve.driver
                driver.type = 'SCRIPTED'
                
                var = driver.variables.new()
                var.name = "offset"
                var.type = 'SINGLE_PROP'
                
                target = var.targets[0]
                target.id_type = 'OBJECT'
                target.id = controller
                target.data_path = '["time_offset"]'
                
                driver.expression = f"offset * {i}"
                
            ratio = i / max(1.0, float(self.num_copies - 1))
            
            for obj in imported_objects:
                if obj.type not in {'MESH', 'CURVE'}:
                    continue
                    
                if geo_group:
                    mod = obj.modifiers.new(name="FadeModifier", type='NODES')
                    mod.node_group = geo_group
                    
                    input_id = self.find_node_group_input_identifier(geo_group, "Fade")
                    if input_id:
                        data_path = f'modifiers["{mod.name}"]["{input_id}"]'
                        try:
                            fcurve = obj.driver_add(data_path)
                            driver = fcurve.driver
                            driver.type = 'SCRIPTED'
                            
                            var = driver.variables.new()
                            var.name = "opacity"
                            var.type = 'SINGLE_PROP'
                            
                            target = var.targets[0]
                            target.id_type = 'OBJECT'
                            target.id = controller
                            target.data_path = '["max_opacity"]'
                            
                            driver.expression = f"(1.0 - opacity) + opacity * {ratio}"
                        except Exception as e:
                            print(f"Failed to add driver to {obj.name}: {e}")
        
        insert_fade_group_to_materials()
        
        context.view_layer.active_layer_collection = original_active_layer_col
        
        msg = f"Imported {self.num_copies} trail copies."
        if missing_files:
            msg += f" WARNING: missing {len(missing_files)} source files!"
        self.report({'INFO'}, msg)
        return {'FINISHED'}

    def find_layer_collection(self, layer_col, name):
        if layer_col.name == name:
            return layer_col
        for child in layer_col.children:
            result = self.find_layer_collection(child, name)
            if result: return result
        return None
        
    def find_node_group_input_identifier(self, group, socket_name):
        if hasattr(group, "interface"):
            for item in group.interface.items_tree:
                if item.item_type == 'SOCKET' and item.name == socket_name:
                    return item.identifier
        else:
            for inp in group.inputs:
                if inp.name == socket_name:
                    return inp.identifier
        return socket_name

def register():
    try:
        bpy.utils.register_class(DUMBTOOLS_OT_usd_trail_import)
    except Exception:
        pass

def unregister():
    try:
        bpy.utils.unregister_class(DUMBTOOLS_OT_usd_trail_import)
    except Exception:
        pass


register()
bpy.ops.dumbtools.usd_trail_import('INVOKE_DEFAULT')
