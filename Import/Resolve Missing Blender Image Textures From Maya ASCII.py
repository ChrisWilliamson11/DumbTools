# Tooltip: Recursively process .blend files next to .ma files and fill null Image Texture filenames from the Maya ASCII shading network
# Usage (GUI): Run in Blender, it opens a dialog to choose a root folder and recursion depth
# Usage (CLI example): blender --background --python "<this file>" -- --root "D:/Assets" --max-depth -1

import bpy
import os
import re
import sys
from collections import defaultdict, deque
from dataclasses import dataclass
from typing import Dict, List, Optional, Set, Tuple
from datetime import datetime

# ----------------------------
# Maya ASCII (.ma) lightweight parser and graph
# ----------------------------

@dataclass
class NodeInfo:
    type: str

class MayaAsciiGraph:
    def __init__(self, ma_path: str):
        self.ma_path = ma_path
        self.node_types: Dict[str, NodeInfo] = {}
        self.sg_to_material: Dict[str, str] = {}  # SG name -> material node feeding SG.surfaceShader
        self.file_textures: Dict[str, str] = {}   # file node name -> fileTextureName path
        # dest (node, attr) -> list of (src_node, src_attr)
        self.incoming: Dict[Tuple[str, str], List[Tuple[str, str]]] = defaultdict(list)
        self._parse()

    def _parse(self):
        current_node: Optional[str] = None
        current_type: Optional[str] = None
        if not os.path.isfile(self.ma_path):
            return
        # Regexes
        re_create = re.compile(r'^createNode\s+(\w+)\s+-n\s+"([^"]+)"')
        # connectAttr "src.node.attr" "dst.node.attr";
        re_connect = re.compile(r'^connectAttr\s+"([^"]+)\.([^"\.]+)"\s+"([^"]+)\.([^"\.]+)"')
        # setAttr forms:
        #   setAttr ".ftn" -type "string" "C:/path";
        #   setAttr -type "string" "file1.fileTextureName" "C:/path";
        re_set_ftn_short = re.compile(r'^setAttr\s+"\.ftn"\s+-type\s+"string"\s+"([^"]*)"')
        re_set_ftn_long = re.compile(r'^setAttr\s+-type\s+"string"\s+"([^.]+)\.fileTextureName"\s+"([^"]*)"')

        try:
            with open(self.ma_path, 'r', encoding='utf-8', errors='ignore') as f:
                for line in f:
                    line = line.strip()
                    if not line:
                        continue
                    m = re_create.match(line)
                    if m:
                        current_type, current_node = m.group(1), m.group(2)
                        self.node_types[current_node] = NodeInfo(type=current_type)
                        continue
                    m = re_connect.match(line)
                    if m:
                        src_node, src_attr, dst_node, dst_attr = m.group(1), m.group(2), m.group(3), m.group(4)
                        self.incoming[(dst_node, dst_attr)].append((src_node, src_attr))
                        # Track SG -> material via surfaceShader/ss
                        if self.node_types.get(dst_node, NodeInfo('')).type == 'shadingEngine' and dst_attr in ('surfaceShader', 'ss'):
                            # last writer wins; typical files only have one
                            self.sg_to_material[dst_node] = src_node
                        continue
                    # fileTextureName set (short form tied to current node)
                    m = re_set_ftn_short.match(line)
                    if m and current_node and self.node_types.get(current_node, NodeInfo('')).type == 'file':
                        self.file_textures[current_node] = m.group(1)
                        continue
                    # fileTextureName set (long form)
                    m = re_set_ftn_long.match(line)
                    if m:
                        node_name, tex_path = m.group(1), m.group(2)
                        if self.node_types.get(node_name, NodeInfo('')).type == 'file':
                            self.file_textures[node_name] = tex_path
                        continue
        except Exception as e:
            print(f"[MA PARSE] Failed to parse {self.ma_path}: {e}")

    def get_material_for_sg(self, sg_name: str) -> Optional[str]:
        return self.sg_to_material.get(sg_name)

    def _bfs_find_upstream_file(self, start_node: str, target_attrs: Set[str], max_depth: int = 4) -> Optional[str]:
        # Start from (material_node, attr), walk incoming edges to find a file node providing it
        queue: deque[Tuple[str, str, int]] = deque((start_node, attr, 0) for attr in target_attrs)
        visited: Set[Tuple[str, str]] = set()
        while queue:
            node, attr, depth = queue.popleft()
            if (node, attr) in visited or depth > max_depth:
                continue
            visited.add((node, attr))
            # Who feeds this (node, attr)?
            for src_node, src_attr in self.incoming.get((node, attr), []):
                ntype = self.node_types.get(src_node, NodeInfo('')).type
                if ntype == 'file':
                    # Found a file node
                    return src_node
                # Continue upstream: heuristics per common node types
                # aiNormalMap: input -> outValue
                if ntype in ('aiNormalMap', 'bump2d', 'bump3d'):
                    # Normal nodes typically take input/bumpValue from textures
                    upstream_targets = {'input', 'bumpValue'}
                    for up_attr in upstream_targets:
                        queue.append((src_node, up_attr, depth + 1))
                else:
                    # Generic: try typical color/alpha outputs driving something
                    # Walk further upstream from this src_node by trying common inputs
                    for up_attr in ('color', 'outColor', 'outAlpha', 'message'):
                        queue.append((src_node, up_attr, depth + 1))
        return None

    def find_texture_for_material_attr(self, material_node: str, attr_candidates: List[str]) -> Optional[str]:
        # Try long names and short names (Maya often has .c for color, but ASCII often uses long names)
        # 1) As-is
        cand1: Set[str] = set(attr_candidates)
        file_node = self._bfs_find_upstream_file(material_node, cand1)
        if file_node and file_node in self.file_textures:
            return self.file_textures[file_node]
        # 2) Alternate/short names, including transparency/opacity variants
        alt_map = {
            'baseColor': ['baseColor', 'color', 'c'],
            'color': ['color', 'c', 'baseColor'],
            'specularRoughness': ['specularRoughness', 'roughness'],
            'metalness': ['metalness', 'metallic'],
            'normalCamera': ['normalCamera', 'n'],
            'emissionColor': ['emissionColor', 'emission'],
            'transparency': ['transparency', 'it'],
            'opacity': ['opacity'],
            'cutoutOpacity': ['cutoutOpacity']
        }
        expanded: Set[str] = set()
        for a in attr_candidates:
            expanded.update(alt_map.get(a, [a]))
        # 3) Channelized forms (e.g., transparencyR/G/B, opacityR/G/B)
        chan_expanded: Set[str] = set()
        for a in expanded:
            chan_expanded.add(a)
            for suf in ('R', 'G', 'B'):
                chan_expanded.add(f"{a}{suf}")
        file_node = self._bfs_find_upstream_file(material_node, chan_expanded)
        if file_node and file_node in self.file_textures:
            return self.file_textures[file_node]
        return None

