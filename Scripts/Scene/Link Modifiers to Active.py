# Tooltip: Link all modifier properties on selected objects to the active object's matching modifiers via drivers

import bpy
from collections import defaultdict


def get_driveable_properties(modifier):
    """
    Yield (prop_name, is_array, array_length) for each property on the
    modifier that can meaningfully be driven.

    Skips:
      - read-only properties
      - the 'type' identifier and internal props (rna_type, name, etc.)
      - pointer / collection / string properties (can't be driven)

    NOTE: Do NOT use this for Geometry Nodes (NODES) modifiers — their
    user-facing inputs are custom properties accessed via bracket notation,
    not RNA properties. Use get_driveable_geonodes_inputs() instead.
    """
    SKIP_PROPS = {
        'rna_type', 'name', 'type', 'show_viewport', 'show_render',
        'show_in_editmode', 'show_on_cage', 'show_expanded',
        'is_active', 'is_override_data',
        'show_group_colors', 'execution_domain',
    }

    for prop in modifier.bl_rna.properties:
        if prop.identifier in SKIP_PROPS:
            continue
        if prop.is_readonly:
            continue
        # Only drive numeric, boolean, and enum properties
        if prop.type in ('FLOAT', 'INT', 'BOOLEAN', 'ENUM'):
            if hasattr(prop, 'is_array') and prop.is_array:
                yield (prop.identifier, True, prop.array_length)
            else:
                yield (prop.identifier, False, 0)


def get_driveable_geonodes_inputs(modifier):
    """
    For Geometry Nodes (NODES type) modifiers, yield
    (identifier, is_array, array_length) for each input socket in the
    node group that can be driven.

    Node group inputs are NOT regular RNA properties — they are exposed as
    custom properties on the modifier and must be accessed / driven via
    bracket notation:  modifier["Socket_0"],  modifier["Socket_0"][1], etc.

    Supports both Blender 4.x (node_group.interface.items_tree) and
    Blender 3.x (node_group.inputs).
    """
    if modifier.type != 'NODES' or not modifier.node_group:
        return

    # These socket types hold IDs / geometry / strings — cannot be driven
    NON_DRIVEABLE = {
        'NodeSocketGeometry', 'NodeSocketString', 'NodeSocketCollection',
        'NodeSocketObject', 'NodeSocketMaterial', 'NodeSocketTexture',
        'NodeSocketImage', 'NodeSocketShader', 'NodeSocketVirtual',
        'NodeSocketMatrix',
        # Blender 3.x type-name variants
        'GEOMETRY', 'STRING', 'COLLECTION', 'OBJECT',
        'MATERIAL', 'TEXTURE', 'IMAGE', 'SHADER',
    }

    node_group = modifier.node_group
    input_items = []

    if hasattr(node_group, 'interface'):
        # Blender 4.x
        for item in node_group.interface.items_tree:
            if (getattr(item, 'item_type', None) == 'SOCKET'
                    and getattr(item, 'in_out', None) == 'INPUT'):
                input_items.append(item)
    elif hasattr(node_group, 'inputs'):
        # Blender 3.x
        input_items = list(node_group.inputs)

    for item in input_items:
        socket_type = getattr(item, 'socket_type', getattr(item, 'type', ''))
        if socket_type in NON_DRIVEABLE:
            continue

        identifier = item.identifier

        # Confirm the modifier actually stores this input as an accessible value
        try:
            value = modifier[identifier]
        except (KeyError, TypeError):
            continue

        # Determine array-ness from the live value (handles Vector, Color, etc.)
        if hasattr(value, '__len__'):
            try:
                yield (identifier, True, len(value))
                continue
            except TypeError:
                pass
        yield (identifier, False, 0)


def build_type_ordered_map(obj):
    """
    Build a dict: modifier_type -> [modifier, ...] preserving stack order.
    """
    result = defaultdict(list)
    for mod in obj.modifiers:
        result[mod.type].append(mod)
    return result


def add_property_driver(target_obj, target_mod, source_obj, source_mod,
                        prop_name, array_index=-1, bracket_notation=False):
    """
    Add a single-variable AVERAGE driver on target_mod.prop_name
    that reads from source_mod.prop_name on source_obj.

    bracket_notation=True  → uses  modifiers["Name"]["prop"]  (Geometry Nodes inputs)
    bracket_notation=False → uses  modifiers["Name"].prop      (standard RNA props)

    Returns True on success, False on failure.
    """
    if bracket_notation:
        data_path_target = f'modifiers["{target_mod.name}"]["{prop_name}"]'
        data_path_source = f'modifiers["{source_mod.name}"]["{prop_name}"]'
    else:
        data_path_target = f'modifiers["{target_mod.name}"].{prop_name}'
        data_path_source = f'modifiers["{source_mod.name}"].{prop_name}'

    # Remove any existing driver first
    try:
        if array_index >= 0:
            target_obj.driver_remove(data_path_target, array_index)
        else:
            target_obj.driver_remove(data_path_target)
    except Exception:
        pass

    # Add the driver
    try:
        if array_index >= 0:
            fcurve = target_obj.driver_add(data_path_target, array_index)
        else:
            fcurve = target_obj.driver_add(data_path_target)
    except Exception:
        return False

    # Handle driver_add returning a list (shouldn't happen with explicit index,
    # but defensive)
    if isinstance(fcurve, list):
        for fc in fcurve:
            _configure_driver(fc, source_obj, data_path_source, fc.array_index)
        return True

    _configure_driver(fcurve, source_obj, data_path_source, array_index)
    return True


