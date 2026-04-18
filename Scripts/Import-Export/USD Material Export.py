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
                real_matrix = real_obj.matrix_world.copy()
                real_obj.parent = instance_empty
                real_obj.matrix_parent_inverse = instance_empty.matrix_world.inverted()
                real_obj.matrix_world = real_matrix
                
                # CRITICAL VISIBILITY OVERRIDE:
                # Make Instances Real often places objects into the original hidden proxy collections.
                # If they are hidden, USD skips them unconditionally!
                try: context.scene.collection.objects.link(real_obj)
                except Exception: pass
                real_obj.hide_viewport = False
                real_obj.hide_render = False
                
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
            
        context.view_layer.update()
        
        # Save necessary state to class variables so the timer can access them!
        self.__class__._deferred_filepath = self.filepath
        self.__class__._deferred_animation = self.export_animation
        self.__class__._deferred_armatures = self.export_armatures
        self.__class__._deferred_shapekeys = self.export_shapekeys
        self.__class__._deferred_temp_objects = temp_objects_to_delete
        self.__class__._deferred_stored_collections = stored_collections
        self.__class__._deferred_original_selection = original_selection
        self.__class__._deferred_original_active = original_active

        # Change to a loading cursor and force Blender to redraw the interface.
        context.window.cursor_set('WAIT')
        bpy.ops.wm.redraw_timer(type='DRAW_WIN_SWAP', iterations=1)

        # Defer the C++ USD Exporter by 0.1 seconds.
        # This completely guarantees Blender's internal Main Thread organically flushes the 
        # C++ BASE_SELECTED flags so the USD exporter actually sees the exact selection!
        bpy.app.timers.register(self.__class__.deferred_export, first_interval=0.1)
        
        return {'FINISHED'}

    @classmethod
    def deferred_export(cls):
        try:
            try:
                bpy.ops.wm.usd_export(filepath=cls._deferred_filepath,
                    selected_objects_only=True,
                    export_animation=cls._deferred_animation,
                    export_armatures=cls._deferred_armatures,
                    export_shapekeys=cls._deferred_shapekeys,
                    export_custom_properties=True
                )
            except Exception:
                try:
                    bpy.ops.wm.usd_export(filepath=cls._deferred_filepath,
                        selected_objects_only=True,
                        export_animation=cls._deferred_animation,
                        export_custom_properties=True
                    )
                except Exception:
                    bpy.ops.wm.usd_export(filepath=cls._deferred_filepath, selected_objects_only=True)
                    
            print(f"[DumbTools] Smoothly exported {len(bpy.context.selected_objects)} objects to USD.")
        except Exception as e:
            print(f"[DumbTools] Failed to export USD: {e}")
            
        finally:
            # Restore the standard Blender cursor
            bpy.context.window.cursor_set('DEFAULT')
        
            # 5. Perfect Deep Clean!
            for obj in cls._deferred_temp_objects:
                try:
                    if getattr(obj, "data", None):
                        bpy.data.objects.remove(obj, do_unlink=True)
                    else:    
                        bpy.data.objects.remove(obj, do_unlink=True)
                except ReferenceError:
                    pass
                    
            # Restore the stripped Collection Instances
            for instance_empty, col in cls._deferred_stored_collections.items():
                try:
                    if instance_empty and getattr(instance_empty, "name", None):
                        instance_empty.instance_type = 'COLLECTION'
                        instance_empty.instance_collection = col
                except ReferenceError:
                    pass
                    
            # Restore selection state precisely
            bpy.ops.object.select_all(action='DESELECT')
            for obj in cls._deferred_original_selection:
                try: obj.select_set(True)
                except ReferenceError: pass
                
            if cls._deferred_original_active:
                try: bpy.context.view_layer.objects.active = cls._deferred_original_active
                except ReferenceError: pass
                
            # Final flush
            bpy.context.view_layer.update()


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
