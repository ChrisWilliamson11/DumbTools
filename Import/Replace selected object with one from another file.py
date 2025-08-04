# Tooltip:  Select an object that exists in another file, run this then select the file, it will replace the selected object with the one from the file
import bpy
from bpy.types import (Panel, Operator)
import os
from bpy.props import StringProperty, BoolProperty
from bpy_extras.io_utils import ImportHelper
from bpy.utils import register_class, unregister_class

class OT_TestOpenFilebrowser(Operator, ImportHelper):

    bl_idname = "test.open_filebrowser"
    bl_label = "Open the file browser (yay)"
    
    filter_glob: StringProperty(
        default='*.blend',
        options={'HIDDEN'}
    )
    
    some_boolean: BoolProperty(
        name='Delete old mesh',
        description='delete the existing part',
        default=True,
    )

    def execute(self, context):
        """Do something with the selected file(s)."""

        selectedObjects = bpy.context.selected_objects

        for obj in selectedObjects:
            file_path = self.filepath
            inner_path = 'Object'
            object_name = obj.name
            obj.name = (obj.name + '_old')
                
            bpy.ops.wm.append(
                filepath=os.path.join(file_path, inner_path, object_name),
                directory=os.path.join(file_path, inner_path),
                filename=object_name
                )

    
            if self.some_boolean:
                bpy.data.objects[object_name].select_set(True)
                bpy.context.view_layer.objects.active = obj
                bpy.ops.object.make_links_data(type='MATERIAL')
                
                bpy.data.objects[obj.name].select_set(True)
                bpy.context.view_layer.objects.active = bpy.data.objects[object_name]
                bpy.ops.object.make_links_data(type='OBDATA')
                
                bpy.data.objects.remove(bpy.data.objects[object_name], do_unlink=True)
                obj.name = object_name
                bpy.context.view_layer.objects.active = obj
                
        return {'FINISHED'}


def registerFileBrowser():
    bpy.utils.register_class(OT_TestOpenFilebrowser)


def unregisterFileBrowser():
    bpy.utils.unregister_class(OT_TestOpenFilebrowser)


registerFileBrowser()
OT_TestOpenFilebrowser('INVOKE_DEFAULT')