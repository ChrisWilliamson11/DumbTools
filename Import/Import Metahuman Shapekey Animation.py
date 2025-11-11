bl_info = {
    "name": "Import Shapekeys from ASCII FBX (CTRL Tracks)",
    "author": "Assistant",
    "version": (1, 3, 0),
    "blender": (3, 0, 0),
    "location": "File > Import > Import Shapekeys from ASCII FBX",
    "description": "Parses ASCII FBX text to import CTRL_* shapekey animation as an Action on the selected mesh",
    "warning": "ASCII FBX only",
    "category": "Import-Export",
}

import os
import re
import statistics

import bpy
from bpy.props import BoolProperty, FloatProperty, IntProperty, StringProperty
from bpy_extras.io_utils import ImportHelper

# FBX time is in 1/46186158000 sec ticks
FBX_TICKS_PER_SECOND = 46186158000.0

# AnimationCurveNode header (captures node id and label)
RE_ANIM_CURVE_NODE_HEADER = re.compile(
    r'^\s*AnimationCurveNode:\s*(\d+),\s*"AnimCurveNode::([^"]+)"'
)
# AnimationCurve header (captures curve id)
RE_ANIM_CURVE_HEADER = re.compile(r'^\s*AnimationCurve:\s*(\d+),\s*"AnimCurve::"')

# Connection mapping curve -> node with property name d|<prop>
# C: "OP", <curve_id>, <node_id>, "d|CTRL_expressions_browDownL"
RE_CONNECTION_OP = re.compile(r'^\s*C:\s*"OP",\s*(\d+),\s*(\d+),\s*"d\|([^"]+)"')

# Property on AnimCurveNode: P: "d|<prop_name>"
RE_PROP_D_NAME = re.compile(r'^\s*P:\s*"d\|([^"]+)"')

# Starts for KeyTime/KeyValue blocks (support both inline and *N { a: ... } )
RE_KEYTIME_START = re.compile(r"^\s*KeyTime\s*:")
RE_KEYVALUE_START = re.compile(r"^\s*KeyValueFloat\s*:")

# Number tokenizers (robust to commas/spaces, with optional exponent)
RE_INT = re.compile(r"[-+]?\d+")
RE_FLOAT = re.compile(r"[-+]?(?:\d+\.\d*|\d*\.\d+|\d+)(?:[eE][-+]?\d+)?")


def parse_csv_numbers_inline(s, as_int=False):
    """Extract a list of numbers from a line (commas/spaces optional)."""
    if as_int:
        return [int(x) for x in RE_INT.findall(s)]
    return [float(x) for x in RE_FLOAT.findall(s)]


