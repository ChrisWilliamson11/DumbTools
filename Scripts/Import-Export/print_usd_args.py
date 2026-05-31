import bpy
print("USD_EXPORT_ARGS_START")
for p in bpy.ops.wm.usd_export.get_rna_type().properties.keys():
    print(p)
print("USD_EXPORT_ARGS_END")
print("USD_IMPORT_ARGS_START")
for p in bpy.ops.wm.usd_import.get_rna_type().properties.keys():
    print(p)
print("USD_IMPORT_ARGS_END")
