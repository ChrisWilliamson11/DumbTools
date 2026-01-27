import bpy
import os
import re

# ------------------------------------------------------------------------
# Data Structures
# ------------------------------------------------------------------------

class SequenceItem(bpy.types.PropertyGroup):
    """Stores information about a single detected sequence"""
    name: bpy.props.StringProperty(name="Display Name")
    # Store metadata to reconstruct/find files later
    base_name: bpy.props.StringProperty()
    sep: bpy.props.StringProperty()
    ext: bpy.props.StringProperty()
    
    count: bpy.props.IntProperty(name="Frame Count")
    is_selected: bpy.props.BoolProperty(name="Selected", default=False)

# ------------------------------------------------------------------------
# UI List
# ------------------------------------------------------------------------

class FILEBROWSER_UL_sequence_list(bpy.types.UIList):
    """Custom List to draw sequence items"""
    def draw_item(self, context, layout, data, item, icon, active_data, active_propname):
        # We ensure the layout is clean
        if self.layout_type in {'DEFAULT', 'COMPACT'}:
            layout.ui_units_x = 1.0 # Optional width constraint
            
            # Checkbox for Multi-select
            layout.prop(item, "is_selected", text="")
            
            # Icon
            layout.label(text="", icon='FILE_IMAGE')
            
            # Name
            layout.prop(item, "name", text="", emboss=False)
            
            # Count Info
            sub = layout.row(align=True)
            sub.alignment = 'RIGHT'
            sub.label(text=f"[{item.count} frames]")
            
        elif self.layout_type == 'GRID':
            layout.alignment = 'CENTER'
            layout.label(text="", icon='FILE_IMAGE')
            layout.label(text=item.name)

# ------------------------------------------------------------------------
# Operators
# ------------------------------------------------------------------------

def scan_directory(wm, directory):
    """
    Helper function to scan directory and populate the list.
    Safe to call from Operator or Draw (with care).
    """
    # Decode bytes
    if isinstance(directory, bytes):
        directory = directory.decode('utf-8')
        
    # Update Cache Token
    wm.collapsed_seq_last_dir = directory
    
    # Clear List
    wm.collapsed_sequences.clear()
    
    # Early exit if dir invalid
    if not os.path.isdir(directory):
        return

    # --- Scan Logic (Optimized) ---
    try:
        files = os.listdir(directory)
        sequences = {}
        
        # Pattern: Name + [Optional Sep] + Digits + .Ext
        pattern = re.compile(r'^(.*?)([\.|_|-]?)(\d+)\.(\w+)$')
        
        for f in files:
            match = pattern.match(f)
            if match:
                base, sep, frame_str, ext = match.groups()
                frame = int(frame_str)
                key = (base, sep, ext)
                
                if key not in sequences:
                    sequences[key] = {
                        'frames': [], 
                        'min_frame': frame
                    }
                
                # Store data
                seq = sequences[key]
                seq['frames'].append(frame)
                
        # Populate PropertyGroup
        for key, data in sequences.items():
            base, sep, ext = key
            frames = data['frames']
            
            frames.sort()
            start = frames[0]
            end = frames[-1]
            
            item = wm.collapsed_sequences.add()
            item.name = f"{base}{sep}####.{ext}  [{start}-{end}]"
            item.count = len(frames)
            
            # Store metadata
            item.base_name = base
            item.sep = sep
            item.ext = ext
            
        # Set Active Index safely
        if len(wm.collapsed_sequences) > 0:
            wm.collapsed_seq_index = 0
            
    except (PermissionError, FileNotFoundError) as e:
        print(f"Sequence Browser Safe Fail: {e}")
        # Fail gracefully (List empty)
        pass
    except Exception as e:
        print(f"Sequence Browser Scan Error: {e}")