# ----------------------------
# Blender-side utilities
# ----------------------------

def node_output_links(node: bpy.types.Node) -> List[bpy.types.NodeLink]:
    links = []
    for output in node.outputs:
        links.extend(output.links)
    return links

# Map a Blender shader input socket name (and/or reached shader node) to likely Maya attribute names
BLENDER_TO_MAYA_ATTR_MAP: Dict[Tuple[str, str], List[str]] = {
    # (shader_node.bl_idname, input_socket_name): [maya_attrs]
    ('ShaderNodeBsdfPrincipled', 'Base Color'): ['baseColor', 'color'],
    ('ShaderNodeBsdfPrincipled', 'Roughness'): ['specularRoughness', 'roughness'],
    ('ShaderNodeBsdfPrincipled', 'Metallic'): ['metalness', 'metallic'],
    ('ShaderNodeBsdfPrincipled', 'Normal'): ['normalCamera'],
    ('ShaderNodeBsdfPrincipled', 'Alpha'): ['transparency', 'opacity', 'cutoutOpacity'],
    ('ShaderNodeEmission', 'Color'): ['emissionColor', 'emission'],
    ('ShaderNodeBsdfDiffuse', 'Color'): ['color'],
    ('ShaderNodeBsdfGlossy', 'Roughness'): ['specularRoughness', 'roughness'],
}

