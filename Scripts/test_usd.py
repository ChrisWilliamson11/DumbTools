import bpy

try:
    print("USD PROPERTIES:")
    for prop in dir(bpy.ops.wm.usd_export.get_rna_type().properties):
        if not prop.startswith("_"):
            print("PROP:", prop)
except Exception as e:
    print("Error:", e)
