# Tooltip:  This will import a CSV file and create a text object with the data in column 1
import bpy
import csv
from bpy_extras.io_utils import ImportHelper
from bpy.props import StringProperty, IntProperty, FloatProperty, EnumProperty

class IMPORT_CSV_OT_ShowPopup(bpy.types.Operator, ImportHelper):
    bl_idname = "import_csv.show_popup"
    bl_label = "Import CSV"

    # Define properties
    filename_ext = ".csv"
    filter_glob: StringProperty(
        default="*.csv",
        options={'HIDDEN'}
    )
    rows_per_object: IntProperty(name="Rows Per Object", default=100, min=1)
    start_row: IntProperty(name="Start Row", default=1, min=1)
    end_row: IntProperty(name="End Row", default=100, min=1)
    offset: IntProperty(name="Offset", default=-100)
    horizontal_padding: FloatProperty(name="Horizontal Padding", default=10.0, min=0.0)

    # Text properties
    text_size: FloatProperty(name="Text Size", default=1.0, min=0.1)
    line_spacing: FloatProperty(name="Line Spacing", default=1.0, min=0.1)
    align_x: EnumProperty(
        name="Align X",
        items=[('LEFT', "Left", ""), ('CENTER', "Center", ""), ('RIGHT', "Right", "")],
        default='LEFT'
    )
    align_y: EnumProperty(
        name="Align Y",
        items=[('TOP', "Top", ""), ('CENTER', "Center", ""), ('BOTTOM', "Bottom", "")],
        default='CENTER'
    )

    def execute(self, context):
        csv_file = self.filepath
        if not csv_file:
            self.report({'ERROR'}, "No file selected.")
            return {'CANCELLED'}

        start_idx = self.start_row - 1
        end_idx = self.end_row

        try:
            with open(csv_file, 'r') as file:
                reader = csv.reader(file)
                rows = list(reader)

            if not rows:
                self.report({'ERROR'}, "CSV file is empty.")
                return {'CANCELLED'}

            num_columns = len(rows[0])
            column_offsets = [i * self.horizontal_padding for i in range(num_columns)]

            for col in range(num_columns):
                formatted_rows = [row[col] for row in rows[start_idx:end_idx] if len(row) > col]
                num_objects = len(formatted_rows) // self.rows_per_object + 1

                parent_obj = None
                text_object_name_prefix = f"CSV_Text_Col_{col}_"

                for i in range(num_objects):
                    rows_subset = formatted_rows[i * self.rows_per_object : (i + 1) * self.rows_per_object]

                    bpy.ops.object.text_add()
                    text_obj = bpy.context.object
                    text_obj.name = text_object_name_prefix + str(i + 1)

                    text_data = text_obj.data
                    text_data.body = '\n'.join(rows_subset)
                    text_data.align_x = self.align_x
                    text_data.align_y = self.align_y
                    text_data.size = self.text_size
                    text_data.space_line = self.line_spacing

                    if parent_obj:
                        text_obj.parent = parent_obj

                    text_obj.location.y = self.offset
                    text_obj.location.x = column_offsets[col]

                    parent_obj = text_obj

            return {'FINISHED'}
        except Exception as e:
            self.report({'ERROR'}, str(e))
            return {'CANCELLED'}

    def draw(self, context):
        layout = self.layout
        layout.prop(self, "rows_per_object")
        layout.prop(self, "start_row")
        layout.prop(self, "end_row")
        layout.prop(self, "offset")
        layout.prop(self, "horizontal_padding")
        layout.prop(self, "text_size")
        layout.prop(self, "line_spacing")
        layout.prop(self, "align_x")
        layout.prop(self, "align_y")

def register():
    if "IMPORT_CSV_OT_ShowPopup" not in bpy.types.Operator.__subclasses__():
        bpy.utils.register_class(IMPORT_CSV_OT_ShowPopup)
    else:
        print("IMPORT_CSV_OT_ShowPopup is already registered")


def unregister():
    if "IMPORT_CSV_OT_ShowPopup" in bpy.types.Operator.__subclasses__():
        bpy.utils.unregister_class(IMPORT_CSV_OT_ShowPopup)


register()


bpy.ops.import_csv.show_popup('INVOKE_DEFAULT')