SHADER_TERMINALS: Set[str] = {
    'ShaderNodeBsdfPrincipled', 'ShaderNodeEmission', 'ShaderNodeBsdfDiffuse', 'ShaderNodeBsdfGlossy'
}

INTERMEDIATE_NORMAL_NODES: Set[str] = {'ShaderNodeNormalMap', 'ShaderNodeBump'}


def infer_maya_attr_for_image_node(material: bpy.types.Material, img_node: bpy.types.Node) -> Optional[List[str]]:
    # BFS forward from image node to find nearest shader terminal and which input is targeted
    if not material.node_tree:
        return None
    nt = material.node_tree
    visited_nodes: Set[bpy.types.Node] = set()
    queue: deque[Tuple[bpy.types.Node, int]] = deque([(img_node, 0)])
    max_depth = 6
    while queue:
        node, depth = queue.popleft()
        if node in visited_nodes or depth > max_depth:
            continue
        visited_nodes.add(node)
        # Check direct outgoing links
        for out_sock in node.outputs:
            for link in out_sock.links:
                to_node = link.to_node
                to_input = link.to_socket
                if to_node.bl_idname in SHADER_TERMINALS:
                    return BLENDER_TO_MAYA_ATTR_MAP.get((to_node.bl_idname, to_input.name))
                if to_node.bl_idname in INTERMEDIATE_NORMAL_NODES:
                    # Treat any path through normal/bump as normalCamera in Maya
                    return ['normalCamera']
                # Otherwise continue traversal
                queue.append((to_node, depth + 1))
    return None


def set_image_on_node(img_node: bpy.types.ShaderNodeTexImage, filepath: str) -> bool:
    """Ensure the Image Texture node has an Image datablock and set its filepath.
    Creates a placeholder image if missing; records the path even if not on disk.
    """
    try:
        if not filepath:
            return False
        path = filepath
        # Keep the exact string for .filepath, but use an absolute path for existence check/logging
        abs_check = os.path.abspath(path) if not os.path.isabs(path) else path
        if not os.path.exists(abs_check):
            print(f"[WARN] Texture not found on disk (set anyway): {abs_check}")
        # Create an image datablock if the node has none
        if img_node.image is None:
            name = os.path.basename(path) or (img_node.name or "missing_image")
            img = bpy.data.images.get(name)
            if img is None:
                img = bpy.data.images.new(name=name, width=1, height=1, alpha=True)
                img.source = 'FILE'
            img.filepath = path
            img_node.image = img
        else:
            # Ensure it's file-backed and set the path
            try:
                img_node.image.source = 'FILE'
            except Exception:
                pass
            img_node.image.filepath = path
        return True
    except Exception as e:
        print(f"[ERR] Failed to set image on node '{img_node.name}': {e}")
        return False

def _rewire_image_alpha_to_color_for_transparency(material: bpy.types.Material,
                                                  img_node: bpy.types.ShaderNodeTexImage) -> bool:
    """If the image node's Alpha output is wired to Principled BSDF Alpha, rewire to Color.
    Returns True if a change was made.
    """
    try:
        nt = material.node_tree
        if nt is None:
            return False
        out_color = getattr(img_node.outputs, 'get', lambda k: None)('Color')
        out_alpha = getattr(img_node.outputs, 'get', lambda k: None)('Alpha')
        if out_alpha is None or out_color is None:
            return False
        changed = False
        for link in list(out_alpha.links):
            to_node = link.to_node
            to_socket = link.to_socket
            if to_node and to_node.bl_idname == 'ShaderNodeBsdfPrincipled' and to_socket and to_socket.name == 'Alpha':
                already = any(lk.from_node is img_node and lk.from_socket is out_color for lk in to_socket.links)
                if not already:
                    nt.links.new(out_color, to_socket)
                nt.links.remove(link)
                changed = True
        return changed
    except Exception as e:
        print(f"[REWIRE-ERR] {e}")
        return False

# ----------------------------
# Batch Operator + CLI entry
# ----------------------------

