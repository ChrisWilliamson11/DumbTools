import re

path = r'g:\DumbTools_Public\DumbTools\Scripts\Rigging\Retarget Multiple FBX.py'
with open(path, 'r', encoding='utf-8') as f:
    content = f.read()

# Don't replace if already log_print
content = re.sub(r'\b(?<!log_)print\(', 'log_print(', content)

# Check if log_print is already defined
if 'def log_print(' not in content:
    log_func = """
def log_print(*args, **kwargs):
    msg = " ".join(map(str, args))
    # Standard console print
    import builtins
    builtins.print(msg, **kwargs)
    try:
        import bpy
        props = bpy.context.scene.retarget_fbx_props
        if props.do_write_log and props.log_filepath:
            with open(props.log_filepath, "a", encoding="utf-8") as f:
                f.write(msg + "\\n")
    except Exception:
        pass

"""
    imports_end = content.find('def _is_retarget_constraint')
    if imports_end != -1:
        content = content[:imports_end] + log_func + content[imports_end:]

with open(path, 'w', encoding='utf-8') as f:
    f.write(content)