class ASCII_FBX_Shapekey_Parser:
    """
    Lightweight ASCII FBX parser for:
      - AnimationCurveNode blocks (to get property names P: "d|<prop>")
      - AnimationCurve blocks (KeyTime / KeyValueFloat arrays)
      - Connection lines C: "OP", curve_id, node_id, "d|<prop>"
    """

    def __init__(self):
        # node_id -> property_name (from P: "d|<prop>")
        self.nodes = {}
        # curve_id -> {"times":[...], "values":[...]}
        self.curves = {}
        # curve_id -> (node_id, "d|<prop>")
        self.connections = {}

    def parse(self, filepath):
        in_node = False
        in_curve = False
        current_node_id = None
        current_curve_id = None

        # For multi-line array collection
        collecting_times = False
        collecting_values = False
        current_curve_times = None
        current_curve_values = None

        with open(filepath, "r", encoding="utf-8", errors="ignore") as f:
            for raw_line in f:
                line = raw_line.rstrip("\r\n")

                # Connection mapping: curve -> (node, d|prop)
                m_conn = RE_CONNECTION_OP.match(line)
                if m_conn:
                    curve_id = int(m_conn.group(1))
                    node_id = int(m_conn.group(2))
                    prop_name = m_conn.group(3)
                    self.connections[curve_id] = (node_id, prop_name)

                # AnimCurveNode header
                if not in_node and not in_curve:
                    m_node = RE_ANIM_CURVE_NODE_HEADER.match(line)
                    if m_node:
                        in_node = True
                        current_node_id = int(m_node.group(1))
                        continue

                # AnimCurve header
                if not in_curve and not in_node:
                    m_curve = RE_ANIM_CURVE_HEADER.match(line)
                    if m_curve:
                        in_curve = True
                        current_curve_id = int(m_curve.group(1))
                        current_curve_times = []
                        current_curve_values = []
                        collecting_times = False
                        collecting_values = False
                        continue

                # Inside AnimationCurveNode: capture property name
                if in_node:
                    m_prop = RE_PROP_D_NAME.match(line)
                    if m_prop:
                        self.nodes[current_node_id] = m_prop.group(1)
                    if line.strip() == "}":
                        in_node = False
                        current_node_id = None
                        continue

                # Inside AnimationCurve: capture KeyTime / KeyValueFloat
                if in_curve:
                    # Start or inline KeyTime
                    if RE_KEYTIME_START.match(line):
                        if "{" not in line:
                            current_curve_times.extend(
                                parse_csv_numbers_inline(line, as_int=True)
                            )
                        else:
                            if "a:" in line:
                                part = line.split("a:", 1)[1]
                                current_curve_times.extend(
                                    parse_csv_numbers_inline(part, as_int=True)
                                )
                            collecting_times = True
                        if "}" in line:
                            collecting_times = False
                        continue

                    # Continue KeyTime block
                    if collecting_times:
                        part = line
                        if "a:" in part:
                            part = part.split("a:", 1)[1]
                        current_curve_times.extend(
                            parse_csv_numbers_inline(part, as_int=True)
                        )
                        if "}" in line:
                            collecting_times = False
                        continue

                    # Start or inline KeyValueFloat
                    if RE_KEYVALUE_START.match(line):
                        if "{" not in line:
                            current_curve_values.extend(
                                parse_csv_numbers_inline(line, as_int=False)
                            )
                        else:
                            if "a:" in line:
                                part = line.split("a:", 1)[1]
                                current_curve_values.extend(
                                    parse_csv_numbers_inline(part, as_int=False)
                                )
                            collecting_values = True
                        if "}" in line:
                            collecting_values = False
                        continue

                    # Continue KeyValueFloat block
                    if collecting_values:
                        part = line
                        if "a:" in part:
                            part = part.split("a:", 1)[1]
                        current_curve_values.extend(
                            parse_csv_numbers_inline(part, as_int=False)
                        )
                        if "}" in line:
                            collecting_values = False
                        continue

                    # End of AnimCurve block
                    if line.strip() == "}":
                        n = min(
                            len(current_curve_times or []),
                            len(current_curve_values or []),
                        )
                        self.curves[current_curve_id] = {
                            "times": (current_curve_times or [])[:n],
                            "values": (current_curve_values or [])[:n],
                        }
                        in_curve = False
                        current_curve_id = None
                        current_curve_times = None
                        current_curve_values = None
                        collecting_times = False
                        collecting_values = False
                        continue

        # Build mapping: property_name -> list(curve_ids)
        property_to_curves = {}
        for curve_id, (node_id, prop_from_conn) in self.connections.items():
            prop_name = self.nodes.get(node_id) or prop_from_conn
            if not prop_name:
                continue
            if not prop_name.startswith("CTRL"):
                continue
            if curve_id not in self.curves:
                continue
            property_to_curves.setdefault(prop_name, []).append(curve_id)

        return property_to_curves


def ensure_shape_key(obj, name):
    if obj.data.shape_keys is None:
        obj.shape_key_add(name="Basis", from_mix=False)
    key = obj.data.shape_keys.key_blocks.get(name)
    if key is None:
        key = obj.shape_key_add(name=name, from_mix=False)
    return key


def ensure_action_for_shape_keys(obj, action_name):
    key_data = obj.data.shape_keys
    if key_data is None:
        obj.shape_key_add(name="Basis", from_mix=False)
        key_data = obj.data.shape_keys

    if key_data.animation_data is None:
        key_data.animation_data_create()
    action = bpy.data.actions.get(action_name)
    if action is None:
        action = bpy.data.actions.new(action_name)
    # Keep the action saved with the file
    action.use_fake_user = True
    key_data.animation_data.action = action
    return action


def get_scene_fps(context):
    scene = context.scene
    return scene.render.fps / (scene.render.fps_base if scene.render.fps_base else 1.0)


def fbx_ticks_to_frame(tick, fps):
    return (float(tick) / FBX_TICKS_PER_SECOND) * fps