class FILEBROWSER_OT_refresh_sequences(bpy.types.Operator):
    """Scans the current directory for sequences and populates the list"""
    bl_idname = "filebrowser.refresh_sequences_v2"
    bl_label = "Refresh Sequences"
    bl_description = "Scan directory for image sequences"
    bl_options = {'INTERNAL'}

    def execute(self, context):
        space = context.space_data
        if not isinstance(space, bpy.types.SpaceFileBrowser):
            return {'CANCELLED'}
            
        scan_directory(context.window_manager, space.params.directory)
        return {'FINISHED'}


class FILEBROWSER_OT_load_sequence(bpy.types.Operator):
    bl_idname = "filebrowser.load_sequence_v2"
    bl_label = "Open Sequence"
    bl_description = "Load the selected sequence(s)"
    
    def execute(self, context):
        try:
            space = context.space_data
            if not isinstance(space, bpy.types.SpaceFileBrowser):
                self.report({'ERROR'}, "Not in File Browser")
                return {'CANCELLED'}

            wm = context.window_manager
            raw_dir = space.params.directory
            if isinstance(raw_dir, bytes):
                raw_dir = raw_dir.decode('utf-8')
            
            # Clean Directory (Fix Windows trailing slash issues)
            directory = os.path.normpath(raw_dir)

            # 1. Identify Target Sequences
            target_items = [item for item in wm.collapsed_sequences if item.is_selected]
            if not target_items:
                idx = wm.collapsed_seq_index
                if 0 <= idx < len(wm.collapsed_sequences):
                    target_items = [wm.collapsed_sequences[idx]]
            if not target_items:
                self.report({'WARNING'}, "No sequence selected")
                return {'CANCELLED'}

            # 2. Identify the Intent/Context
            active_op_id = ""
            if space.active_operator:
                # e.g. "IMAGE_OT_open", "SEQUENCER_OT_image_strip_add"
                active_op_id = space.active_operator.bl_idname
            
            print(f"DEBUG: Active Op: {active_op_id}")

            # 3. Helpers
            def get_files_for_item(item):
                prefix = item.base_name + item.sep
                suffix = "." + item.ext
                files = []
                try:
                    all_files = os.listdir(directory)
                    for f in all_files:
                        if f.startswith(prefix) and f.endswith(suffix):
                            middle = f[len(prefix):-len(suffix)]
                            if middle.isdigit():
                                files.append({'name': f})
                    files.sort(key=lambda x: x['name'])
                except:
                    pass
                return files

            # Shared VSE Import Logic (with Time Offset)
            def import_into_vse(ctx_override):
                # 1. Gather Data & Start Frames
                seq_data = []
                for item in target_items:
                    files = get_files_for_item(item)
                    if files:
                        # Parse start frame from first filename
                        # Filename: Base + Sep + [Frame] + . + Ext
                        f_name = files[0]['name']
                        prefix_len = len(item.base_name) + len(item.sep)
                        suffix_len = len(item.ext) + 1 # count dot
                        
                        try:
                            frame_str = f_name[prefix_len : -suffix_len]
                            start_frame = int(frame_str)
                        except:
                            # Fallback if parsing fails
                            start_frame = 1 
                            
                        seq_data.append({
                            'item': item,
                            'files': files,
                            'start': start_frame
                        })
                
                if not seq_data:
                    return 0

                # 2. Calculate Offsets
                # Find min frame
                min_start = min(d['start'] for d in seq_data)
                
                # Get Current Frame (Target Start)
                current_frame = context.scene.frame_current
                
                # 3. Import Loop
                count = 0
                # We start at channel 1 (or current active + 1?)
                # Safer: just increment from a base, or let blender handle overlap?
                # User asked for "layers", implying stacking.
                # Let's try to stack them starting from channel 2 or 3 to be safe, 
                # or just use 'channel' arg if we can query active.
                
                # Simple logic: increment channel for each imported strip
                base_channel = 1 
                # Try to find a safe channel? 
                # For now, let's just supply channel=base_channel+i to ensure they don't overwrite
                
                for i, data in enumerate(seq_data):
                    offset = data['start'] - min_start
                    final_start = current_frame + offset
                    
                    try:
                        # Prepare kwargs
                        # Note: 'channel' arg forces specific channel. 
                        # If we omit it, Blender finds free space.
                        # But free space might put them on same channel but shifted in time (not layers).
                        # Getting "Layers of a shot" usually means vertical stacking.
                        # So let's force channel increment.
                        
                        with ctx_override:
                            bpy.ops.sequencer.image_strip_add(
                                'EXEC_DEFAULT',
                                directory=directory, 
                                files=data['files'],
                                frame_start=final_start,
                                channel=base_channel + i
                            )
                        count += 1
                        print(f"DEBUG: VSE Added {data['item'].name} at frame {final_start} (Offset {offset})")
                    except Exception as e:
                        print(f"DEBUG: VSE Add Failed: {e}")
                
                return count

            # 4. Dispatch Logic (Refactored)
            
            # --- Active Op: Sequencer Add OR Standalone (Fallback) ---
            if "sequencer" in active_op_id.lower() or not active_op_id:
                
                target_area = None
                override = None
                
                # Determine Context
                if "sequencer" in active_op_id.lower():
                    # We are in the Add Operator -> Context is implicitly VSE or linked
                    # But wait, file browser is a separate window/area usually.
                    # We might still need to override if the browser is maximized or popup.
                    # But usually if active_op is set, context is linked.
                    # HOWEVER, to be safe (and match "Standalone" logic), let's find the area.
                    # If invoked from VSE, VSE is 'area' or 'parent'? 
                    # Actually, if active_op is set, we can just Cancel browser and run it?
                    # But 'Cancel' destroys the ephemeral popup context.
                    pass
                
                # Search for VSE Area (Standard Robust Method)
                # If we are in a popup, context.area is the browser.
                # We need the VSE area.
                for screen in bpy.data.screens:
                    for area in screen.areas:
                        if area.type == 'SEQUENCE_EDITOR':
                            target_area = area
                            break
                    if target_area: break
                
                if target_area:
                    print("DEBUG: Targeting VSE Area")
                    
                    # Only cancel if we are in a temporary popup (indicated by active_op_id)
                    if active_op_id:
                        try:
                            bpy.ops.file.cancel()
                        except Exception as e:
                            print(f"DEBUG: Cancel failed (safe to ignore in standalone): {e}")
                    
                    # Create override
                    with context.temp_override(window=context.window, area=target_area):
                         count = import_into_vse(context.temp_override(window=context.window, area=target_area))
                         
                    self.report({'INFO'}, f"Added {count} strips to VSE")
                    return {'FINISHED'}
                else:
                    self.report({'ERROR'}, "No Video Sequencer found.")
                    return {'CANCELLED'}

            # --- Case B: Image Open (Shader Node, Image Editor) ---
            elif "IMAGE_OT_open" in active_op_id:
                print("DEBUG: Manual Image Open Dispatch")
                print(f"DEBUG: Directory: {directory}")
                
                # Context Inspection w/ Priority (Global Window Search)
                found_node = None
                target_tree = None
                target_tree_type = None

                print("DEBUG: Starting Global Context Search...")
                
                try:
                    # Iterate ALL Windows (in case multi-monitor or separate window)
                    for win in context.window_manager.windows:
                        screen = win.screen
                        for area in screen.areas:
                            # print(f"DEBUG: Checking Area: {area.type}") 
                            if area.type == 'NODE_EDITOR':
                                for space in area.spaces:
                                    # DEBUG API CHECK
                                    # print(f"DEBUG: Space Type: {type(space)}")
                                    
                                    if hasattr(space, "node_tree") and space.node_tree:
                                        tree = space.node_tree
                                        # print(f"DEBUG: Found Tree: {tree.name} ({tree.bl_idname})")
                                        
                                        # Check Active Node
                                        candidates = []
                                        if tree.nodes.active:
                                            candidates.append(tree.nodes.active)
                                        
                                        # Fallback: Check Selected Nodes
                                        selected = [n for n in tree.nodes if n.select and n not in candidates]
                                        candidates.extend(selected)
                                        
                                        for node in candidates:
                                            # Strong Match: Node accepts an image
                                            if hasattr(node, "image"):
                                                found_node = node
                                                target_tree = tree
                                                target_tree_type = space.tree_type
                                                print(f"DEBUG: Found Strong Match in {area.type}: {node.name}")
                                                break # Stop checking candidates
                                        
                                        # Weak Match logic (store tree but don't stop searching for strong)
                                        if not target_tree:
                                            target_tree = tree
                                            target_tree_type = space.tree_type
                                        
                                        if found_node: break
                                    else:
                                         # If no node_tree, print props to see if API changed
                                         if space.type == 'NODE_EDITOR':
                                             print(f"DEBUG: No node_tree found in Node Editor. Space props: {dir(space)}")

                                if found_node: break
                        if found_node: break
                except Exception as e:
                    print(f"DEBUG: Context Search Error: {e}")

                # Priority 2: Global Context (If no visible active node found AND no visible tree found)
                # If we found a visible tree (target_tree) but no active node, we should SKIP this 
                # and go straight to Auto-In creation in that visible tree.
                if not found_node and not target_tree:
                    try:
                        obj = context.active_object or bpy.context.active_object
                        # A. Object Material (Shader)
                        if obj and obj.active_material and obj.active_material.node_tree:
                            act_node = obj.active_material.node_tree.nodes.active
                            if act_node and hasattr(act_node, "image"):
                                found_node = act_node
                        
                        # B. Scene Node Tree (Compositor - Hidden)
                        if not found_node and context.scene.node_tree:
                            if context.scene.node_tree.nodes.active:
                                 act_node = context.scene.node_tree.nodes.active
                                 if act_node and hasattr(act_node, "image"):
                                     found_node = act_node
                    except:
                        pass

                # --- Auto-Create Node if Missing (using visible tree found in step 1) ---
                if not found_node and target_tree:
                    print(f"DEBUG: No active node found. Creating new node in {target_tree_type}...")
                    try:
                        new_node = None
                        if target_tree_type == 'CompositorNodeTree':
                            new_node = target_tree.nodes.new(type='CompositorNodeImage')
                        elif target_tree_type == 'ShaderNodeTree':
                            new_node = target_tree.nodes.new(type='ShaderNodeTexImage')
                        elif target_tree_type == 'TextureNodeTree':
                            new_node = target_tree.nodes.new(type='TextureNodeImage')
                        
                        if new_node:
                            new_node.location = (0, 0)
                            # Deselect all
                            for n in target_tree.nodes: n.select = False
                            # Select New
                            new_node.select = True
                            target_tree.nodes.active = new_node
                            found_node = new_node
                            print(f"DEBUG: Created New Node: {new_node.name}")
                    except Exception as e:
                        print(f"DEBUG: Node Creation Failed: {e}")

                if found_node:
                     print(f"DEBUG: Found/Created Node: {found_node.name} Type: {found_node.type}")

                # We cancel the browser first
                bpy.ops.file.cancel()
                
                # Load Logic using Low-Level API (Bypassing Ops)
                item = target_items[0]
                files = get_files_for_item(item)
                
                if files:
                    full_path = os.path.join(directory, files[0]['name'])
                    print(f"DEBUG: Attempting raw load: {full_path}")
                    
                    try:
                        # 1. Load the Image Block directly
                        img = bpy.data.images.load(full_path, check_existing=True)
                        print(f"DEBUG: Image Loaded: {img}")
                        
                        # 2. Configure as Sequence
                        img.source = 'SEQUENCE'
                        # img.frame_duration is Read-Only! We must set it on the USER (Node or Space)
                        # img.frame_duration = len(files) 
                        
                        # 3. Assign to Node (Generic)
                        if found_node and hasattr(found_node, "image"):
                            print(f"DEBUG: Assigning to Node: {found_node.name}")
                            found_node.image = img
                            if hasattr(found_node, "image_user"):
                                found_node.image_user.frame_duration = len(files)
                                found_node.image_user.use_auto_refresh = True
                                print(f"DEBUG: Node Frame Duration Set: {len(files)}")
                        
                        # 4. Assign to Image Editor if open?
                        for area in context.screen.areas:
                             if area.type == 'IMAGE_EDITOR':
                                 for space in area.spaces:
                                     space.image = img
                                     if hasattr(space, "image_user"):
                                         space.image_user.frame_duration = len(files)
                                         space.image_user.use_auto_refresh = True
                                 
                    except Exception as e:
                         print(f"DEBUG: API Load Failed: {e}")
                         import traceback
                         traceback.print_exc()
                         
                return {'FINISHED'}

            # --- Default/Unknown Op ---
            else:
                self.report({'ERROR'}, f"Unsupported context: {active_op_id}. No sequence loaded.")
                return {'CANCELLED'}
            
        except Exception as e:
            print(f"DEBUG: Load Sequence Critical Fail: {e}")
            self.report({'ERROR'}, f"Failed to load: {e}")
            # Try to print full trace to console for debug
            import traceback
            traceback.print_exc()
            return {'CANCELLED'}