from bpy.props import StringProperty, IntProperty, BoolProperty
from bpy.types import Operator

class ResolveTexturesFromMayaOperator(Operator):
    bl_idname = "file.resolve_textures_from_maya"
    bl_label = "Resolve Image Textures From Maya .ma"
    bl_options = {'REGISTER'}

    # Logging helpers
    _log_initialized: bool = False

    def _ensure_log(self):
        try:
            if not getattr(self, '_log_initialized', False):
                if not getattr(self, 'log_path', None):
                    # Default log in root directory
                    ts = datetime.now().strftime('%Y%m%d_%H%M%S')
                    self.log_path = os.path.join(self.root_directory or os.getcwd(), f"ResolveTextures_{ts}.log")
                os.makedirs(os.path.dirname(self.log_path), exist_ok=True)
                with open(self.log_path, 'a', encoding='utf-8') as f:
                    f.write(f"# Resolve Textures Log - {datetime.now().isoformat()}\n")
                self._log_initialized = True
        except Exception as e:
            print(f"[LOG-ERR] Failed to init log: {e}")

    def _log(self, message: str):
        print(message)
        try:
            self._ensure_log()
            with open(self.log_path, 'a', encoding='utf-8') as f:
                f.write(message + "\n")
        except Exception as e:
            print(f"[LOG-ERR] {e}")

    def _norm(self, p: str) -> str:
        try:
            return os.path.normcase(os.path.normpath(p))
        except Exception:
            return p

    def _load_resume_set(self, resume_log: str) -> Set[str]:
        done: Set[str] = set()
        try:
            with open(resume_log, 'r', encoding='utf-8') as f:
                for line in f:
                    if line.startswith('[SAVED]') or line.startswith('[NO-OP]'):
                        rest = line.split(']', 1)[1].strip()
                        # Trim trailing details in parentheses
                        if ' (' in rest:
                            rest = rest.split(' (', 1)[0].strip()
                        done.add(self._norm(rest))
        except Exception as e:
            self._log(f"[RESUME] Failed to read resume log '{resume_log}': {e}")
        return done

    def _choose_ma_for_dir(self, dir_path: str, blend_name: str) -> Optional[str]:
        # Prefer .ma that shares stem with .blend; fallback to single .ma present; else None
        stem = os.path.splitext(os.path.basename(blend_name))[0]
        cands = [f for f in os.listdir(dir_path) if f.lower().endswith('.ma')]
        if not cands:
            return None
        for c in cands:
            if os.path.splitext(c)[0] == stem:
                return os.path.join(dir_path, c)
        if len(cands) == 1:
            return os.path.join(dir_path, cands[0])
        # If multiple, pick one whose name includes 'shader' or 'material' as a weak heuristic
        for key in ('shader', 'material', 'shading'):
            for c in cands:
                if key in c.lower():
                    return os.path.join(dir_path, c)
        # Fallback first
        return os.path.join(dir_path, cands[0])

    def _process_blend_with_ma(self, blend_path: str, ma_path: str) -> None:
        self._log(f"\n[PROCESS] Blend: {blend_path}\n          Maya:  {ma_path}")
        # Open blend with error handling (e.g., Missing DNA block)
        try:
            res = bpy.ops.wm.open_mainfile(filepath=blend_path)
            if isinstance(res, set) and 'FINISHED' not in res:
                self._log(f"[ERROR] Failed to open blend: {blend_path}; result={res}")
                return

        except Exception as e:
            self._log(f"[ERROR] Failed to read blend file '{blend_path}': {e}")
            return
        ma_graph = MayaAsciiGraph(ma_path)
        changes = 0
        # Iterate mesh-used materials
        used_mats: Set[bpy.types.Material] = set()
        for obj in bpy.data.objects:
            if obj.type != 'MESH':
                continue
            for slot in obj.material_slots:
                if slot and slot.material:
                    used_mats.add(slot.material)
        for mat in used_mats:
            if not mat.use_nodes or not mat.node_tree:
                continue
            sg_name = mat.name
            maya_mat = ma_graph.get_material_for_sg(sg_name)
            if not maya_mat:
                # Some pipelines may have SG suffix; try ensure trailing SG
                if not sg_name.endswith('SG'):
                    maya_mat = ma_graph.get_material_for_sg(sg_name + 'SG')
            if not maya_mat:
                self._log(f"[SKIP] No Maya material feeding SG '{sg_name}' in .ma")
                continue
            # Find image texture nodes with missing filenames
            for node in mat.node_tree.nodes:
                if getattr(node, 'bl_idname', '') == 'ShaderNodeTexImage':
                    missing = (node.image is None) or (node.image and not node.image.filepath)
                    if not missing:
                        continue
                    maya_attr_list = infer_maya_attr_for_image_node(mat, node)
                    if not maya_attr_list:
                        self._log(f"[INFO] Could not infer target shader input for image node '{node.name}' in material '{mat.name}'")
                        continue
                    tex_path = ma_graph.find_texture_for_material_attr(maya_mat, maya_attr_list)
                    if not tex_path:
                        self._log(f"[INFO] No texture found in .ma for material '{maya_mat}' attrs {maya_attr_list}")
                        continue
                    # If not absolute/doesn't exist, try resolve relative to .ma dir
                    if not os.path.isabs(tex_path) or not os.path.exists(tex_path):
                        candidate = os.path.join(os.path.dirname(ma_path), os.path.basename(tex_path))
                        if os.path.exists(candidate):
                            tex_path = candidate
                    if set_image_on_node(node, tex_path):
                        self._log(f"[SET] {mat.name}: '{node.name}' -> {tex_path}")
                        changes += 1
                        # If this came from Maya transparency/opacity, ensure Color (RGB) drives BSDF Alpha
                        if any(a in ('transparency', 'opacity', 'cutoutOpacity') for a in maya_attr_list):
                            if _rewire_image_alpha_to_color_for_transparency(mat, node):
                                self._log(f"[REWIRE] {mat.name}: '{node.name}' Alpha->Alpha -> Color->Alpha")
        if changes:
            try:
                bpy.ops.wm.save_mainfile()
            except Exception as e:
                self._log(f"[ERROR] Failed to save '{blend_path}': {e}")
            else:
                self._log(f"[SAVED] {blend_path} ({changes} texture(s) set)")
        else:
            self._log(f"[NO-OP] {blend_path} (no changes)")

    def process_directory(self, root: str, current_depth: int, max_depth: int):
        # Iterate entries to ensure we pair .blend with .ma in the same directory
        try:
            with os.scandir(root) as it:
                entries = list(it)
        except Exception as e:
            print(f"[ERR] Unable to scan directory {root}: {e}")
            return
        has_ma = any(e.is_file() and e.name.lower().endswith('.ma') for e in entries)
        if has_ma:
            for e in entries:
                if e.is_file() and e.name.lower().endswith('.blend'):
                    ma = self._choose_ma_for_dir(root, e.name)
                    if ma:
                        blend_path = e.path
                        resume = getattr(self, '_resume_set', None)
                        if resume and self._norm(blend_path) in resume:
                            self._log(f"[SKIP-RESUME] {blend_path}")
                            continue
                        self._process_blend_with_ma(blend_path, ma)
        # Recurse
        if max_depth == -1 or current_depth < max_depth:
            for e in entries:
                if e.is_dir():
                    self.process_directory(e.path, current_depth + 1, max_depth)

    # GUI/Operator props
    root_directory: StringProperty(
        name="Root Directory",
        description="Root folder to search (recursively) for .blend files next to a .ma file",
        subtype='DIR_PATH'
    )
    recursion_depth: IntProperty(
        name="Recursion Depth",
        description="How deep to recurse (-1 for unlimited, 0 for current folder only)",
        default=-1,
        min=-1
    )
    log_path: StringProperty(
        name="Log File",
        description="Optional log file path (defaults to a timestamped log in the root directory)",
        subtype='FILE_PATH',
        default=""
    )
    resume_from_log: BoolProperty(
        name="Resume from Log",
        description="Skip .blend files that already show as SAVED or NO-OP in the chosen log",
        default=False
    )
    resume_log_path: StringProperty(
        name="Resume Log File",
        description="Existing log to resume from (defaults to current Log File if left empty)",
        subtype='FILE_PATH',
        default=""
    )


    def execute(self, context):
        if not self.root_directory or not os.path.isdir(self.root_directory):
            self.report({'ERROR'}, "Please choose a valid Root Directory")
            return {'CANCELLED'}
        # Initialize logging (if path not set, it will default under root)
        self._ensure_log()
        # Optional resume set
        self._resume_set = set()
        if getattr(self, 'resume_from_log', False):
            resume_src = (self.resume_log_path or self.log_path) if getattr(self, 'log_path', None) is not None else self.resume_log_path
            if resume_src and os.path.exists(resume_src):
                self._resume_set = self._load_resume_set(resume_src)
                self._log(f"[RESUME] Loaded {len(self._resume_set)} completed entries from {resume_src}")
            else:
                self._log("[RESUME] No resume log found; proceeding without resume")
        self._log(f"[START] Root={self.root_directory} Depth={self.recursion_depth} Log={self.log_path}")
        self.process_directory(self.root_directory, 0, self.recursion_depth)
        self._log("[DONE] Finished resolving textures from Maya .ma")
        self.report({'INFO'}, "Finished resolving textures from Maya .ma")
        return {'FINISHED'}

    def invoke(self, context, event):
        return context.window_manager.invoke_props_dialog(self, width=520)

    def draw(self, context):
        layout = self.layout
        box = layout.box()
        box.label(text="Root Directory:")
        box.prop(self, "root_directory")
        box = layout.box()
        box.label(text="Recursion Settings:")
        box.prop(self, "recursion_depth")
        box = layout.box()
        box.label(text="Logging:")
        box.prop(self, "log_path")
        box = layout.box()
        box.label(text="Resume:")
        box.prop(self, "resume_from_log")
        box.prop(self, "resume_log_path")