def remove_shapekey_value_drivers(obj, name_prefix=None):
    """
    Remove drivers that target key_blocks["<name>"].value on the object's shape key datablock.
    If name_prefix is provided, only remove drivers for shape keys whose name starts with that prefix.
    Returns the number of removed drivers.
    """
    key_data = obj.data.shape_keys
    if not key_data or not key_data.animation_data:
        return 0

    removed = 0
    fcurves = key_data.animation_data.drivers
    for fcu in list(fcurves):
        dp = fcu.data_path
        m = re.match(r'key_blocks\["([^"]+)"\]\.value', dp)
        if not m:
            continue
        sk_name = m.group(1)
        if name_prefix is None or sk_name.startswith(name_prefix):
            fcurves.remove(fcu)
            removed += 1
    return removed


def remove_existing_fcurves_for_datapath(action, data_path):
    """Remove existing FCurves in an action for a specific data_path."""
    if not action:
        return 0
    to_remove = [fcu for fcu in action.fcurves if fcu.data_path == data_path]
    for fcu in to_remove:
        action.fcurves.remove(fcu)
    return len(to_remove)


def insert_curve_on_shapekey(
    action,
    shapekey_name,
    frames,
    values,
    group_name="CTRL",
    clear_existing=True,
    interpolation="BEZIER",
    clamp_01=False,
    log_spikes=False,
    despike=False,
    median_window=5,
    spike_threshold=1.2,
    quantized=False,
    q_epsilon=0.0003,
    q_den=8192,
    q_min_abs=1.2,
):
    """Create an FCurve on key_blocks[shapekey].value and insert keys.

    - Optional median despike filter
    - Optional quantized (k/den) outlier replacement
    - Deduplicate frames (last value wins)
    - Sort frames ascending
    - Bulk add keyframe points, set interpolation and clamp handles if BEZIER
    """
    data_path = f'key_blocks["{shapekey_name}"].value'
    if clear_existing:
        remove_existing_fcurves_for_datapath(action, data_path)
    fc = action.fcurves.new(data_path=data_path, index=-1, action_group=group_name)

    # Optional despike using a sliding median (replace isolated outliers with neighborhood median)
    if despike and len(values) >= 3:
        w = (
            int(median_window)
            if int(median_window) % 2 == 1
            else max(3, int(median_window) + 1)
        )
        half = w // 2
        filtered_vals = []
        for i, v in enumerate(values):
            left = max(0, i - half)
            right = min(len(values), i + half + 1)
            neighborhood = values[left:i] + values[i + 1 : right]
            if neighborhood:
                med = statistics.median([float(x) for x in neighborhood])
                if abs(float(v) - float(med)) > float(spike_threshold):
                    v = med
            filtered_vals.append(v)
        values = filtered_vals

    # Optional quantized-outlier suppression snapped to k/den if near and large
    if quantized and len(values) > 0:
        processed_vals = []
        nvals = len(values)
        for i, v in enumerate(values):
            try:
                vf = float(v)
            except Exception:
                processed_vals.append(v)
                continue
            if abs(vf) > float(q_min_abs):
                k = round(vf * float(q_den))
                quant = k / float(q_den)
                if abs(vf - quant) <= float(q_epsilon):
                    # replace with neighbor median when available, else 0.0
                    neigh = []
                    if i > 0:
                        try:
                            neigh.append(float(values[i - 1]))
                        except Exception:
                            pass
                    if i + 1 < nvals:
                        try:
                            neigh.append(float(values[i + 1]))
                        except Exception:
                            pass
                    vf = statistics.median(neigh) if neigh else 0.0
            processed_vals.append(vf)
        values = processed_vals

    # Deduplicate and sort frames
    frame_map = {}
    for fr, val in zip(frames, values):
        try:
            fr_f = float(fr)
            val_f = float(val)
            if clamp_01:
                if val_f < 0.0:
                    val_f = 0.0
                elif val_f > 1.0:
                    val_f = 1.0
        except Exception:
            continue
        frame_map[fr_f] = val_f  # last value for duplicate frames

    sorted_frames = sorted(frame_map.keys())
    count = len(sorted_frames)

    # Optional spike logging (large jumps between consecutive keys)
    if log_spikes and count > 1:
        prev_f = sorted_frames[0]
        prev_v = frame_map[prev_f]
        for fr in sorted_frames[1:]:
            v = frame_map[fr]
            if abs(v - prev_v) > 0.25:
                print(
                    f"[CTRL Import] Spike on {shapekey_name}: frame {prev_f}->{fr} delta {v - prev_v:.3f}"
                )
            prev_v = v
            prev_f = fr

    if count > 0:
        kps = fc.keyframe_points
        kps.add(count)
        for i, fr in enumerate(sorted_frames):
            kp = kps[i]
            kp.co = (fr, frame_map[fr])
            kp.interpolation = interpolation
            if interpolation == "BEZIER":
                kp.handle_left_type = "AUTO_CLAMPED"
                kp.handle_right_type = "AUTO_CLAMPED"

    fc.update()
    return fc