# ------------------------------------------------------------------------
# Panel
# ------------------------------------------------------------------------

class FILEBROWSER_PT_sequence_view(bpy.types.Panel):
    bl_label = "Collapsed Sequences V2"
    bl_space_type = 'FILE_BROWSER'
    bl_region_type = 'TOOLS'
    bl_category = "Sequences"

    def draw(self, context):
        layout = self.layout
        wm = context.window_manager
        space = context.space_data
        
        # --- Auto Refresh Logic ---
        # We check if directory changed.
        # Note: space.params.directory acts as the trigger.
        curr_dir = space.params.directory
        
        # Bytes check for comparison
        cmp_dir = curr_dir
        if isinstance(cmp_dir, bytes):
             cmp_dir = cmp_dir.decode('utf-8', 'ignore') # ignore errors for safe cmp
             
        if wm.collapsed_seq_last_dir != cmp_dir:
            scan_directory(wm, curr_dir)
        
        # List
        row = layout.row()
        row.template_list(
            "FILEBROWSER_UL_sequence_list", "sequences",
            wm, "collapsed_sequences",
            wm, "collapsed_seq_index"
        )
        
        # Load Button
        col = layout.column(align=True)
        col.operator("filebrowser.load_sequence_v2", text="Open Sequence", icon='CHECKMARK')
        
        col.separator()
        col.operator("filebrowser.refresh_sequences_v2", text="Force Refresh", icon='FILE_REFRESH')


# ------------------------------------------------------------------------
# Registration
# ------------------------------------------------------------------------

classes = (
    SequenceItem,
    FILEBROWSER_UL_sequence_list,
    FILEBROWSER_OT_refresh_sequences,
    FILEBROWSER_OT_load_sequence,
    FILEBROWSER_PT_sequence_view,
)

def register():
    #print("\n\n!!! COLLAPSED SEQUENCE BROWSER V2 LOADED !!!\n\n")
    for cls in classes:
        bpy.utils.register_class(cls)
        
    # Register Properties on WindowManager
    bpy.types.WindowManager.collapsed_sequences = bpy.props.CollectionProperty(type=SequenceItem)
    bpy.types.WindowManager.collapsed_seq_index = bpy.props.IntProperty(name="Index")
    bpy.types.WindowManager.collapsed_seq_last_dir = bpy.props.StringProperty(name="Last Dir", default="")


def unregister():
    for cls in reversed(classes):
        bpy.utils.unregister_class(cls)
        
    del bpy.types.WindowManager.collapsed_sequences
    del bpy.types.WindowManager.collapsed_seq_index
    del bpy.types.WindowManager.collapsed_seq_last_dir

register()
