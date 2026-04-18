# Tooltip: Tags selected objects with their original material assignments and file paths for USD export.
import bpy
import json
from bpy_extras.io_utils import ExportHelper

class DUMBTOOLS_OT_usd_material_export(bpy.types.Operator, ExportHelper):
    """Tags selected objects with material assignment metadata and exports to USD"""
    bl_idname = "dumbtools.usd_material_export"
    bl_label = "Export USD with Materials"
    bl_options = {'REGISTER', 'UNDO'}
    
    filename_ext = ".usd"
    filter_glob: bpy.props.StringProperty(
        default="*.usd;*.usdc;*.usda",
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
        
        # 1. Non-destructive Collection Instance Processor
        instances = [obj for obj in original_selection if getattr(obj, "instance_type", "") == 'COLLECTION' and obj.instance_collection]
        
        for instance_empty in instances:
            bpy.ops.object.select_all(action='DESELECT')
            
            # Select only the specific instance
            instance_empty.select_set(True)
            context.view_layer.objects.active = instance_empty
            
            # Isolate a duplicate so we don't destroy the original empty during Make Real
            bpy.ops.object.duplicate(linked=False)
            dummy_empty = context.active_object
            
            # Explode the duplicate into real geometry
            bpy.ops.object.duplicates_make_real(use_base_instance=False, use_hierarchy=True)
            
            realized_objects = []
            for obj in context.selected_objects:
                if obj != dummy_empty:
                    realized_objects.append(obj)
            
            for real_obj in realized_objects:
                temp_objects_to_delete.append(real_obj)
                objects_to_export.add(real_obj)
                
                # Rigid-link the realized geometry to the original Empty so it perfectly inherits constraints!
                real_obj.parent = instance_empty
                real_obj.matrix_parent_inverse = instance_empty.matrix_world.inverted()
                
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