def find_driver_source_for_shapekey(obj, shapekey_name):
    """

    For a given object's shapekey name, try to locate a driver that feeds

    key_blocks["<name>"].value and return (target_id, target_data_path, transform_type).

    - If the driver uses an object transform variable, transform_type will be non-None
      (e.g., 'LOC_Y', 'ROT_X', 'SCALE_Z') and data_path may be None.
    - Otherwise, data_path will be populated (e.g., 'pose.bones["CTRL_x"].location', or a property path)
    """
    key_data = getattr(obj.data, "shape_keys", None)

    if not key_data or not key_data.animation_data:
        return None

    data_path = f'key_blocks["{shapekey_name}"].value'

    for fcu in key_data.animation_data.drivers:
        if fcu.data_path != data_path:
            continue

        drv = fcu.driver

        if not drv or not drv.variables:
            continue

        for var in drv.variables:
            for t in var.targets:
                if not t or not t.id:
                    continue
                # Prefer transforms-style targets (object transform drivers)
                if getattr(var, "type", None) == "TRANSFORMS" and getattr(
                    t, "transform_type", None
                ):
                    return (t.id, None, t.transform_type)
                # Fallback to explicit property path targets
                dp = getattr(t, "data_path", None)

                if dp:
                    return (t.id, dp, None)
    return None


def ensure_action_for_id(id_block, action_name):
    """
    Ensure an Action exists and is assigned on the given ID datablock.
    Works for Object (including Armature objects for pose bone FCurves),
    NodeTree, etc.
    """
    if id_block.animation_data is None:
        id_block.animation_data_create()
    action = bpy.data.actions.get(action_name)
    if action is None:
        action = bpy.data.actions.new(action_name)
    action.use_fake_user = True
    id_block.animation_data.action = action
    return action


