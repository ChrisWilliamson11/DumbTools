# Tooltip: Tags selected objects with their original material assignments and file paths for USD export.
import bpy
import json
from bpy_extras.io_utils import ExportHelper

class DUMBTOOLS_OT_usd_material_export(bpy.types.Operator, ExportHelper):
    """Tags selected objects with material assignment metadata and exports to USD"""
    bl_idname = "dumbtools.usd_material_export"
    bl_label = "Export USD with Materials"
    bl_options = {'REGISTER', 'UNDO'}
    
    filename_ext = ".usdc"
    filter_glob: bpy.props.StringProperty(
        default="*.usdc;*.usd;*.usda",
        options={'HIDDEN'},
        maxlen=255,
    )
    
    export_animation: bpy.props.BoolProperty(
        name="Export Animation",
        description="Bake animation over the scene frame range",
        default=True
    )
    
    export_armatures: bpy.props.BoolProperty(
        name="Export Armatures",
        description="Include armatures in the USD hierarchy",
        default=False
    )
    
    export_shapekeys: bpy.props.BoolProperty(
        name="Export Shapekeys",
        description="Include shapekeys (blendshapes)",
        default=False
    )

    def draw(self, context):
        layout = self.layout
        box = layout.box()
        box.label(text="DumbTools Output Settings:")
        box.prop(self, "export_animation")
        box.prop(self, "export_armatures")
        box.prop(self, "export_shapekeys")
        layout.label(text="* 'Selected Objects Only' is strictly enforced.", icon='INFO')

    def execute(self, context):
        if not bpy.data.is_saved:
            self.report({'WARNING'}, "Current file is not saved. Local material paths will be empty. Please save your .blend file first!")

        tagged_count = 0
        original_selection = list(context.selected_objects)
        original_active = context.active_object
        
        objects_to_export = set(original_selection)
        temp_objects_to_delete = []
        
        # Force an initial depsgraph update
        context.view_layer.update()
        
        # 1. Non-destructive Collection Instance Processor
        instances = [obj for obj in original_selection if getattr(obj, "instance_type", "") == 'COLLECTION' and obj.instance_collection]
        stored_collections = {}
        
        for instance_empty in instances:
            bpy.ops.object.select_all(action='DESELECT')
            
            # Select only the specific instance
            instance_empty.select_set(True)
            context.view_layer.objects.active = instance_empty
            
            # Isolate a duplicate so we don't destroy the original empty during Make Real
            bpy.ops.object.duplicate(linked=False)
            dummy_empty = context.active_object
            
            # CRITICAL: Blender hasn't populated this new dummy empty into the scene graph yet. 
            context.view_layer.update()
            
            # Use strict set subtraction to perfectly isolate what Make Instances Real actually creates
            objs_before = set(context.scene.objects)
            
            # Explode the duplicate into real geometry
            try:
                bpy.ops.object.duplicates_make_real(use_hierarchy=True)
            except Exception:
                bpy.ops.object.duplicates_make_real()
                
            objs_after = set(context.scene.objects)
            realized_objects = list(objs_after - objs_before)
            
            for real_obj in realized_objects:
                temp_objects_to_delete.append(real_obj)
                objects_to_export.add(real_obj)
                
                # Rigid-link the realized geometry to the original Empty so it perfectly inherits constraints!
                # We save world matrix explicitly first to avert weird shifts if Blender pre-parented them to dummy_empty
                real_matrix = real_obj.matrix_world.copy()
                real_obj.parent = instance_empty
                real_obj.matrix_parent_inverse = instance_empty.matrix_world.inverted()
                real_obj.matrix_world = real_matrix
                
            # Temporarily strip the original Empty of its exact "Collection Instance" properties.
            # If we don't do this, the USD Exporter sees it's a Collection Instance and aggressively 
            # ignores/culls all its children, causing an empty 1kb export!
            stored_collections[instance_empty] = instance_empty.instance_collection
            instance_empty.instance_type = 'NONE'
            instance_empty.instance_collection = None
                
            # Queue the sacrifical dummy empty for cleanup
            try:
                if dummy_empty and dummy_empty.name != instance_empty.name and dummy_empty in context.scene.objects[:]:
                    temp_objects_to_delete.append(dummy_empty)
            except ReferenceError:
                pass

        # 2. Add Material Metadata Tags
        for obj in objects_to_export:
            if obj.type not in {'MESH', 'CURVE', 'SURFACE', 'META', 'FONT', 'GPENCIL'}:
                continue
                
            if getattr(obj, "instance_type", "") == 'COLLECTION':
                continue
                
            if not getattr(obj, "material_slots", None):
                continue
                
            mat_data = {}
            for i, slot in enumerate(obj.material_slots):
                mat = slot.material
                if not mat:
                    mat_data[str(i)] = {
                        "name": None,
                        "path": "",
                        "link_param": getattr(slot, "link", 'OBJECT')
                    }
                    continue
                    
                path = ""
                if mat.library:
                    path = mat.library.filepath
                else:
                    path = bpy.data.filepath
                    
                if path.startswith("//"):
                    path = bpy.path.abspath(path)
                    
                mat_data[str(i)] = {
                    "name": mat.name,
                    "path": path,
                    "link_param": slot.link
                }
            
            if mat_data:
                obj["_dt_usd_materials"] = json.dumps(mat_data)
                tagged_count += 1
                
        # 3. Target the Export
        bpy.ops.object.select_all(action='DESELECT')
        for obj in objects_to_export:
            try: obj.select_set(True)
            except: pass

        # Change to a loading cursor and force Blender to redraw the interface.
        context.window.cursor_set('WAIT')
        bpy.ops.wm.redraw_timer(type='DRAW_WIN_SWAP', iterations=1)
        
        # CRITICAL: We've spawned raw meshes, altered parents, and changed selection states. 
        context.view_layer.update()
        
        # DEBUG LOGGER
        try:
            log_path = self.filepath + ".log.txt"
            with open(log_path, "w") as f:
                f.write("--- DUMBTOOLS USD DEBUG LOG ---\n")
                f.write(f"Export Animation: {self.export_animation}\n")
                f.write(f"Original Collection Instances detected: {len(instances)}\n")
                f.write(f"Target Export Objects set count: {len(objects_to_export)}\n")
                f.write(f"Current Context Selected Objects count: {len(context.selected_objects)}\n\n")
                
                f.write("--- OBJECTS TO EXPORT SET ---\n")
                for obj in objects_to_export:
                    parent_name = obj.parent.name if obj.parent else "None"
                    f.write(f"Name: {obj.name} | Type: {obj.type} | Sel: {obj.select_get()} | Parent: {parent_name}\n")
                    
                f.write("\n--- CONTEXT SELECTED OBJECTS LIST ---\n")
                for obj in context.selected_objects:
                    parent_name = obj.parent.name if obj.parent else "None"
                    f.write(f"Name: {obj.name} | Type: {obj.type} | Sel: {obj.select_get()} | Parent: {parent_name}\n")
        except Exception:
            pass

        # 4. Trigger Synchronous Native USD Export
        try:
            try:
                bpy.ops.wm.usd_export(filepath=self.filepath,
                    selected_objects_only=True,
                    export_animation=self.export_animation,
                    export_armatures=self.export_armatures,
                    export_shapekeys=self.export_shapekeys,
                    export_custom_properties=True
                )
            except Exception as e:
                try:
                    bpy.ops.wm.usd_export(filepath=self.filepath,
                        selected_objects_only=True,
                        export_animation=self.export_animation,
                        export_custom_properties=True
                    )
                except Exception as e2:
                    bpy.ops.wm.usd_export(filepath=self.filepath, selected_objects_only=True)
                    
            self.report({'INFO'}, f"Smoothly exported {len(context.selected_objects)} total objects with {tagged_count} material tags.")
        except Exception as e:
            self.report({'ERROR'}, f"Failed to export USD: {e}")
            
        finally:
            # Restore the standard Blender cursor
            context.window.cursor_set('DEFAULT')
        
        # 5. Perfect Deep Clean!
        # Quietly annihilate all the temporary realized geometry we created
        for obj in temp_objects_to_delete:
            try:
                if getattr(obj, "data", None):
                    bpy.data.objects.remove(obj, do_unlink=True)
                else:    
                    bpy.data.objects.remove(obj, do_unlink=True)
            except ReferenceError:
                pass
                
        # Restore the stripped Collection Instances
        for instance_empty, col in stored_collections.items():
            try:
                if instance_empty and getattr(instance_empty, "name", None):
                    instance_empty.instance_type = 'COLLECTION'
                    instance_empty.instance_collection = col
            except ReferenceError:
                pass
                
        # Restore selection state precisely
        bpy.ops.object.select_all(action='DESELECT')
        for obj in original_selection:
            try: obj.select_set(True)
            except ReferenceError: pass
            
        if original_active:
            try: context.view_layer.objects.active = original_active
            except ReferenceError: pass

        return {'FINISHED'}


def register():
    try:
        bpy.utils.register_class(DUMBTOOLS_OT_usd_material_export)
    except Exception:
        pass


def unregister():
    try:
        bpy.utils.unregister_class(DUMBTOOLS_OT_usd_material_export)
    except Exception:
        pass


register()
bpy.ops.dumbtools.usd_material_export('INVOKE_DEFAULT')
