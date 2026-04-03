# Tooltip: Export selected Text objects to SVG (maps Blender X->SVG x, Z->SVG y)
import bpy, os, html
from bpy.types import Operator
from bpy_extras.io_utils import ExportHelper
from bpy.props import StringProperty, FloatProperty, IntProperty


def _esc_text(s: str) -> str:
    return html.escape(s or "", quote=False).replace("\r\n", "\n").replace("\r", "\n")


def _esc_attr(s: str) -> str:
    return html.escape(s or "", quote=True)


def _font_name(tdat) -> str:
    f = getattr(tdat, "font", None)
    if f and getattr(f, "filepath", ""):
        return os.path.splitext(os.path.basename(f.filepath))[0]
    if f and getattr(f, "name", ""):
        return f.name
    return "sans-serif"


class EXPORT_OT_selected_text_to_svg(Operator, ExportHelper):
    bl_idname = "export.selected_text_to_svg"
    bl_label = "Export Selected Text to SVG"
    bl_options = {"REGISTER"}

    filename_ext = ".svg"
    filter_glob: StringProperty(default="*.svg", options={"HIDDEN"})

    pixels_per_unit: FloatProperty(
        name="Pixels per Blender Unit", description="Scale world units to SVG px",
        default=100.0, min=1.0, soft_max=1000.0,
    )
    padding_px: IntProperty(
        name="Canvas Padding (px)", default=20, min=0, soft_max=400,
    )

    def execute(self, context):
        objs = [o for o in context.selected_objects or [] if o.type == 'FONT']
        if not objs:
            self.report({'WARNING'}, "Select one or more Text objects")
            return {'CANCELLED'}

        # World-space X/Z extents
        xs = [o.matrix_world.translation.x for o in objs]
        zs = [o.matrix_world.translation.z for o in objs]
        minx, maxx = min(xs), max(xs)
        minz, maxz = min(zs), max(zs)
        scale = float(self.pixels_per_unit)
        pad = int(self.padding_px)
        w = int(round(max(1.0, (maxx - minx) * scale) + 2 * pad))
        h = int(round(max(1.0, (maxz - minz) * scale) + 2 * pad))

        lines = [
            "<?xml version=\"1.0\" encoding=\"UTF-8\"?>",
            f"<svg xmlns=\"http://www.w3.org/2000/svg\" width=\"{w}\" height=\"{h}\" viewBox=\"0 0 {w} {h}\">",
        ]

        # Sort by name for determinism
        for o in sorted(objs, key=lambda x: x.name):
            tdat = o.data
            pos = o.matrix_world.translation
            x_px = pad + (pos.x - minx) * scale
            y_px = pad + (maxz - pos.z) * scale  # flip so SVG y grows downward
            # Approx font size in px (size in BU scaled by object XY scale)
            size_px = max(1.0, tdat.size * (o.scale.x + o.scale.y) * 0.5 * scale)
            fam = _font_name(tdat)
            text_body = _esc_text(getattr(tdat, 'body', ''))
            lines.append(
                f"  <text x=\"{x_px:.2f}\" y=\"{y_px:.2f}\" font-family=\"{_esc_attr(fam)}\" "
                f"font-size=\"{size_px:.2f}\" fill=\"black\" xml:space=\"preserve\" style=\"white-space:pre\">{text_body}</text>"
            )

        lines.append("</svg>")

        try:
            with open(self.filepath, "w", encoding="utf-8") as f:
                f.write("\n".join(lines))
        except Exception as e:
            self.report({'ERROR'}, f"Failed to write SVG: {e}")
            return {'CANCELLED'}

        self.report({'INFO'}, f"Exported {len(objs)} text object(s) to SVG: {os.path.basename(self.filepath)}")
        return {'FINISHED'}


def menu_func_export(self, context):
    self.layout.operator(EXPORT_OT_selected_text_to_svg.bl_idname, text="Selected Text to SVG (.svg)")


def register():
    bpy.utils.register_class(EXPORT_OT_selected_text_to_svg)
    bpy.types.TOPBAR_MT_file_export.append(menu_func_export)


def unregister():
    bpy.types.TOPBAR_MT_file_export.remove(menu_func_export)
    bpy.utils.unregister_class(EXPORT_OT_selected_text_to_svg)



register()
# Launch file browser immediately when run from Text Editor/DumbTools
try:
    bpy.ops.export.selected_text_to_svg('INVOKE_DEFAULT')
except Exception:
    pass
