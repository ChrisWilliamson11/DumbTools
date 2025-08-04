# Tooltip: Create circular arrays of platonic solids with customizable radius, count, and rotation
import bpy
import math
from mathutils import Vector, Matrix, Euler

def create_platonic_solid(size=1.0):
    """Create a tetrahedron"""
    bpy.ops.mesh.primitive_cone_add(vertices=3, radius1=size, radius2=0, depth=size*2)
    obj = bpy.context.active_object
    obj.scale = (1, 1, 0.8)
    return obj

def arrange_in_circular_array(num_objects, radius, rotation_offset=0):
    """Arrange objects in a circular array"""
    # Calculate size based on radius and number of objects
    circumference = 2 * math.pi * radius
    size = circumference / (num_objects * 1.6)  # Packing factor
    
    angle_step = (2 * math.pi) / num_objects
    
    for i in range(num_objects):
        angle = i * angle_step + rotation_offset
        x = radius * math.cos(angle)
        y = radius * math.sin(angle)
        
        obj = create_platonic_solid(size=size)
        obj.location = Vector((x, y, 0))
        
        # Calculate tangent angle
        tangent_angle = angle + (math.pi / 2)
        
        # Alternate orientation for adjacent objects
        flip_factor = math.pi if i % 2 == 0 else 0
        
        # Initial orientation - alternating flip around tangent axis
        obj.rotation_euler = Euler((flip_factor, 0, tangent_angle), 'XYZ')
        
        # Add X-axis rotation driver (primary rotation)
        driver_x = obj.driver_add('rotation_euler', 0).driver
        driver_x.type = 'SCRIPTED'
        var_x = driver_x.variables.new()
        var_x.name = 'frame'
        var_x.type = 'SINGLE_PROP'
        var_x.targets[0].id_type = 'SCENE'
        var_x.targets[0].id = bpy.context.scene
        var_x.targets[0].data_path = "frame_current"
        
        # Add Y-axis rotation driver (secondary rotation)
        driver_y = obj.driver_add('rotation_euler', 1).driver
        driver_y.type = 'SCRIPTED'
        var_y = driver_y.variables.new()
        var_y.name = 'frame'
        var_y.type = 'SINGLE_PROP'
        var_y.targets[0].id_type = 'SCENE'
        var_y.targets[0].id = bpy.context.scene
        var_y.targets[0].data_path = "frame_current"
        
        # Alternate rotation direction based on radius and position
        rotation_direction = -1 if (radius % 2 == 0) != (i % 2 == 0) else 1
        
        # Phase shift for Y rotation
        phase = (i / num_objects) * 2 * math.pi
        
        # Primary rotation (X-axis) with initial flip
        driver_x.expression = f"{rotation_direction} * frame * 0.05 + {flip_factor}"
        
        # Reduced amplitude for Y-axis rotation to prevent intersection
        driver_y.expression = f"sin(frame * 0.05 + {phase}) * 0.3"

def create_concentric_circles(num_rings):
    """Create concentric circles of objects"""
    base_objects = 4  # Start with 4 objects in center
    ring_spacing = 0.55  # Tighter ring spacing
    
    for ring in range(num_rings):
        current_radius = ring * ring_spacing
        if ring == 0:
            num_objects = base_objects
        else:
            # Calculate objects needed for this ring
            num_objects = int(base_objects * (ring + 1))
        
        # Alternate offset for better interlocking
        rotation_offset = 0 if ring % 2 == 0 else math.pi / num_objects
        arrange_in_circular_array(num_objects, current_radius, rotation_offset)

def main():
    # Clear existing objects
    bpy.ops.object.select_all(action='SELECT')
    bpy.ops.object.delete()
    
    num_rings = 6
    create_concentric_circles(num_rings)

main()