def insert_curve_on_id(
    action,
    data_path,
    frames,
    values,
    group_name="CTRL",
    clear_existing=True,
    interpolation="BEZIER",
    clamp_01=False,
    log_spikes=False,
    despike=False,
    median_window=5,
    spike_threshold=1.2,
    quantized=False,
    q_epsilon=0.0003,
    q_den=8192,
    q_min_abs=1.2,
    channel_index=None,
):
    """Insert an FCurve on an arbitrary data_path for the given action.
    Mirrors insert_curve_on_shapekey behavior for filtering, clamping, interpolation, etc.
    """
    if clear_existing:
        to_remove = [
            fcu
            for fcu in action.fcurves
            if fcu.data_path == data_path
            and (
                channel_index is None
                or getattr(fcu, "array_index", -1) == channel_index
            )
        ]
        for fcu in to_remove:
            action.fcurves.remove(fcu)
    fc = action.fcurves.new(
        data_path=data_path,
        index=(channel_index if channel_index is not None else -1),
        action_group=group_name,
    )

    values_local = list(values)

    # Optional despike using a sliding median
    if despike and len(values_local) >= 3:
        w = (
            int(median_window)
            if int(median_window) % 2 == 1
            else max(3, int(median_window) + 1)
        )
        half = w // 2
        filtered_vals = []
        for i, v in enumerate(values_local):
            left = max(0, i - half)
            right = min(len(values_local), i + half + 1)
            neighborhood = values_local[left:i] + values_local[i + 1 : right]
            if neighborhood:
                med = statistics.median([float(x) for x in neighborhood])
                if abs(float(v) - float(med)) > float(spike_threshold):
                    v = med
            filtered_vals.append(v)
        values_local = filtered_vals

    # Optional quantized-outlier suppression snapped to k/den if near and large
    if quantized and len(values_local) > 0:
        processed_vals = []
        nvals = len(values_local)
        for i, v in enumerate(values_local):
            try:
                vf = float(v)
            except Exception:
                processed_vals.append(v)
                continue
            if abs(vf) > float(q_min_abs):
                k = round(vf * float(q_den))
                quant = k / float(q_den)
                if abs(vf - quant) <= float(q_epsilon):
                    neigh = []
                    if i > 0:
                        try:
                            neigh.append(float(values_local[i - 1]))
                        except Exception:
                            pass
                    if i + 1 < nvals:
                        try:
                            neigh.append(float(values_local[i + 1]))
                        except Exception:
                            pass
                    vf = statistics.median(neigh) if neigh else 0.0
            processed_vals.append(vf)
        values_local = processed_vals

    # Deduplicate and sort frames
    frame_map = {}
    for fr, val in zip(frames, values_local):
        try:
            fr_f = float(fr)
            val_f = float(val)
            if clamp_01:
                if val_f < 0.0:
                    val_f = 0.0
                elif val_f > 1.0:
                    val_f = 1.0
        except Exception:
            continue
        frame_map[fr_f] = val_f  # last value for duplicate frames

    sorted_frames = sorted(frame_map.keys())
    count = len(sorted_frames)

    # Optional spike logging
    if log_spikes and count > 1:
        prev_f = sorted_frames[0]
        prev_v = frame_map[prev_f]
        for fr in sorted_frames[1:]:
            v = frame_map[fr]
            if abs(v - prev_v) > 0.25:
                print(
                    f"[CTRL Import] Spike on {data_path}: frame {prev_f}->{fr} delta {v - prev_v:.3f}"
                )
            prev_v = v
            prev_f = fr

    if count > 0:
        kps = fc.keyframe_points
        kps.add(count)
        for i, fr in enumerate(sorted_frames):
            kp = kps[i]
            kp.co = (fr, frame_map[fr])
            kp.interpolation = interpolation
            if interpolation == "BEZIER":
                kp.handle_left_type = "AUTO_CLAMPED"
                kp.handle_right_type = "AUTO_CLAMPED"

    fc.update()
    return fc

    """
    Try to resolve the Face Board (armature) and a pose-bone transform data_path (location/rotation_euler/scale)
    for a given CTRL_* shapekey. Returns (face_board_object, data_path, axis_index) or (None, None, None).
    """

    axis_index = {"X": 0, "Y": 1, "Z": 2}.get(str(axis).upper(), 2)

    src = find_driver_source_for_shapekey(obj, shapekey_name)

    if src:
        target_id, target_dp, transform_type = src

        # Object transform target via transform_type (e.g., LOC_Y, ROT_X, SCALE_Z)
        if transform_type and hasattr(target_id, "type"):
            tt = str(transform_type).upper()
            mapping = {
                "LOC": "location",
                "ROT": "rotation_euler",
                "SCALE": "scale",
            }
            axis_map = {"X": 0, "Y": 1, "Z": 2}
            for prefix, dp_name in mapping.items():
                if tt.startswith(prefix):
                    axis_char = tt.split("_")[-1] if "_" in tt else ""
                    idx = axis_map.get(axis_char, axis_index)
                    return target_id, dp_name, idx
        # Pose-bone location target via data_path
        if (
            target_dp
            and isinstance(target_id, bpy.types.ID)
            and "pose.bones[" in target_dp
            and ".location" in target_dp
        ):
            base_dp = target_dp

            det_axis_index = axis_index

            if base_dp.endswith(".x"):
                base_dp = base_dp[:-2]

                det_axis_index = 0

            elif base_dp.endswith(".y"):
                base_dp = base_dp[:-2]

                det_axis_index = 1

            elif base_dp.endswith(".z"):
                base_dp = base_dp[:-2]

                det_axis_index = 2

        if target_dp and hasattr(target_id, "type"):
            if target_dp.endswith(".location") or target_dp.endswith("location"):
                return target_id, "location", axis_index

            if target_dp.endswith(".rotation_euler") or target_dp.endswith(
                "rotation_euler"
            ):
                return target_id, "rotation_euler", axis_index
            if target_dp.endswith(".scale") or target_dp.endswith("scale"):
                return target_id, "scale", axis_index

    # 2) Use MetaHuman DNA addon's scene data if available to find a face_board
    face_obj = None
    try:
        scene = context.scene
        mh = getattr(scene, "meta_human_dna", None)
        inst_list = getattr(mh, "rig_logic_instance_list", None) if mh else None
        if inst_list:
            cand = None
            for inst in inst_list:
                fb = getattr(inst, "face_board", None)
                if not fb:
                    continue
                # Prefer the instance that references this mesh as its head_mesh
                if getattr(inst, "head_mesh", None) == obj:
                    cand = fb
                    break
                cand = cand or fb
            face_obj = cand
    except Exception:
        face_obj = None

    # 3) Fallback: heuristic search for a likely face_gui armature
    if not face_obj:
        for o in bpy.data.objects:
            if getattr(o, "type", None) == "ARMATURE":
                name_l = o.name.lower()
                if "face_gui" in name_l or name_l.endswith("_face_gui"):
                    face_obj = o
                    break

    if not face_obj or not getattr(face_obj, "pose", None):
        return None, None, None

    # Candidate bone names: prefer exact CTRL_* name
    candidates = [shapekey_name]
    if not shapekey_name.startswith("CTRL"):
        candidates.append(f"CTRL_{shapekey_name}")

    for bn in candidates:
        pb = face_obj.pose.bones.get(bn)

        if pb:
            return face_obj, f'pose.bones["{bn}"].location', axis_index

    # Object-control fallback: map CTRL_* name to object control if present (no drivers)
    # Try exact object name match, then names with numeric suffixes (.001, etc.)
    for name in candidates:
        ob = bpy.data.objects.get(name)
        if ob:
            return ob, "location", axis_index
    # Try suffix variants (name.###)
    for ob in bpy.data.objects:
        for name in candidates:
            if ob.name.startswith(name + "."):
                return ob, "location", axis_index

    return None, None, None