def _configure_driver(fcurve, source_obj, data_path_source, array_index):
    """Configure a single FCurve's driver to read from the source."""
    driver = fcurve.driver
    driver.type = 'AVERAGE'

    # Clear existing variables
    while driver.variables:
        driver.variables.remove(driver.variables[0])

    var = driver.variables.new()
    var.name = 'var'
    var.type = 'SINGLE_PROP'

    target = var.targets[0]
    target.id_type = 'OBJECT'
    target.id = source_obj
    if array_index >= 0:
        target.data_path = f'{data_path_source}[{array_index}]'
    else:
        target.data_path = data_path_source


def link_modifiers(active_obj, selected_objs):
    """
    Main logic: match modifiers between active and each selected object,
    then create drivers for every driveable property.

    Returns (total_drivers_created, total_modifiers_linked, skipped_props).
    """
    active_type_map = build_type_ordered_map(active_obj)

    total_drivers = 0
    total_mods_linked = 0
    skipped_props = []

    for obj in selected_objs:
        if obj == active_obj:
            continue

        target_type_map = build_type_ordered_map(obj)

        for mod_type, active_mods in active_type_map.items():
            if mod_type not in target_type_map:
                continue

            target_mods = target_type_map[mod_type]
            # Pair in order: 1st↔1st, 2nd↔2nd, etc.
            pairs = zip(active_mods, target_mods)

            for source_mod, target_mod in pairs:
                mod_drivers = 0

                # Geometry Nodes exposes its inputs as custom properties
                # (bracket notation), not as RNA properties (dot notation).
                if mod_type == 'NODES':
                    props = get_driveable_geonodes_inputs(source_mod)
                    bracket = True
                else:
                    props = get_driveable_properties(source_mod)
                    bracket = False

                for prop_name, is_array, array_length in props:
                    # Verify the target modifier also exposes this property
                    if bracket:
                        try:
                            _ = target_mod[prop_name]
                        except (KeyError, TypeError):
                            continue
                    else:
                        if not hasattr(target_mod, prop_name):
                            continue

                    if is_array:
                        for idx in range(array_length):
                            ok = add_property_driver(
                                obj, target_mod,
                                active_obj, source_mod,
                                prop_name, array_index=idx,
                                bracket_notation=bracket,
                            )
                            if ok:
                                mod_drivers += 1
                            else:
                                skipped_props.append(
                                    f"{obj.name} → {target_mod.name}"
                                    f'["{prop_name}"][{idx}]'
                                )
                    else:
                        ok = add_property_driver(
                            obj, target_mod,
                            active_obj, source_mod,
                            prop_name,
                            bracket_notation=bracket,
                        )
                        if ok:
                            mod_drivers += 1
                        else:
                            skipped_props.append(
                                f"{obj.name} → {target_mod.name}"
                                f'["{prop_name}"]' if bracket
                                else f"{obj.name} → {target_mod.name}.{prop_name}"
                            )

                if mod_drivers > 0:
                    total_mods_linked += 1
                    total_drivers += mod_drivers
                    print(f"  Linked {source_mod.name} ({active_obj.name}) → "
                          f"{target_mod.name} ({obj.name}): {mod_drivers} drivers")

    return total_drivers, total_mods_linked, skipped_props


# ── Main ─────────────────────────────────────────────────────────────────────

active = bpy.context.active_object
selected = [obj for obj in bpy.context.selected_objects if obj != active]

if not active:
    raise RuntimeError("No active object.")
if not selected:
    raise RuntimeError("No other selected objects.")
if not active.modifiers:
    raise RuntimeError(f"Active object '{active.name}' has no modifiers.")

print(f"\n{'='*60}")
print(f"Linking modifiers from active '{active.name}' to {len(selected)} object(s)")
print(f"Active modifiers: {[m.name for m in active.modifiers]}")
print(f"{'='*60}")

drivers_created, mods_linked, skipped = link_modifiers(active, selected)

print(f"\n{'='*60}")
print(f"Done. Created {drivers_created} drivers across {mods_linked} modifier pairs.")
if skipped:
    print(f"Skipped {len(skipped)} properties that couldn't be driven:")
    for s in skipped:
        print(f"  - {s}")
print(f"{'='*60}\n")
