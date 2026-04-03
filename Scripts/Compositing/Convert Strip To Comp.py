# Tooltip: Create a new scene with the selected strip as the input image for compositing
import bpy

def create_compositing_scene(strip):
    # Create a new scene
    new_scene = bpy.data.scenes.new(name=f"{strip.name}_Scene")
    
    # Enable node-based compositing
    new_scene.use_nodes = True
    tree = new_scene.node_tree

    # Clear default nodes
    for node in tree.nodes:
        tree.nodes.remove(node)

    # Add the image input node
    image_node = tree.nodes.new(type="CompositorNodeImage")
    
    if strip.type == 'MOVIE':
        # Load the movie as an image sequence
        image_node.image = bpy.data.images.load(strip.filepath)
        image_node.image.source = 'MOVIE'
        # Set the frame duration manually
        image_node.frame_duration = strip.frame_final_duration
        # Set the scene duration to match the movie
        new_scene.frame_end = strip.frame_final_duration
    elif strip.type == 'IMAGE':
        # Construct the full file path
        directory = strip.directory
        filename = strip.elements[0].filename
        file_path = bpy.path.abspath(directory + filename)
        image_node.image = bpy.data.images.load(file_path)
        # Set the scene duration to match the strip length
        new_scene.frame_end = strip.frame_final_duration
        if len(strip.elements) > 1:
            # If it's an image sequence
            image_node.image.source = 'SEQUENCE'
            image_node.frame_duration = strip.frame_final_duration
    
    # Add a composite output node
    composite_node = tree.nodes.new(type="CompositorNodeComposite")

    # Link the nodes
    tree.links.new(image_node.outputs[0], composite_node.inputs[0])

    return new_scene

def replace_strip_with_scene_strip(original_scene, strip, new_scene):
    # Get the sequence editor from the original scene
    seq_editor = original_scene.sequence_editor

    # Add the new scene strip
    scene_strip = seq_editor.sequences.new_scene(
        name=new_scene.name,
        scene=new_scene,
        channel=strip.channel,
        frame_start=int(strip.frame_start)  # Ensure frame_start is an integer
    )

    # Remove the original strip
    seq_editor.sequences.remove(strip)

def switch_to_original_scene_and_workspace(original_scene, workspace_name):
    # Switch back to the original scene
    bpy.context.window.scene = original_scene
    # Switch back to the video editing workspace
    for workspace in bpy.data.workspaces:
        if workspace.name == workspace_name:
            bpy.context.window.workspace = workspace
            break

def main():
    # Ensure a strip is selected
    selected_strips = bpy.context.selected_sequences
    if not selected_strips:
        print("No strips selected")
        return

    strip = selected_strips[0]

    if strip.type not in {'MOVIE', 'IMAGE'}:
        print("Selected strip is not a movie or image")
        return

    # Store the original scene and workspace
    original_scene = bpy.context.scene
    original_workspace = bpy.context.window.workspace.name

    # Create the compositing scene
    new_scene = create_compositing_scene(strip)

    if new_scene:
        # Replace the strip with the scene strip in the original scene
        replace_strip_with_scene_strip(original_scene, strip, new_scene)

        # Switch back to the original scene and video editing workspace
        switch_to_original_scene_and_workspace(original_scene, original_workspace)

main()