def register():
    bpy.utils.register_class(ResolveTexturesFromMayaOperator)


def unregister():
    bpy.utils.unregister_class(ResolveTexturesFromMayaOperator)

# CLI support when run with -- and args
if __name__ == "__main__":
    # If Blender passes control here, allow CLI usage with --root and --max-depth
    argv = sys.argv
    if '--' in argv:
        argv = argv[argv.index('--') + 1:]
    else:
        argv = []
    arg_root = None
    arg_depth = -1
    arg_log = None
    arg_resume = False
    arg_resume_log = None
    i = 0
    while i < len(argv):
        if argv[i] in ('--root', '--root-dir') and i + 1 < len(argv):
            arg_root = argv[i + 1]
            i += 2
        elif argv[i] in ('--max-depth', '--depth') and i + 1 < len(argv):
            try:
                arg_depth = int(argv[i + 1])
            except Exception:
                arg_depth = -1
            i += 2
        elif argv[i] in ('--log', '--log-file') and i + 1 < len(argv):
            arg_log = argv[i + 1]
            i += 2
        elif argv[i] in ('--resume',):
            arg_resume = True
            i += 1
        elif argv[i] in ('--resume-log',) and i + 1 < len(argv):
            arg_resume_log = argv[i + 1]
            i += 2
        else:
            i += 1
    register()
    if arg_root:
        # Execute operator in EXEC mode with properties instead of instantiating the class
        kwargs = dict(root_directory=arg_root, recursion_depth=arg_depth)
        if arg_log:
            kwargs['log_path'] = arg_log
        if arg_resume:
            kwargs['resume_from_log'] = True
        if arg_resume_log:
            kwargs['resume_log_path'] = arg_resume_log
        try:
            bpy.ops.file.resolve_textures_from_maya('EXEC_DEFAULT', **kwargs)
        except Exception as e:
            print(f"[ERROR] Failed to execute operator: {e}")
    else:
        # Launch UI in foreground sessions
        try:
            bpy.ops.file.resolve_textures_from_maya('INVOKE_DEFAULT')
        except Exception as e:
            print(f"[INFO] Register complete. In background mode, supply -- --root <dir>. Error: {e}")