class IMPORT_OT_ascii_fbx_shapekeys(bpy.types.Operator, ImportHelper):
    bl_idname = "import_scene.ascii_fbx_shapekeys_ctrl"
    bl_label = "Import Shapekeys from ASCII FBX"
    bl_options = {"REGISTER", "UNDO"}
    filename_ext = ".fbx"
    filter_glob: StringProperty(default="*.fbx", options={"HIDDEN"})

    # Options
    only_ctrl: BoolProperty(
        name="Only CTRL tracks",
        description="Import only tracks whose names start with 'CTRL' (also used when clearing drivers)",
        default=True,
    )

    clear_drivers: BoolProperty(
        name="Clear shapekey drivers before import",
        description='Remove drivers on key_blocks["*"].value before importing (limits to CTRL_* if "Only CTRL tracks" is on)',
        default=True,
    )

    clear_existing_fcurves: BoolProperty(
        name="Clear existing FCurves for imported keys",
        description="Remove any existing FCurves on the same shapekey value before inserting new keyframes",
        default=True,
    )

    sequential_index_frames: BoolProperty(
        name="Map key index to frames (ignore FBX time)",
        description="Write key i to frame_start + i*frame_step for each CTRL property",
        default=True,
    )
    frame_start: IntProperty(
        name="Start Frame",
        description="Frame to place first key when mapping by index",
        default=1,
        min=0,
    )
    frame_step: IntProperty(
        name="Frame Step",
        description="Frame increment between keys when mapping by index",
        default=1,
        min=1,
    )

    bezier_auto_clamped: BoolProperty(
        name="Bezier auto-clamped interpolation",
        description="Use BEZIER interpolation with AUTO_CLAMPED handles for inserted keys",
        default=True,
    )

    clamp_values_01: BoolProperty(
        name="Clamp values to [0,1]",
        description="Clamp incoming shapekey values to the 0..1 range before inserting",
        default=True,
    )

    log_spikes: BoolProperty(
        name="Log large value jumps (debug)",
        description="Print to the console when consecutive keys jump by more than 0.25",
        default=False,
    )

    despike_filter: BoolProperty(
        name="Filter spikes (median)",
        description="Apply a sliding median filter to suppress isolated outliers before key insertion",
        default=True,
    )
    despike_window: IntProperty(
        name="Median window",
        description="Odd window size for median filter (>=3). Used only if Filter spikes is enabled.",
        default=5,
        min=3,
    )
    despike_threshold: FloatProperty(
        name="Spike threshold",
        description="Treat a value as a spike if it deviates from the neighborhood median by more than this amount",
        default=1.0,
        min=0.0,
    )

    quantized_filter: BoolProperty(
        name="Filter quantized outliers (k/8192)",
        description="Replace values > min abs that are within epsilon of k/8192 with neighbor median",
        default=True,
    )
    quantized_epsilon: FloatProperty(
        name="Quantized epsilon",
        description="Max distance to nearest k/denominator to treat as quantized",
        default=0.0003,
        min=0.0,
    )
    quantized_denominator: IntProperty(
        name="Quantized denominator",
        description="Denominator used for detecting quantized values (k/denominator)",
        default=8192,
        min=1,
    )
    quantized_min_abs: FloatProperty(
        name="Quantized min abs",
        description="Only treat values with abs(value) greater than this as quantized outliers",
        default=1.2,
        min=0.0,
    )

    apply_to_face_board: BoolProperty(
        name="Apply to Face Board",
        description="Insert keyframes on the Face Board (pose bone location) instead of shapekey values",
        default=True,
    )

    face_board_axis: bpy.props.EnumProperty(
        name="Face Board Axis",
        description="Axis on the Face Board control location to key (X/Y/Z). Default Z",
        items=[
            ("X", "X", "Use X axis"),
            ("Y", "Y", "Use Y axis"),
            ("Z", "Z", "Use Z axis"),
        ],
        default="Y",
    )

    stagger_channels: BoolProperty(
        name="Stagger channels (offset frames per channel)",
        description="Offset frames per channel by a fixed amount to avoid overlapping frames across channels",
        default=False,
    )
    stagger_step: IntProperty(
        name="Stagger step per channel",
        description="Frame offset added per channel index when staggering",
        default=1,
        min=0,
    )

    def execute(self, context):
        filepath = self.filepath

        if not os.path.isfile(filepath):
            self.report({"ERROR"}, "File not found")

            return {"CANCELLED"}

        # Collect selected mesh objects
        sel_objs = [
            o for o in (context.selected_objects or []) if o and o.type == "MESH"
        ]
        if not sel_objs:
            self.report(
                {"ERROR"},
                "Select one or more mesh objects to receive the shapekey action",
            )

            return {"CANCELLED"}

        # Ensure datablock exists only when writing to shapekeys
        id_to_action = {}
        keyed_pairs = set()
        if not self.apply_to_face_board:
            for obj in sel_objs:
                ensure_shape_key(obj, "Basis")

        # Optionally clear drivers on shapekey values for all targets

        if self.clear_drivers and not self.apply_to_face_board:
            prefix = "CTRL" if self.only_ctrl else None

            total_removed = 0
            for obj in sel_objs:
                total_removed += remove_shapekey_value_drivers(obj, name_prefix=prefix)

            if total_removed:
                self.report({"INFO"}, f"Removed {total_removed} shapekey drivers")

        # Parse FBX (ASCII) once

        parser = ASCII_FBX_Shapekey_Parser()

        prop_to_curves = parser.parse(filepath)

        if not prop_to_curves:
            self.report(
                {"WARNING"},
                "No CTRL shapekey tracks found (ensure the FBX is ASCII and contains KeyTime/KeyValue data).",
            )

            return {"CANCELLED"}

        fps = get_scene_fps(context)

        base_name = os.path.splitext(os.path.basename(filepath))[0]

        # Channel order for optional staggering (global, reused for each object)

        props_sorted = sorted(prop_to_curves.keys())

        prop_idx = {name: i for i, name in enumerate(props_sorted)}

        total_imported_tracks = 0
        objects_processed = 0
        global_min_frame = None

        global_max_frame = None

        unresolved_targets = 0

        for obj in sel_objs:
            action = None
            if not self.apply_to_face_board:
                action_name = f"FBX_CTRL_{base_name}__{obj.name}"

                action = ensure_action_for_shape_keys(obj, action_name)

            imported_count = 0
            min_frame = None
            max_frame = None

            for prop_name, curve_ids in prop_to_curves.items():
                # Use first curve per property

                curve_id = curve_ids[0]

                payload = parser.curves.get(curve_id)

                if not payload:
                    continue

                ticks = payload["times"]

                values = payload["values"]

                if not ticks or not values:
                    continue

                # Compute frames: either map by index (start + i*step) or convert FBX ticks

                ch_off = (
                    (prop_idx.get(prop_name, 0) * self.stagger_step)
                    if self.stagger_channels
                    else 0
                )

                if self.sequential_index_frames:
                    frames = [
                        self.frame_start + i * self.frame_step + ch_off
                        for i in range(len(values))
                    ]

                else:
                    frames = [fbx_ticks_to_frame(t, fps) + ch_off for t in ticks]

                if self.apply_to_face_board:
                    # Resolve Face Board pose bone location path for this CTRL_* name
                    face_obj, target_dp, axis_index = resolve_face_board_and_datapath(
                        context, obj, prop_name, self.face_board_axis
                    )
                    if face_obj and target_dp:
                        # Reuse or create an action on the Face Board object
                        target_action = id_to_action.get(face_obj)
                        if target_action is None:
                            target_action = ensure_action_for_id(
                                face_obj,
                                f"FBX_CTRL_{base_name}__{getattr(face_obj, 'name', 'FaceBoard')}",
                            )
                            id_to_action[face_obj] = target_action
                        # Avoid duplicating the same channel across multiple selected meshes
                        pair_key = (id(face_obj), target_dp, axis_index)
                        if pair_key not in keyed_pairs:
                            insert_curve_on_id(
                                target_action,
                                target_dp,
                                frames,
                                values,
                                group_name="CTRL",
                                clear_existing=self.clear_existing_fcurves,
                                interpolation="BEZIER"
                                if self.bezier_auto_clamped
                                else "LINEAR",
                                clamp_01=self.clamp_values_01,
                                log_spikes=self.log_spikes,
                                despike=self.despike_filter,
                                median_window=self.despike_window,
                                spike_threshold=self.despike_threshold,
                                quantized=self.quantized_filter,
                                q_epsilon=self.quantized_epsilon,
                                q_den=self.quantized_denominator,
                                q_min_abs=self.quantized_min_abs,
                                channel_index=axis_index,
                            )
                            keyed_pairs.add(pair_key)
                            imported_count += 1

                    else:
                        # No matching face board or control target found; track as unresolved and skip
                        unresolved_targets += 1
                        continue

                else:
                    # Ensure the shapekey exists
                    ensure_shape_key(obj, prop_name)
                    # Insert keys on Action
                    insert_curve_on_shapekey(
                        action,
                        prop_name,
                        frames,
                        values,
                        group_name="CTRL",
                        clear_existing=self.clear_existing_fcurves,
                        interpolation="BEZIER"
                        if self.bezier_auto_clamped
                        else "LINEAR",
                        clamp_01=self.clamp_values_01,
                        log_spikes=self.log_spikes,
                        despike=self.despike_filter,
                        median_window=self.despike_window,
                        spike_threshold=self.despike_threshold,
                        quantized=self.quantized_filter,
                        q_epsilon=self.quantized_epsilon,
                        q_den=self.quantized_denominator,
                        q_min_abs=self.quantized_min_abs,
                    )
                    imported_count += 1

                # removed duplicate increment to avoid inflated counts

                if frames:
                    fmin = min(frames)

                    fmax = max(frames)

                    min_frame = fmin if min_frame is None else min(min_frame, fmin)

                    max_frame = fmax if max_frame is None else max(max_frame, fmax)

            if imported_count > 0:
                objects_processed += 1
                total_imported_tracks += imported_count
                if min_frame is not None and max_frame is not None:
                    global_min_frame = (
                        min_frame
                        if global_min_frame is None
                        else min(global_min_frame, min_frame)
                    )
                    global_max_frame = (
                        max_frame
                        if global_max_frame is None
                        else max(global_max_frame, max_frame)
                    )

        if objects_processed == 0:
            self.report(
                {"WARNING"},
                "No usable CTRL curves were imported (no keyframes present).",
            )
            return {"CANCELLED"}

        # Fit scene frame range based on all imported objects
        if (
            global_min_frame is not None
            and global_max_frame is not None
            and global_min_frame < global_max_frame
        ):
            scene = context.scene

            scene.frame_start = int(max(1, round(global_min_frame)))

            scene.frame_end = int(round(global_max_frame))

        mode = "Face Board" if self.apply_to_face_board else "shapekeys"
        extra = (
            f" Unresolved targets: {unresolved_targets}."
            if self.apply_to_face_board and unresolved_targets
            else ""
        )
        self.report(
            {"INFO"},
            f"Imported {total_imported_tracks} CTRL tracks into {objects_processed} object(s) ({mode}).{extra}",
        )

        return {"FINISHED"}


def menu_func_import(self, context):
    self.layout.operator(
        IMPORT_OT_ascii_fbx_shapekeys.bl_idname, text="Import Shapekeys from ASCII FBX"
    )


classes = (IMPORT_OT_ascii_fbx_shapekeys,)


def register():
    for cls in classes:
        bpy.utils.register_class(cls)
    bpy.types.TOPBAR_MT_file_import.append(menu_func_import)


def unregister():
    bpy.types.TOPBAR_MT_file_import.remove(menu_func_import)
    for cls in reversed(classes):
        bpy.utils.unregister_class(cls)


register()
