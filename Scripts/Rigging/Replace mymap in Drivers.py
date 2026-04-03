import bpy
import re

"""
Replace mymap(...) calls in driver expressions with pure expressions.

mymap(x, x_s, x_e, k, b) semantics (from legacy script):
- Clamp x to [-1, 1]
- If x in [x_s, x_e], return k*x + b
- Otherwise return 0.0

We rewrite:
    mymap(X, XS, XE, K, B)
into:
    ((K)*CL + (B)) if (CL >= (XS) and CL <= (XE)) else 0.0
where CL = min(1.0, max(-1.0, (X)))

This removes the dependency on a custom driver function so drivers can
evaluate without registering Python into the driver namespace.
"""

# Preview without writing changes
DRY_RUN = False


# Scope controls
# - By default, operate only on shape key drivers of selected mesh objects
ONLY_SELECTED = True
ONLY_SHAPE_KEYS = True

# Lower-level scanning toggles (leave as-is unless you need broader scanning)
SCAN_OBJECTS = True
SCAN_SHAPE_KEYS = True
SCAN_MATERIALS = False
SCAN_NODE_GROUPS = False
SCAN_SCENES = False
SCAN_WORLDS = False


def _split_args_preserving_parens(s: str):
    """
    Split a function argument string on commas while preserving nested parentheses.
    Returns a list of raw argument strings (not stripped).
    """
    args = []
    level = 0
    current = []
    i = 0
    while i < len(s):
        ch = s[i]
        if ch == "(":
            level += 1
            current.append(ch)
        elif ch == ")":
            level = max(0, level - 1)
            current.append(ch)
        elif ch == "," and level == 0:
            args.append("".join(current))
            current = []
        else:
            current.append(ch)
        i += 1
    if current:
        args.append("".join(current))
    return args


def _find_mymap_calls(expr: str):
    """
    Generator yielding tuples (start_idx, end_idx_exclusive, args_list)
    for each mymap(...) occurrence in expr. args_list has raw strings.
    """
    i = 0
    needle = "mymap("
    L = len(expr)
    while i < L:
        j = expr.find(needle, i)
        if j == -1:
            break
        # Locate matching closing parenthesis
        k = j + len(needle)  # position after '('
        depth = 1
        while k < L and depth > 0:
            if expr[k] == "(":
                depth += 1
            elif expr[k] == ")":
                depth -= 1
            k += 1
        if depth != 0:
            # Unbalanced; bail out of this occurrence
            i = j + len("mymap")
            continue
        # args portion is between j+len(needle) and k-1
        args_str = expr[j + len(needle) : k - 1]
        args = _split_args_preserving_parens(args_str)
        yield (j, k, args)
        i = k


def _rewrite_single_mymap_call(args_raw):
    """
    Given a list of 5 raw args for mymap, return a pure expression string
    implementing the same logic. If not compatible, return None.
    """
    if len(args_raw) != 5:
        return None

    # Keep tokens as-is, but wrap in parentheses where sensible
    x_raw = args_raw[0].strip()
    x_s_raw = args_raw[1].strip()
    x_e_raw = args_raw[2].strip()
    k_raw = args_raw[3].strip()
    b_raw = args_raw[4].strip()

    # Build clamp subexpression
    # Use explicit 1.0/-1.0 to avoid int-only context
    clamp_x = f"min(1.0, max(-1.0, ({x_raw})))"

    # Build final replacement with parentheses to ensure precedence
    # ((K)*CL + (B)) if (CL >= (XS) and CL <= (XE)) else 0.0
    repl = (
        f"(({k_raw})*{clamp_x}+({b_raw})) "
        f"if ({clamp_x}>=({x_s_raw}) and {clamp_x}<=({x_e_raw})) else 0.0"
    )
    return repl


def rewrite_mymap_expression(expr: str):
    """
    Rewrite all mymap(...) calls in an expression string.
    Returns (new_expr, replaced_count).
    """
    if "mymap(" not in expr:
        return expr, 0

    # We replace from left to right, carefully tracking shifting indexes
    out = []
    last = 0
    replaced = 0
    for start, end, args in _find_mymap_calls(expr):
        # Append any text before this call
        out.append(expr[last:start])

        repl = _rewrite_single_mymap_call(args)
        if repl is None:
            # Could not parse; keep original mymap(...) text
            out.append(expr[start:end])
        else:
            out.append(f"({repl})")
            replaced += 1

        last = end

    # Append any trailing text
    out.append(expr[last:])
    new_expr = "".join(out)
    return new_expr, replaced


def _iter_id_blocks_with_drivers():
    """
    Iterate ID blocks that might have animation_data.drivers.
    Yields (idblock, fcu) for each driver FCurve.
    """
    # Objects and their data/shape_keys
    if SCAN_OBJECTS:
        for ob in bpy.data.objects:
            ad = getattr(ob, "animation_data", None)
            if ad and getattr(ad, "drivers", None):
                for fcu in ad.drivers:
                    yield ob, fcu
            # Object data (Mesh, Camera, Light, Armature, etc.)
            data_id = getattr(ob, "data", None)
            if data_id:
                ad = getattr(data_id, "animation_data", None)
                if ad and getattr(ad, "drivers", None):
                    for fcu in ad.drivers:
                        yield data_id, fcu
            # Shape keys live on a distinct datablock
            shape_keys = getattr(getattr(ob, "data", None), "shape_keys", None)
            if shape_keys and SCAN_SHAPE_KEYS:
                ad = getattr(shape_keys, "animation_data", None)
                if ad and getattr(ad, "drivers", None):
                    for fcu in ad.drivers:
                        yield shape_keys, fcu

    if SCAN_SHAPE_KEYS:
        for sk in bpy.data.shape_keys:
            ad = getattr(sk, "animation_data", None)
            if ad and getattr(ad, "drivers", None):
                for fcu in ad.drivers:
                    yield sk, fcu

    if SCAN_MATERIALS:
        for mat in bpy.data.materials:
            ad = getattr(mat, "animation_data", None)
            if ad and getattr(ad, "drivers", None):
                for fcu in ad.drivers:
                    yield mat, fcu
            nt = getattr(mat, "node_tree", None)
            if nt:
                ad = getattr(nt, "animation_data", None)
                if ad and getattr(ad, "drivers", None):
                    for fcu in ad.drivers:
                        yield nt, fcu

    if SCAN_NODE_GROUPS:
        for nt in bpy.data.node_groups:
            ad = getattr(nt, "animation_data", None)
            if ad and getattr(ad, "drivers", None):
                for fcu in ad.drivers:
                    yield nt, fcu

    if SCAN_SCENES:
        for sc in bpy.data.scenes:
            ad = getattr(sc, "animation_data", None)
            if ad and getattr(ad, "drivers", None):
                for fcu in ad.drivers:
                    yield sc, fcu

    if SCAN_WORLDS:
        for wd in bpy.data.worlds:
            ad = getattr(wd, "animation_data", None)
            if ad and getattr(ad, "drivers", None):
                for fcu in ad.drivers:
                    yield wd, fcu


def replace_mymap_in_drivers():
    """
    Scan driver expressions across common ID blocks and replace mymap(...) calls.
    """
    total_fc = 0
    changed_fc = 0
    total_replacements = 0
    changes = []

    # Build selected shape key set if limiting to selected meshes
    selected_keys = set()
    if ONLY_SELECTED:
        for _ob in bpy.context.selected_objects or []:
            if getattr(_ob, "type", None) == "MESH":
                _sk = getattr(getattr(_ob, "data", None), "shape_keys", None)
                if _sk:
                    selected_keys.add(_sk)

    for idb, fcu in _iter_id_blocks_with_drivers():
        # Limit to shape key drivers if requested
        if ONLY_SHAPE_KEYS and not hasattr(idb, "key_blocks"):
            continue
        # Limit to selected objects' shape key datablocks if requested
        if ONLY_SELECTED and selected_keys and idb not in selected_keys:
            continue

        drv = getattr(fcu, "driver", None)

        if not drv:
            continue
        expr = getattr(drv, "expression", "")
        if not expr or "mymap(" not in expr:
            continue

        new_expr, n = rewrite_mymap_expression(expr)
        total_fc += 1

        if n > 0 and new_expr != expr:
            changes.append(
                (
                    idb,
                    fcu.data_path,
                    getattr(fcu, "array_index", -1),
                    expr,
                    new_expr,
                    n,
                )
            )
            changed_fc += 1
            total_replacements += n

    # Apply changes
    if not DRY_RUN:
        for idb, dp, idx, old, new, n in changes:
            # Re-find the fcurve to avoid dangling references
            ad = getattr(idb, "animation_data", None)
            if not ad:
                continue
            for fcu in ad.drivers:
                if fcu.data_path == dp and getattr(fcu, "array_index", -1) == idx:
                    fcu.driver.expression = new
                    break

    # Reporting
    print("[mymap->expr] Driver scan complete")
    print(f"[mymap->expr] Drivers with mymap found: {total_fc}")
    print(f"[mymap->expr] Drivers changed: {changed_fc}")
    print(f"[mymap->expr] mymap() calls replaced: {total_replacements}")
    if DRY_RUN:
        print("[mymap->expr] DRY_RUN=True (no changes written)")
    # Show a sample of changes
    for i, (_, dp, idx, old, new, n) in enumerate(changes[:20]):
        print("-----")
        print(f"[mymap->expr] {dp}[{idx}] replacements: {n}")
        print(f"FROM: {old}")
        print(f"TO  : {new}")
    if len(changes) > 20:
        print(f"[mymap->expr] ... and {len(changes) - 20} more changes.")


replace_mymap_in_drivers()
