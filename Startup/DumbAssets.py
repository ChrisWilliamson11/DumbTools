import bpy
from bpy.types import Operator, Panel
from bpy_extras.io_utils import ImportHelper
import os
import mathutils
import math
import random
import json

# Try to import shapely for NFP support, auto-install if missing
SHAPELY_AVAILABLE = False

def ensure_user_site_packages():
    """Add user site-packages to Python path for Windows Store Blender"""
    import sys
    import site

    # Get user site-packages directory
    user_site = site.getusersitepackages()

    # Add to sys.path if not already there
    if user_site not in sys.path:
        sys.path.insert(0, user_site)
        print(f"Added user site-packages to path: {user_site}")

# Ensure user site-packages is in path (needed for Windows Store Blender)
ensure_user_site_packages()

try:
    from shapely.geometry import Polygon, Point, LineString
    from shapely.ops import unary_union
    SHAPELY_AVAILABLE = True
    print("✓ Shapely available - NFP packing enabled")
except ImportError:
    print("⚠ Shapely not found - attempting to install...")

    # Auto-install Shapely
    import subprocess
    import sys

    try:
        # Get Blender's Python executable path
        python_exe = sys.executable
        print(f"Installing Shapely using: {python_exe}")

        # Install shapely using pip (force user install for Windows Store Blender)
        subprocess.check_call([python_exe, "-m", "pip", "install", "--user", "shapely"])

        print("✓ Shapely installed successfully!")

        # Ensure user site-packages is in path again
        ensure_user_site_packages()

        # Try importing again after installation
        try:
            from shapely.geometry import Polygon, Point, LineString
            from shapely.ops import unary_union
            SHAPELY_AVAILABLE = True
            print("✓ Shapely import successful - NFP packing enabled")
        except ImportError as e:
            print(f"✗ Shapely import failed after installation: {e}")
            print("This can happen with Windows Store Blender - please restart Blender")

    except subprocess.CalledProcessError as e:
        print(f"✗ Failed to install Shapely: {e}")
        print("NFP packing will be disabled")
    except Exception as e:
        print(f"✗ Error installing Shapely: {e}")
        print("NFP packing will be disabled")


# Global positioning function that both operators can use
def position_objects_with_layout(objects, bounds_data, cursor_matrix, assets_per_row, scene_props, original_selection):
    """Position objects using the selected scattering algorithm with stored bounds data"""
    if not objects:
        return

    print(f"Positioning {len(objects)} objects using {scene_props.scattering_method}")

    # Use stored bounds data if available, otherwise calculate
    if bounds_data and len(bounds_data) == len(objects):
        print("Using stored bounds data")
        object_bounds = []
        for bound_info in bounds_data:
            object_bounds.append((bound_info["width"], bound_info["height"], bound_info["depth"]))
    else:
        print("Calculating bounds data")
        object_bounds = calculate_object_bounds(objects)

    # Order objects based on scene property settings
    print(f"Object ordering: {scene_props.object_order}")
    if scene_props.object_order == 'SIZE_BIG_TO_SMALL' or scene_props.object_order == 'SIZE_LARGE_FIRST':
        # Sort by volume (largest first)
        volume_pairs = []
        for i, obj in enumerate(objects):
            if i < len(object_bounds):
                w, h, d = object_bounds[i]
                volume = w * h * d
                volume_pairs.append((volume, obj, object_bounds[i]))
                print(f"Object {obj.name}: volume = {volume:.3f}")
            else:
                volume_pairs.append((1.0, obj, (2.0, 2.0, 2.0)))

        volume_pairs.sort(key=lambda x: x[0], reverse=True)
        objects = [pair[1] for pair in volume_pairs]
        object_bounds = [pair[2] for pair in volume_pairs]
        print("Sorted by size (large first)")

    elif scene_props.object_order == 'SIZE_SMALL_TO_BIG' or scene_props.object_order == 'SIZE_SMALL_FIRST':
        # Sort by volume (smallest first)
        volume_pairs = []
        for i, obj in enumerate(objects):
            if i < len(object_bounds):
                w, h, d = object_bounds[i]
                volume = w * h * d
                volume_pairs.append((volume, obj, object_bounds[i]))
                print(f"Object {obj.name}: volume = {volume:.3f}")
            else:
                volume_pairs.append((1.0, obj, (2.0, 2.0, 2.0)))

        volume_pairs.sort(key=lambda x: x[0])
        objects = [pair[1] for pair in volume_pairs]
        object_bounds = [pair[2] for pair in volume_pairs]
        print("Sorted by size (small first)")

    elif scene_props.object_order == 'RANDOM':
        print(f"Random seed: {scene_props.random_seed}")
        # Create paired list of objects and bounds
        paired_data = list(zip(objects, object_bounds))
        # Set seed for consistent randomization
        random.seed(scene_props.random_seed)
        random.shuffle(paired_data)
        # Unpack back to separate lists
        objects, object_bounds = zip(*paired_data)
        objects = list(objects)
        object_bounds = list(object_bounds)
        print("Randomized object order")

    # Apply the selected scattering method using scene properties
    if scene_props.scattering_method == 'GRID':
        apply_grid_layout(objects, object_bounds, cursor_matrix, scene_props.grid_rows, scene_props.grid_spacing)
    elif scene_props.scattering_method == 'CIRCLE':
        apply_circle_packing(objects, object_bounds, cursor_matrix, scene_props.circle_spacing)
    elif scene_props.scattering_method == 'SPIRAL':
        apply_spiral_layout(objects, object_bounds, cursor_matrix, scene_props.spiral_density)
    elif scene_props.scattering_method == 'VERTICAL_STACK':
        apply_vertical_stack(objects, object_bounds, cursor_matrix, scene_props.grid_spacing)
    elif scene_props.scattering_method == 'POISSON_DISK':
        apply_poisson_disk_sampling(objects, object_bounds, cursor_matrix,
                                   scene_props.poisson_min_distance, scene_props.poisson_area_size, scene_props.random_seed)
    elif scene_props.scattering_method == 'NFP':
        if SHAPELY_AVAILABLE:
            apply_nfp_packing(objects, object_bounds, cursor_matrix, scene_props.nfp_spacing, scene_props.random_seed)
        else:
            print("⚠ NFP packing requires Shapely library. Install with: pip install shapely")
            print("Falling back to grid packing...")
            apply_simple_grid(objects, object_bounds, cursor_matrix, assets_per_row, scene_props.grid_spacing)
    elif scene_props.scattering_method == 'SURFACE_PACK':
        apply_surface_packing(objects, object_bounds, cursor_matrix,
                            scene_props.surface_pack_spacing, scene_props.surface_pack_density,
                            scene_props.random_seed, original_selection)

    # Apply surface conforming if enabled (works with all scattering methods except SURFACE_PACK)
    if scene_props.conform_to_surface and scene_props.scattering_method != 'SURFACE_PACK':
        if scene_props.scattering_method == 'VERTICAL_STACK':
            # For vertical stack, only conform the first (bottom) object
            if objects:
                conform_objects_to_surface([objects[0]], [object_bounds[0]], cursor_matrix, original_selection)
        else:
            # For all other methods, conform all objects
            conform_objects_to_surface(objects, object_bounds, cursor_matrix, original_selection)


# Global positioning functions that both operators can use
def apply_cursor_transform(obj, local_position, cursor_matrix, bounds, is_non_base=False):
    """Transform object position from local cursor space to world space"""
    # Transform local position to world space
    world_position = cursor_matrix @ local_position

    # Apply position
    obj.location = world_position

    # Apply cursor rotation to object
    cursor_rotation = cursor_matrix.to_euler()
    obj.rotation_euler = cursor_rotation

    # Apply surface offset (half bounding box height) unless it's a non-base object in vertical stack
    if not is_non_base:
        # Get cursor normal (Z-axis of cursor matrix)
        cursor_normal = cursor_matrix.to_3x3() @ mathutils.Vector((0, 0, 1))
        cursor_normal.normalize()

        # Offset by half the object's height along cursor normal
        height_offset = bounds[2] / 2  # bounds[2] is depth/height
        offset_vector = cursor_normal * height_offset
        obj.location += offset_vector


def calculate_object_bounds(objects):
    """Calculate bounding box dimensions for all objects"""
    object_bounds = []

    for obj in objects:
        if obj and obj.type in {'MESH', 'CURVE', 'SURFACE', 'META', 'FONT', 'EMPTY'}:
            # Get object bounding box in world space
            bbox = [obj.matrix_world @ mathutils.Vector(corner) for corner in obj.bound_box]
            min_x = min(corner.x for corner in bbox)
            max_x = max(corner.x for corner in bbox)
            min_y = min(corner.y for corner in bbox)
            max_y = max(corner.y for corner in bbox)
            min_z = min(corner.z for corner in bbox)
            max_z = max(corner.z for corner in bbox)

            width = max_x - min_x
            height = max_y - min_y
            depth = max_z - min_z

            object_bounds.append((width, height, depth))
        else:
            # Default bounds for unsupported object types
            object_bounds.append((2.0, 2.0, 2.0))

    return object_bounds


def apply_circle_packing(objects, object_bounds, cursor_matrix, spacing):
    """Circle packing algorithm - fit circles tightly together without overlaps"""
    if not objects:
        return

    total_objects = len(objects)
    if total_objects == 1:
        # Single object at cursor
        apply_cursor_transform(objects[0], mathutils.Vector((0, 0, 0)), cursor_matrix, object_bounds[0])
        return

    # Convert object bounds to circle radii (use max dimension / 2)
    circles = []
    for i, bounds in enumerate(object_bounds):
        radius = max(bounds[0], bounds[1]) / 2  # Don't add spacing to radius
        circles.append((radius, i))

    # Pack circles using iterative placement algorithm
    packed_circles = pack_circles_tightly(circles, spacing)

    # Position objects based on packed circle positions
    for obj_idx, (x, y, radius) in packed_circles.items():
        if obj_idx >= len(objects):
            continue

        obj = objects[obj_idx]
        if not obj:
            continue

        # Position in local space
        local_position = mathutils.Vector((x, y, 0))

        # Transform to world space using cursor matrix and apply rotation
        apply_cursor_transform(obj, local_position, cursor_matrix, object_bounds[obj_idx])


def pack_circles_tightly(circles, spacing=0.0):
    """Pack circles tightly together using iterative placement"""
    if not circles:
        return {}

    packed = {}
    placed_circles = []

    # Place first circle at center
    first_radius, first_idx = circles[0]
    packed[first_idx] = (0, 0, first_radius)
    placed_circles.append((0, 0, first_radius))

    # Place remaining circles
    for radius, obj_idx in circles[1:]:
        best_position = find_best_circle_position(radius, placed_circles, spacing)
        if best_position:
            x, y = best_position
            packed[obj_idx] = (x, y, radius)
            placed_circles.append((x, y, radius))
        else:
            # Fallback: place at a safe distance
            safe_distance = sum(c[2] for c in placed_circles) / len(placed_circles) + radius
            angle = len(placed_circles) * 0.618 * 2 * math.pi  # Golden angle
            x = safe_distance * math.cos(angle)
            y = safe_distance * math.sin(angle)
            packed[obj_idx] = (x, y, radius)
            placed_circles.append((x, y, radius))

    return packed


def find_best_circle_position(radius, placed_circles, spacing=0.0):
    """Find the best position for a circle that doesn't overlap with existing circles"""
    if not placed_circles:
        return (0, 0)

    best_position = None
    min_distance_to_center = float('inf')

    # Try positions around each existing circle
    for cx, cy, cr in placed_circles:
        # Try positions at various angles around this circle
        for angle in [i * math.pi / 8 for i in range(16)]:  # 16 angles
            # Distance from center of existing circle to center of new circle
            distance = cr + radius + spacing  # Use spacing parameter
            test_x = cx + distance * math.cos(angle)
            test_y = cy + distance * math.sin(angle)

            # Check if this position overlaps with any existing circle
            valid = True
            for other_x, other_y, other_r in placed_circles:
                dist = math.sqrt((test_x - other_x)**2 + (test_y - other_y)**2)
                if dist < (radius + other_r + spacing):  # Use spacing parameter
                    valid = False
                    break

            if valid:
                # Check if this is closer to center than previous best
                distance_to_center = math.sqrt(test_x**2 + test_y**2)
                if distance_to_center < min_distance_to_center:
                    min_distance_to_center = distance_to_center
                    best_position = (test_x, test_y)

    return best_position


def apply_vertical_stack(objects, object_bounds, cursor_matrix, spacing):
    """Vertical stacking - bottom object at cursor, others stacked above"""
    # Start position at cursor level (bottom object sits on cursor)
    current_local_z = 0

    for i, obj in enumerate(objects):
        if not obj:
            continue

        bounds = object_bounds[i]
        # Position object so its bottom is at current_local_z
        local_position = mathutils.Vector((0, 0, current_local_z + bounds[2] / 2))

        # Transform to world space using cursor matrix and apply rotation
        # Only the first object (base) gets surface offset, others are already positioned relative to it
        is_non_base = i > 0
        apply_cursor_transform(obj, local_position, cursor_matrix, bounds, is_non_base)

        # Move to next position (add this object's height plus spacing for next object)
        current_local_z += bounds[2] + spacing


def apply_grid_layout(objects, object_bounds, cursor_matrix, grid_rows, spacing):
    """Grid layout - simple grid if grid_rows specified, otherwise bin packing"""
    if not objects:
        return

    if grid_rows > 0:
        # Calculate assets per row from number of rows
        num_objects = len(objects)
        assets_per_row = math.ceil(num_objects / grid_rows)
        apply_simple_grid(objects, object_bounds, cursor_matrix, assets_per_row, spacing)
    else:
        # Auto-calculate optimal square grid
        num_objects = len(objects)
        optimal_cols = math.ceil(math.sqrt(num_objects))
        apply_simple_grid(objects, object_bounds, cursor_matrix, optimal_cols, spacing)


def apply_simple_grid(objects, object_bounds, cursor_matrix, assets_per_row, spacing):
    """Simple regular grid layout respecting assets_per_row - uses actual bounding boxes"""
    if not objects or assets_per_row <= 0:
        return

    total_objects = len(objects)
    total_rows = math.ceil(total_objects / assets_per_row)

    # Calculate cumulative sizes for each row and column
    row_heights = [0] * total_rows
    col_widths = [0] * assets_per_row

    # First pass: determine row heights and column widths
    for i, bounds in enumerate(object_bounds):
        row = i // assets_per_row
        col = i % assets_per_row

        if row < len(row_heights):
            row_heights[row] = max(row_heights[row], bounds[1])  # Height (Y dimension)
        if col < len(col_widths):
            col_widths[col] = max(col_widths[col], bounds[0])   # Width (X dimension)

    # Calculate cumulative positions
    row_positions = [0]
    for i in range(len(row_heights) - 1):
        row_positions.append(row_positions[-1] + row_heights[i] + spacing)

    col_positions = [0]
    for i in range(len(col_widths) - 1):
        col_positions.append(col_positions[-1] + col_widths[i] + spacing)

    # Calculate total dimensions for centering
    total_width = sum(col_widths) + spacing * (len(col_widths) - 1)
    total_height = sum(row_heights) + spacing * (len(row_heights) - 1)

    # Position objects in grid
    for i, obj in enumerate(objects):
        if not obj:
            continue

        row = i // assets_per_row
        col = i % assets_per_row

        if row >= len(row_positions) or col >= len(col_positions):
            continue

        # Calculate position based on actual cumulative sizes
        x = col_positions[col] + col_widths[col] / 2 - total_width / 2
        y = row_positions[row] + row_heights[row] / 2 - total_height / 2

        # Position in local space
        local_position = mathutils.Vector((x, y, 0))

        # Transform to world space using cursor matrix and apply rotation
        apply_cursor_transform(obj, local_position, cursor_matrix, object_bounds[i])


def apply_bin_packed_grid(objects, object_bounds, cursor_matrix, spacing):
    """Bin-packed grid layout for optimal space usage"""
    # Create rectangles for bin packing (width, height, object_index)
    rectangles = []
    for i, bounds in enumerate(object_bounds):
        # Add spacing to each rectangle
        width = bounds[0] + spacing
        height = bounds[1] + spacing
        rectangles.append((width, height, i))

    # Sort by area (largest first) for better packing
    rectangles.sort(key=lambda r: r[0] * r[1], reverse=True)

    # Pack rectangles using shelf algorithm
    packed_positions = pack_rectangles_shelf_global(rectangles)

    if packed_positions:
        # Calculate bounds of packed area for centering
        min_x = min(pos[0] for pos in packed_positions.values())
        max_x = max(pos[0] + rectangles[next(i for i, r in enumerate(rectangles) if r[2] == obj_idx)][0]
                   for obj_idx, pos in packed_positions.items())
        min_y = min(pos[1] for pos in packed_positions.values())
        max_y = max(pos[1] + rectangles[next(i for i, r in enumerate(rectangles) if r[2] == obj_idx)][1]
                   for obj_idx, pos in packed_positions.items())

        # Center the packed area
        offset_x = -(max_x + min_x) / 2
        offset_y = -(max_y + min_y) / 2

        # Position objects
        for obj_idx, (x, y) in packed_positions.items():
            if obj_idx >= len(objects):
                continue

            obj = objects[obj_idx]
            if not obj:
                continue

            bounds = object_bounds[obj_idx]

            # Position in local space (relative to cursor center)
            local_position = mathutils.Vector((
                x + offset_x + bounds[0] / 2,  # X: center of object
                y + offset_y + bounds[1] / 2,  # Y: center of object
                0                              # Z: at cursor level
            ))

            # Transform to world space using cursor matrix and apply rotation
            apply_cursor_transform(obj, local_position, cursor_matrix, bounds)


def pack_rectangles_shelf_global(rectangles):
    """Simple shelf-based bin packing algorithm"""
    if not rectangles:
        return {}

    positions = {}
    shelves = []  # Each shelf: (y_position, height, current_x)

    for width, height, obj_idx in rectangles:
        placed = False

        # Try to place on existing shelves
        for i, (shelf_y, shelf_height, shelf_x) in enumerate(shelves):
            if height <= shelf_height:
                # Place on this shelf
                positions[obj_idx] = (shelf_x, shelf_y)
                shelves[i] = (shelf_y, shelf_height, shelf_x + width)
                placed = True
                break

        if not placed:
            # Create new shelf
            new_y = shelves[-1][0] + shelves[-1][1] if shelves else 0
            positions[obj_idx] = (0, new_y)
            shelves.append((new_y, height, width))

    return positions


def apply_spiral_layout(objects, object_bounds, cursor_matrix, density):
    """Fibonacci spiral layout"""
    if not objects:
        return

    golden_ratio = (1 + math.sqrt(5)) / 2

    for i, obj in enumerate(objects):
        if not obj:
            continue

        # Fibonacci spiral formula
        angle = i * 2 * math.pi / golden_ratio
        radius = density * math.sqrt(i + 1)

        x = radius * math.cos(angle)
        y = radius * math.sin(angle)

        # Position in local space
        local_position = mathutils.Vector((x, y, 0))

        # Transform to world space using cursor matrix and apply rotation
        apply_cursor_transform(obj, local_position, cursor_matrix, object_bounds[i])


def apply_poisson_disk_sampling(objects, object_bounds, cursor_matrix, min_distance, area_size, random_seed):
    """Poisson disk sampling - place objects one by one with proper size-aware spacing"""
    if not objects:
        return

    print(f"Applying object-aware Poisson disk: {len(objects)} objects, area_size={area_size}, min_distance={min_distance}")

    # Place objects one by one, each considering sizes of already-placed objects
    placed_positions = place_objects_with_poisson_spacing(objects, object_bounds, area_size, min_distance, random_seed)

    print(f"Successfully placed {len(placed_positions)} objects")

    # Position objects at calculated positions
    for i, obj in enumerate(objects):
        if not obj or i >= len(placed_positions):
            continue

        x, y = placed_positions[i]
        local_position = mathutils.Vector((x, y, 0))
        print(f"Object {i} ({obj.name}): positioned at ({x:.2f}, {y:.2f})")

        # Transform to world space using cursor matrix and apply rotation
        apply_cursor_transform(obj, local_position, cursor_matrix, object_bounds[i])


def place_objects_with_poisson_spacing(objects, object_bounds, area_size, base_min_distance, random_seed):
    """Place objects one by one using Poisson disk principles with object-specific spacing.
    Automatically reduces minimum distance until all objects can be placed."""
    if not objects:
        return []

    random.seed(random_seed)

    # Calculate object radii - use diagonal of bounding box for irregular shapes
    object_radii = []
    for i, bounds in enumerate(object_bounds):
        # For irregular shapes, use the diagonal of the bounding box as diameter
        diagonal = math.sqrt(bounds[0]**2 + bounds[1]**2)
        radius = diagonal / 2
        object_radii.append(radius)
        print(f"Object {i}: bounds=({bounds[0]:.2f}, {bounds[1]:.2f}), diagonal={diagonal:.2f}, radius={radius:.2f}")

    print(f"Object radii: {[f'{r:.2f}' for r in object_radii]}")

    # Try different minimum distances until we can place all objects
    current_min_distance = base_min_distance
    min_distance_step = base_min_distance * 0.2  # Reduce by 20% each time
    min_distance_floor = 0.001  # Don't go below this

    # Initialize positions in case we never enter the loop
    positions = []

    while current_min_distance >= min_distance_floor:
        print(f"\n🔄 Attempting placement with min_distance={current_min_distance:.3f}")

        placed_objects = []  # List of (x, y, radius) for placed objects
        positions = []       # List of (x, y) positions to return
        failed_count = 0

        # Place first object at center
        first_radius = object_radii[0]
        placed_objects.append((0.0, 0.0, first_radius))
        positions.append((0.0, 0.0))
        print(f"Placed object 0 at center (0.0, 0.0) with radius {first_radius:.2f}")

        # Place remaining objects
        for i in range(1, len(objects)):
            current_radius = object_radii[i]

            # Try to find a valid position for this object
            best_position = find_poisson_position_for_object(
                current_radius, placed_objects, area_size, current_min_distance, random_seed + i
            )

            if best_position:
                x, y = best_position
                placed_objects.append((x, y, current_radius))
                positions.append((x, y))
                print(f"✓ Placed object {i} at ({x:.2f}, {y:.2f}) with radius {current_radius:.2f}")
            else:
                failed_count += 1
                print(f"✗ FAILED to place object {i} with radius {current_radius:.2f}")

        print(f"📊 Results: {len(positions)} placed, {failed_count} failed")

        # If we placed all objects successfully, we're done!
        if failed_count == 0:
            print(f"🎉 SUCCESS! Placed all {len(objects)} objects with min_distance={current_min_distance:.3f}")
            return positions

        # Otherwise, reduce minimum distance and try again
        current_min_distance -= min_distance_step
        if current_min_distance < min_distance_floor:
            current_min_distance = min_distance_floor
            break

    # If we get here, we couldn't place all objects even with minimum distance
    print(f"⚠️ Could not place all objects even with minimum distance. Returning {len(positions)} positions.")
    return positions


def apply_nfp_packing(objects, object_bounds, cursor_matrix, spacing=0.1, seed=42):
    """Apply No Fit Polygon packing to objects"""
    if not SHAPELY_AVAILABLE:
        print("⚠ NFP packing requires Shapely library")
        return

    if not objects:
        return

    print(f"🔧 NFP packing {len(objects)} objects with spacing {spacing}")

    # Convert Blender objects to polygons for NFP calculation
    polygons = []
    for i, obj in enumerate(objects):
        if not obj or i >= len(object_bounds):
            continue

        # Create a simple polygon from bounding box for now
        # TODO: Extract actual mesh geometry for better results
        width, height, depth = object_bounds[i]  # Unpack all 3 dimensions
        half_w, half_h = width/2, height/2

        # Create rectangle polygon (counter-clockwise)
        poly_coords = [
            (-half_w, -half_h),
            (half_w, -half_h),
            (half_w, half_h),
            (-half_w, half_h),
            (-half_w, -half_h)  # Close the polygon
        ]

        try:
            polygon = Polygon(poly_coords)
            if polygon.is_valid:
                polygons.append(polygon)
                print(f"Object {i}: created polygon with bounds ({width:.2f}, {height:.2f})")
            else:
                print(f"⚠ Object {i}: invalid polygon, skipping")
                polygons.append(None)
        except Exception as e:
            print(f"⚠ Object {i}: polygon creation failed: {e}")
            polygons.append(None)

    # Calculate positions using simplified NFP approach
    positions = calculate_nfp_positions(polygons, spacing, seed)

    print(f"📊 NFP placed {len(positions)} objects")

    # Position objects at calculated positions
    for i, obj in enumerate(objects):
        if not obj or i >= len(positions):
            continue

        x, y = positions[i]
        local_position = mathutils.Vector((x, y, 0))
        print(f"Object {i} ({obj.name}): positioned at ({x:.2f}, {y:.2f})")

        # Transform to world space using cursor matrix and apply rotation
        apply_cursor_transform(obj, local_position, cursor_matrix, object_bounds[i])


def calculate_nfp_positions(polygons, spacing, seed):
    """Calculate positions using simplified NFP approach"""
    random.seed(seed)

    if not polygons:
        return []

    positions = []
    placed_polygons = []  # Store (polygon, x, y) tuples

    # Place first object at origin
    first_poly = polygons[0]
    if first_poly:
        positions.append((0.0, 0.0))
        placed_polygons.append((first_poly, 0.0, 0.0))
        print(f"✓ Placed object 0 at origin")
    else:
        positions.append((0.0, 0.0))
        print(f"⚠ Object 0: no valid polygon, placed at origin")

    # Place remaining objects using simplified NFP logic
    for i in range(1, len(polygons)):
        current_poly = polygons[i]

        if not current_poly:
            # If no valid polygon, place randomly
            x = random.uniform(-2.0, 2.0)
            y = random.uniform(-2.0, 2.0)
            positions.append((x, y))
            print(f"⚠ Object {i}: no valid polygon, placed randomly at ({x:.2f}, {y:.2f})")
            continue

        # Find best position for current polygon
        best_position = find_nfp_position(current_poly, placed_polygons, spacing)

        if best_position:
            x, y = best_position
            positions.append((x, y))
            placed_polygons.append((current_poly, x, y))
            print(f"✓ Placed object {i} at ({x:.2f}, {y:.2f})")
        else:
            # Fallback to random placement if NFP fails
            x = random.uniform(-3.0, 3.0)
            y = random.uniform(-3.0, 3.0)
            positions.append((x, y))
            print(f"⚠ Object {i}: NFP failed, placed randomly at ({x:.2f}, {y:.2f})")

    return positions


def find_nfp_position(polygon, placed_polygons, spacing):
    """Find a valid position for a polygon using simplified NFP logic"""
    if not placed_polygons:
        return (0.0, 0.0)

    # Get polygon bounds to determine minimum search distance
    bounds = polygon.bounds  # (minx, miny, maxx, maxy)
    poly_width = bounds[2] - bounds[0]
    poly_height = bounds[3] - bounds[1]
    min_radius = max(poly_width, poly_height) / 2

    # Try positions in expanding circles, starting much closer
    # Scale everything to work with small objects (mm scale)
    max_radius = min_radius * 20  # Search up to 20x object size
    radius_step = min_radius * 0.1  # Step by 10% of object size
    angle_step = 15    # More angles to try

    current_radius = min_radius + spacing

    print(f"NFP search: min_radius={min_radius:.3f}, max_radius={max_radius:.3f}, step={radius_step:.3f}")

    while current_radius <= max_radius:
        for angle in range(0, 360, angle_step):
            angle_rad = math.radians(angle)
            test_x = current_radius * math.cos(angle_rad)
            test_y = current_radius * math.sin(angle_rad)

            # Check if this position is valid (no overlaps)
            if is_nfp_position_valid(polygon, test_x, test_y, placed_polygons, spacing):
                return (test_x, test_y)

        current_radius += radius_step

    return None  # No valid position found


def is_nfp_position_valid(polygon, x, y, placed_polygons, spacing):
    """Check if a polygon position is valid (no overlaps with placed polygons)"""
    try:
        # Translate the polygon to the test position
        from shapely import affinity
        test_polygon = affinity.translate(polygon, xoff=x, yoff=y)

        # Check against all placed polygons
        for placed_poly, placed_x, placed_y in placed_polygons:
            # Translate placed polygon to its position
            positioned_placed = affinity.translate(placed_poly, xoff=placed_x, yoff=placed_y)

            # Check minimum spacing first (faster than intersection)
            distance = test_polygon.distance(positioned_placed)
            if distance < spacing:
                return False  # Too close

            # Check for actual overlap (should be rare with proper spacing)
            if test_polygon.intersects(positioned_placed):
                intersection = test_polygon.intersection(positioned_placed)
                if hasattr(intersection, 'area') and intersection.area > 0.001:
                    return False  # Actual overlap, position invalid

        return True  # Position is valid

    except Exception as e:
        print(f"⚠ NFP validation error: {e}")
        return False  # Assume invalid on error


def find_poisson_position_for_object(radius, placed_objects, area_size, base_min_distance, random_seed):
    """Find a valid position for an object that doesn't overlap with existing objects"""
    random.seed(random_seed)

    # Try multiple candidate positions
    for attempt in range(100):
        # Generate random position within area
        x = random.uniform(-area_size/2, area_size/2)
        y = random.uniform(-area_size/2, area_size/2)

        # Check if this position is valid (no overlaps)
        valid = True
        for placed_x, placed_y, placed_radius in placed_objects:
            distance = math.sqrt((x - placed_x)**2 + (y - placed_y)**2)
            # Use much more aggressive spacing for irregular shapes
            safety_multiplier = 1.5  # Extra safety margin
            required_distance = (radius + placed_radius) * safety_multiplier + base_min_distance

            if distance < required_distance:
                valid = False
                print(f"  Position ({x:.2f}, {y:.2f}) rejected: distance={distance:.2f} < required={required_distance:.2f}")
                break

        if valid:
            return (x, y)

    return None  # Could not find valid position


def generate_poisson_disk_samples_with_areas(num_objects, area_size, base_min_distance, object_bounds, random_seed):
    """Generate Poisson disk sample points accounting for object areas - ALWAYS generates enough points"""
    if num_objects == 0:
        return []

    # Set random seed for consistent results
    random.seed(random_seed)

    print(f"Poisson disk: Generating {num_objects} points in area {area_size} with base_min_distance {base_min_distance}")

    # Calculate object radii (use the larger of width/height as diameter, then get radius)
    object_radii = []
    for bounds in object_bounds:
        radius = max(bounds[0], bounds[1]) / 2
        object_radii.append(radius)

    # Use the largest object radius as the base minimum distance
    max_object_radius = max(object_radii) if object_radii else 1.0
    min_distance = max(base_min_distance, max_object_radius * 2)  # Ensure objects don't overlap

    print(f"Object radii: {[f'{r:.2f}' for r in object_radii]}")
    print(f"Max object radius: {max_object_radius:.2f}, using min_distance: {min_distance:.2f}")

    attempt = 0

    while True:
        attempt += 1
        print(f"Poisson disk attempt {attempt}: min_distance = {min_distance:.3f}")

        # Generate samples using current minimum distance
        samples = generate_poisson_disk_samples_object_aware(area_size, min_distance, object_radii, random_seed + attempt)

        print(f"Generated {len(samples)} sample points")

        if len(samples) >= num_objects:
            # Success! Return the first num_objects samples
            print(f"Poisson disk SUCCESS after {attempt} attempts with min_distance = {min_distance:.3f}")
            return samples[:num_objects]

        # Not enough samples, reduce minimum distance more aggressively
        if attempt < 5:
            min_distance *= 0.9  # Gentle reduction first
        elif attempt < 10:
            min_distance *= 0.8  # More aggressive
        else:
            min_distance *= 0.7  # Very aggressive

        print(f"Not enough samples ({len(samples)} < {num_objects}), reducing min_distance to {min_distance:.3f}")

        # Safety check - if min_distance gets too small, just place objects randomly
        if min_distance < max_object_radius:
            print("Min distance too small, placing objects randomly within area")
            samples = []
            for i in range(num_objects):
                x = random.uniform(-area_size/2, area_size/2)
                y = random.uniform(-area_size/2, area_size/2)
                samples.append((x, y))
            return samples


def generate_poisson_disk_samples_object_aware(area_size, min_distance, object_radii, random_seed):
    """Generate Poisson disk samples that account for different object sizes"""
    if not object_radii:
        return []

    random.seed(random_seed)

    # Use the minimum distance as the base grid cell size
    cell_size = min_distance / math.sqrt(2)

    # Grid dimensions
    grid_width = int(math.ceil(area_size / cell_size))
    grid_height = int(math.ceil(area_size / cell_size))

    # Initialize grid - store (sample_index, radius) pairs
    grid = [[None for _ in range(grid_height)] for _ in range(grid_width)]

    # Sample list and active list
    samples = []
    active_list = []

    # Generate first sample at center
    first_x = 0.0
    first_y = 0.0
    first_radius = object_radii[0] if object_radii else min_distance / 2

    samples.append((first_x, first_y))
    active_list.append(0)

    # Add to grid
    grid_x = int((first_x + area_size/2) / cell_size)
    grid_y = int((first_y + area_size/2) / cell_size)
    if 0 <= grid_x < grid_width and 0 <= grid_y < grid_height:
        grid[grid_x][grid_y] = (0, first_radius)

    # Generate samples
    while active_list and len(samples) < len(object_radii):
        # Pick random sample from active list
        active_index = random.randint(0, len(active_list) - 1)
        sample_index = active_list[active_index]
        sample_x, sample_y = samples[sample_index]

        # Get the radius for the next object to place
        next_object_index = len(samples)
        next_radius = object_radii[next_object_index] if next_object_index < len(object_radii) else min_distance / 2

        # Try to generate new sample around this point
        found = False
        for _ in range(30):  # k attempts
            # Generate random point in annulus
            angle = random.uniform(0, 2 * math.pi)
            # Use larger radius for spacing to account for object sizes
            min_spacing = min_distance + next_radius
            max_spacing = min_spacing * 2
            radius = random.uniform(min_spacing, max_spacing)

            new_x = sample_x + radius * math.cos(angle)
            new_y = sample_y + radius * math.sin(angle)

            # Check if point is in bounds
            if abs(new_x) > area_size/2 or abs(new_y) > area_size/2:
                continue

            # Check if point is valid (not too close to existing samples)
            if is_valid_sample_object_aware(new_x, new_y, next_radius, samples, grid, cell_size, area_size, grid_width, grid_height, object_radii):
                # Add new sample
                samples.append((new_x, new_y))
                active_list.append(len(samples) - 1)

                # Add to grid
                grid_x = int((new_x + area_size/2) / cell_size)
                grid_y = int((new_y + area_size/2) / cell_size)
                if 0 <= grid_x < grid_width and 0 <= grid_y < grid_height:
                    grid[grid_x][grid_y] = (len(samples) - 1, next_radius)

                found = True
                break

        if not found:
            # Remove from active list
            active_list.pop(active_index)

    return samples


def generate_poisson_disk_samples(area_size, min_distance, random_seed):
    """Generate Poisson disk samples using Bridson's algorithm"""
    random.seed(random_seed)

    # Grid cell size
    cell_size = min_distance / math.sqrt(2)

    # Grid dimensions
    grid_width = int(math.ceil(area_size / cell_size))
    grid_height = int(math.ceil(area_size / cell_size))

    # Initialize grid
    grid = [[None for _ in range(grid_height)] for _ in range(grid_width)]

    # Sample list and active list
    samples = []
    active_list = []

    # Generate first sample
    first_x = random.uniform(-area_size/2, area_size/2)
    first_y = random.uniform(-area_size/2, area_size/2)
    first_sample = (first_x, first_y)

    samples.append(first_sample)
    active_list.append(0)

    # Add to grid
    grid_x = int((first_x + area_size/2) / cell_size)
    grid_y = int((first_y + area_size/2) / cell_size)
    if 0 <= grid_x < grid_width and 0 <= grid_y < grid_height:
        grid[grid_x][grid_y] = 0

    # Generate samples
    while active_list:
        # Pick random sample from active list
        active_index = random.randint(0, len(active_list) - 1)
        sample_index = active_list[active_index]
        sample_x, sample_y = samples[sample_index]

        # Try to generate new sample around this point
        found = False
        for _ in range(30):  # k attempts
            # Generate random point in annulus
            angle = random.uniform(0, 2 * math.pi)
            radius = random.uniform(min_distance, 2 * min_distance)

            new_x = sample_x + radius * math.cos(angle)
            new_y = sample_y + radius * math.sin(angle)

            # Check if point is in bounds
            if abs(new_x) > area_size/2 or abs(new_y) > area_size/2:
                continue

            # Check if point is valid (not too close to existing samples)
            if is_valid_sample(new_x, new_y, samples, grid, cell_size, min_distance, area_size, grid_width, grid_height):
                # Add new sample
                new_sample = (new_x, new_y)
                samples.append(new_sample)
                active_list.append(len(samples) - 1)

                # Add to grid
                grid_x = int((new_x + area_size/2) / cell_size)
                grid_y = int((new_y + area_size/2) / cell_size)
                if 0 <= grid_x < grid_width and 0 <= grid_y < grid_height:
                    grid[grid_x][grid_y] = len(samples) - 1

                found = True
                break

        if not found:
            # Remove from active list
            active_list.pop(active_index)

    return samples


def is_valid_sample_object_aware(x, y, radius, samples, grid, cell_size, area_size, grid_width, grid_height, object_radii):
    """Check if a sample point is valid considering object sizes"""
    # Get grid coordinates
    grid_x = int((x + area_size/2) / cell_size)
    grid_y = int((y + area_size/2) / cell_size)

    # Check neighboring grid cells
    for i in range(max(0, grid_x - 2), min(grid_width, grid_x + 3)):
        for j in range(max(0, grid_y - 2), min(grid_height, grid_y + 3)):
            if grid[i][j] is not None:
                sample_index, other_radius = grid[i][j]
                sample_x, sample_y = samples[sample_index]
                distance = math.sqrt((x - sample_x)**2 + (y - sample_y)**2)
                # Objects need to be separated by the sum of their radii plus some spacing
                required_distance = radius + other_radius + 0.1  # Small buffer
                if distance < required_distance:
                    return False

    return True


def is_valid_sample(x, y, samples, grid, cell_size, min_distance, area_size, grid_width, grid_height):
    """Check if a sample point is valid (not too close to existing samples)"""
    # Get grid coordinates
    grid_x = int((x + area_size/2) / cell_size)
    grid_y = int((y + area_size/2) / cell_size)

    # Check neighboring grid cells
    for i in range(max(0, grid_x - 2), min(grid_width, grid_x + 3)):
        for j in range(max(0, grid_y - 2), min(grid_height, grid_y + 3)):
            if grid[i][j] is not None:
                sample_index = grid[i][j]
                sample_x, sample_y = samples[sample_index]
                distance = math.sqrt((x - sample_x)**2 + (y - sample_y)**2)
                if distance < min_distance:
                    return False

    return True



def apply_surface_packing(objects, object_bounds, cursor_matrix, spacing, density, random_seed, surface_objects):
    """Surface-adaptive packing algorithm for irregular surfaces"""
    if not objects:
        return

    if not surface_objects:
        print("⚠ Surface packing requires selected surface objects. Falling back to circle packing...")
        apply_circle_packing(objects, object_bounds, cursor_matrix, spacing)
        return

    print(f"🔧 Surface packing {len(objects)} objects on {len(surface_objects)} surface objects")
    print(f"Surface objects: {[obj.name for obj in surface_objects]}")

    # Generate sample points on the surface mesh
    surface_points = generate_surface_sample_points(surface_objects, density, random_seed)

    if not surface_points:
        print("⚠ No surface points generated. Falling back to circle packing...")
        apply_circle_packing(objects, object_bounds, cursor_matrix, spacing)
        return

    print(f"Generated {len(surface_points)} surface sample points")

    # Pack objects on surface points using adaptive circle packing
    packed_positions = pack_objects_on_surface(objects, object_bounds, surface_points, spacing, random_seed)

    print(f"📊 Surface packed {len(packed_positions)} objects")

    # Position objects at calculated positions
    for i, obj in enumerate(objects):
        if not obj or i >= len(packed_positions):
            continue

        position, normal = packed_positions[i]

        # Position object at surface point
        obj.location = position

        # Align object with surface normal
        object_up = mathutils.Vector((0, 0, 1))
        rotation_quat = object_up.rotation_difference(normal)
        obj.rotation_euler = rotation_quat.to_euler()

        # Offset object to sit on surface (not embedded)
        bounds = object_bounds[i] if i < len(object_bounds) else (2.0, 2.0, 2.0)
        height_offset = bounds[2] / 2
        offset_vector = normal * height_offset
        obj.location += offset_vector

        print(f"Object {i} ({obj.name}): positioned at {position} with normal {normal}")


def generate_surface_sample_points(surface_objects, density, random_seed):
    """Generate sample points on surface meshes using face sampling"""
    random.seed(random_seed)

    all_points = []

    for surface_obj in surface_objects:
        if not surface_obj or surface_obj.type != 'MESH':
            continue

        # Get evaluated mesh data
        depsgraph = bpy.context.evaluated_depsgraph_get()
        eval_obj = surface_obj.evaluated_get(depsgraph)
        mesh = eval_obj.data

        if not mesh.polygons:
            continue

        # Calculate number of samples based on surface area and density
        total_area = sum(face.area for face in mesh.polygons)
        num_samples = max(10, int(total_area * density * 1000))  # Scale for small objects

        print(f"Surface {surface_obj.name}: area={total_area:.3f}, samples={num_samples}")

        # Sample points on faces weighted by area
        face_areas = [face.area for face in mesh.polygons]
        total_face_area = sum(face_areas)

        if total_face_area == 0:
            continue

        # Generate samples
        for _ in range(num_samples):
            # Choose face weighted by area
            rand_val = random.uniform(0, total_face_area)
            cumulative_area = 0
            selected_face = None

            for i, area in enumerate(face_areas):
                cumulative_area += area
                if rand_val <= cumulative_area:
                    selected_face = mesh.polygons[i]
                    break

            if not selected_face:
                continue

            # Generate random point on the selected face
            face_verts = [mesh.vertices[v] for v in selected_face.vertices]

            if len(face_verts) >= 3:
                # Use barycentric coordinates for triangular faces
                r1, r2 = random.random(), random.random()
                if r1 + r2 > 1:
                    r1, r2 = 1 - r1, 1 - r2
                r3 = 1 - r1 - r2

                # Calculate point position
                point = (r1 * face_verts[0].co +
                        r2 * face_verts[1].co +
                        r3 * face_verts[2].co)

                # Transform to world space
                world_point = surface_obj.matrix_world @ point
                world_normal = surface_obj.matrix_world.to_3x3() @ selected_face.normal
                world_normal.normalize()

                all_points.append((world_point, world_normal))

    return all_points


def pack_objects_on_surface(objects, object_bounds, surface_points, spacing, random_seed):
    """Pack objects on surface points using adaptive spacing"""
    if not objects or not surface_points:
        return []

    random.seed(random_seed)

    # Calculate object radii for spacing
    object_radii = []
    for bounds in object_bounds:
        # Use diagonal of bounding box for irregular shapes
        diagonal = math.sqrt(bounds[0]**2 + bounds[1]**2)
        radius = diagonal / 2
        object_radii.append(radius)

    packed_positions = []
    used_points = []  # List of (point, radius) for placed objects

    # Shuffle surface points for randomness
    available_points = surface_points.copy()
    random.shuffle(available_points)

    for i, obj in enumerate(objects):
        if not obj or i >= len(object_radii):
            continue

        current_radius = object_radii[i]
        best_point = None
        best_distance = float('inf')

        # Find the best available surface point for this object
        for point, normal in available_points:
            # Check if this point is far enough from all placed objects
            valid = True
            min_distance_to_placed = float('inf')

            for used_point, used_radius in used_points:
                distance = (point - used_point).length
                required_distance = current_radius + used_radius + spacing

                if distance < required_distance:
                    valid = False
                    break

                min_distance_to_placed = min(min_distance_to_placed, distance)

            if valid:
                # Prefer points that are reasonably spaced from others
                if min_distance_to_placed < best_distance:
                    best_distance = min_distance_to_placed
                    best_point = (point, normal)

        if best_point:
            point, normal = best_point
            packed_positions.append((point, normal))
            used_points.append((point, current_radius))
            print(f"✓ Placed object {i} at surface point")
        else:
            # Fallback: use the first available point with reduced spacing
            if available_points:
                point, normal = available_points[0]
                packed_positions.append((point, normal))
                used_points.append((point, current_radius))
                print(f"⚠ Object {i}: used fallback placement")
            else:
                print(f"✗ Object {i}: no surface points available")

    return packed_positions


def conform_objects_to_surface(objects, object_bounds, cursor_matrix, surface_objects):
    """Apply surface conforming to objects using raycast"""
    if not objects or not surface_objects:
        return

    print(f"Conforming {len(objects)} objects to {len(surface_objects)} surface objects")
    print(f"Surface objects: {[obj.name for obj in surface_objects]}")

    # Get cursor normal (Z-axis of cursor matrix)
    cursor_normal = cursor_matrix.to_3x3() @ mathutils.Vector((0, 0, 1))
    cursor_normal.normalize()
    cursor_location = cursor_matrix.translation
    print(f"3D Cursor location: {cursor_location}")
    print(f"3D Cursor normal: {cursor_normal}")

    # Temporarily hide the objects we're positioning so they don't interfere with raycast
    hidden_positioned_objects = []
    for obj in objects:
        if obj and not obj.hide_viewport:
            obj.hide_viewport = True
            hidden_positioned_objects.append(obj)
    print(f"Temporarily hid {len(hidden_positioned_objects)} positioned objects for raycasting")

    # Get depsgraph for raycasting
    depsgraph = bpy.context.evaluated_depsgraph_get()

    for i, obj in enumerate(objects):
        if not obj:
            continue

        bounds = object_bounds[i] if i < len(object_bounds) else (2.0, 2.0, 2.0)

        # Get object's position in cursor space, then project onto cursor's XY plane
        # Transform object location to cursor local space
        cursor_matrix_inv = cursor_matrix.inverted()
        local_position = cursor_matrix_inv @ obj.location

        # Keep XY in cursor space, zero out Z
        local_xy = mathutils.Vector((local_position.x, local_position.y, 0))

        # Transform back to world space for raycasting
        world_xy_position = cursor_matrix @ local_xy
        print(f"Object position in cursor space: {local_position}")
        print(f"Projected to cursor XY plane: {world_xy_position}")

        # Try raycasting downward first
        raycast_start_down = world_xy_position + cursor_normal * 100
        raycast_direction_down = -cursor_normal
        print(f"Raycast DOWN: start={raycast_start_down}, direction={raycast_direction_down}")
        hit_down, hit_location_down, hit_normal_down, face_index_down, hit_object_down, hit_matrix_down = bpy.context.scene.ray_cast(
            depsgraph, raycast_start_down, raycast_direction_down
        )
        print(f"Raycast DOWN result: hit={hit_down}, location={hit_location_down}, normal={hit_normal_down}, object={hit_object_down.name if hit_object_down else None}")

        # Try raycasting upward
        raycast_start_up = world_xy_position - cursor_normal * 100
        raycast_direction_up = cursor_normal
        print(f"Raycast UP: start={raycast_start_up}, direction={raycast_direction_up}")
        hit_up, hit_location_up, hit_normal_up, face_index_up, hit_object_up, hit_matrix_up = bpy.context.scene.ray_cast(
            depsgraph, raycast_start_up, raycast_direction_up
        )
        print(f"Raycast UP result: hit={hit_up}, location={hit_location_up}, normal={hit_normal_up}, object={hit_object_up.name if hit_object_up else None}")

        # Use the closest hit
        if hit_down and hit_up:
            # Use the hit that's closer to the object's current position
            dist_down = (hit_location_down - obj.location).length
            dist_up = (hit_location_up - obj.location).length
            if dist_down <= dist_up:
                hit_location = hit_location_down
                hit_normal = hit_normal_down
            else:
                hit_location = hit_location_up
                hit_normal = hit_normal_up
        elif hit_down:
            hit_location = hit_location_down
            hit_normal = hit_normal_down
        elif hit_up:
            hit_location = hit_location_up
            hit_normal = hit_normal_up
        else:
            print(f"No surface hit for object {obj.name}")
            continue

        # Calculate offset to place object ON the surface (not embedded)
        height_offset = bounds[2] / 2

        # First, rotate object to align with surface normal
        object_up = mathutils.Vector((0, 0, 1))  # Object's local up vector

        # Calculate rotation to align object's up with surface normal
        rotation_quat = object_up.rotation_difference(hit_normal)
        obj.rotation_euler = rotation_quat.to_euler()

        # Then, position object so its bottom sits ON the surface
        # The hit_location is where the surface is, so we offset the object's center
        # upward by half its height along the surface normal
        offset_vector = hit_normal * height_offset
        obj.location = hit_location + offset_vector

    # Restore visibility of positioned objects
    for obj in hidden_positioned_objects:
        obj.hide_viewport = False

# Scene properties to store imported objects data between operators
class DumbToolsSceneProperties(bpy.types.PropertyGroup):
    imported_object_names: bpy.props.StringProperty(
        name="Imported Object Names",
        description="Comma-separated list of imported object names",
        default=""
    )
    cursor_location: bpy.props.FloatVectorProperty(
        name="Cursor Location",
        description="3D cursor location when objects were imported",
        size=3,
        default=(0.0, 0.0, 0.0)
    )
    cursor_rotation: bpy.props.FloatVectorProperty(
        name="Cursor Rotation",
        description="3D cursor rotation when objects were imported",
        size=3,
        default=(0.0, 0.0, 0.0)
    )
    object_bounds_data: bpy.props.StringProperty(
        name="Object Bounds Data",
        description="JSON string containing bounding box data for each object",
        default=""
    )
    initial_random_seed: bpy.props.IntProperty(
        name="Initial Random Seed",
        description="Random seed used during import",
        default=1
    )

    # UI control for Asset Browser panel
    show_scattering_settings: bpy.props.BoolProperty(
        name="Show Scattering Settings",
        description="Show/hide scattering settings in Asset Browser panel",
        default=False
    )

    # Scattering settings for Asset Browser panel
    scattering_method: bpy.props.EnumProperty(
        name="Scattering Method",
        description="Choose the scattering algorithm",
        items=[
            ('GRID', "Grid Packing", "Smart bin-packed grid layout"),
            ('CIRCLE', "Circle Packing", "Pack circles tightly together without overlap"),
            ('SPIRAL', "Fibonacci Spiral", "Arrange in golden ratio spiral"),
            ('VERTICAL_STACK', "Vertical Stack", "Stack objects vertically"),
            ('POISSON_DISK', "Poisson Disk", "Even distribution using Poisson disk sampling"),
            ('NFP', "NFP Packing", "No Fit Polygon - industry standard for irregular shapes"),
            ('SURFACE_PACK', "Surface Packing", "Adaptive packing on irregular surfaces with even spacing"),
        ],
        default='GRID'
    )

    object_order: bpy.props.EnumProperty(
        name="Object Order",
        description="How to order objects before scattering",
        items=[
            ('RANDOM', "Random", "Random order based on seed"),
            ('SIZE_LARGE_FIRST', "Size: Large First", "Order by volume, largest objects first"),
            ('SIZE_SMALL_FIRST', "Size: Small First", "Order by volume, smallest objects first"),
        ],
        default='RANDOM'
    )

    grid_spacing: bpy.props.FloatProperty(
        name="Grid Spacing",
        description="Extra spacing between objects in grid layout",
        default=0.1,
        min=0.0,
        max=10.0,
        step=0.01,
        precision=3
    )

    circle_spacing: bpy.props.FloatProperty(
        name="Circle Spacing",
        description="Extra spacing between circles in circle packing",
        default=0.1,
        min=0.0,
        max=5.0,
        step=0.01,
        precision=3
    )

    spiral_density: bpy.props.FloatProperty(
        name="Spiral Density",
        description="Density of spiral pattern (lower = more spread out)",
        default=0.8,
        min=0.01,
        max=5.0,
        step=0.01,
        precision=3
    )

    nfp_spacing: bpy.props.FloatProperty(
        name="NFP Spacing",
        description="Minimum spacing between objects in NFP packing",
        default=0.1,
        min=0.0,
        max=5.0,
        step=0.01,
        precision=3
    )

    surface_pack_spacing: bpy.props.FloatProperty(
        name="Surface Spacing",
        description="Minimum spacing between objects in surface packing",
        default=0.1,
        min=0.0,
        max=5.0,
        step=0.01,
        precision=3
    )

    surface_pack_density: bpy.props.FloatProperty(
        name="Surface Density",
        description="Density of surface sampling (higher = more sample points)",
        default=1.0,
        min=0.1,
        max=10.0,
        step=0.1,
        precision=2
    )

    random_seed: bpy.props.IntProperty(
        name="Random Seed",
        description="Seed for randomizing object order (change to get different arrangements)",
        default=1,
        min=1,
        max=9999
    )

    grid_rows: bpy.props.IntProperty(
        name="Grid Rows",
        description="Number of rows in grid layout (0 = auto-calculate)",
        default=0,
        min=0,
        max=20
    )

    poisson_min_distance: bpy.props.FloatProperty(
        name="Min Distance",
        description="Minimum distance between objects (based on object size)",
        default=0.1,
        min=0.001,
        max=5.0,
        step=0.001,
        precision=4
    )

    poisson_area_size: bpy.props.FloatProperty(
        name="Area Size",
        description="Size of the distribution area",
        default=1.0,
        min=0.01,
        max=50.0,
        step=0.01,
        precision=3
    )

    conform_to_surface: bpy.props.BoolProperty(
        name="Conform to Selected Surface(s)",
        description="Raycast objects to conform to selected surface geometry along 3D cursor's Z normal",
        default=False
    )

class DUMBTOOLS_OT_browse_asset_folder(Operator, ImportHelper):
    """Select a folder to use as an asset library"""
    bl_idname = "dumbtools.browse_asset_folder"
    bl_label = "Browse Asset Folder"
    
    # Set up the file browser to select directories only
    directory: bpy.props.StringProperty(
        name="Directory",
        subtype='DIR_PATH'
    )
    
    filename_ext = ""
    use_filter_folder = True
    
    def execute(self, context):
        # Check if 'DumbAssets' library already exists
        if 'DumbAssets' not in bpy.context.preferences.filepaths.asset_libraries:
            # Create new asset library using the operator
            bpy.ops.preferences.asset_library_add()
            # Get reference to the newly added library
            new_lib = bpy.context.preferences.filepaths.asset_libraries[-1]
            new_lib.name = 'DumbAssets'
        
        # Get the library (either existing or newly created)
        lib = bpy.context.preferences.filepaths.asset_libraries['DumbAssets']
        
        # Set the path
        lib.path = self.directory
        
        # Switch the asset browser to the DumbAssets library
        context.space_data.params.asset_library_reference = 'DumbAssets'
        
        return {'FINISHED'}


class DUMBTOOLS_OT_import_assets(Operator):
    """Import multiple selected assets from the asset browser and scatter them around the 3D cursor"""
    bl_idname = "dumbtools.import_assets"
    bl_label = "Scatter Selected Assets"
    bl_description = "Import and scatter selected assets around the 3D cursor using the chosen scattering method"
    bl_options = {'REGISTER'}  # Simple register, no undo needed





    @classmethod
    def poll(cls, context):
        # Available in 3D View or Asset Browser with selected assets
        if context.space_data and context.space_data.type == 'VIEW_3D':
            # In 3D View, always available (will use clipboard or prompt user)
            return True
        elif (context.space_data and
              context.space_data.type == 'FILE_BROWSER' and
              context.space_data.browse_mode == 'ASSETS' and
              hasattr(context, 'selected_assets') and
              context.selected_assets is not None and
              len(context.selected_assets) > 0):
            # In Asset Browser, only when assets are selected
            return True
        return False
    
    def invoke(self, context, event):
        # Detect modifier key combinations for different scattering methods
        # Only override scene properties if modifier keys are pressed
        scene_props = context.scene.dumbtools_props
        ctrl = event.ctrl
        alt = event.alt
        shift = event.shift

        # Only set scattering method if modifier keys are pressed (for quick access)
        if ctrl:
            # Ctrl only = Vertical stack
            scene_props.scattering_method = 'VERTICAL_STACK'
            print("Modifier override: Vertical Stack")
        elif alt:
            # Alt only = Circle packing
            scene_props.scattering_method = 'CIRCLE'
            print("Modifier override: Circle Packing")
        elif shift:
            # Shift only = Fibonacci spiral
            scene_props.scattering_method = 'SPIRAL'
            print("Modifier override: Spiral")
        # No else clause - use whatever is set in the UI panel!

        return self.execute(context)

    def execute(self, context):
        print(f"=== IMPORT ASSETS EXECUTE ===")

        # Capture current selection for surface conforming
        original_selection = [obj for obj in context.selected_objects]
        original_active = context.active_object
        print(f"Captured selection: {len(original_selection)} objects")

        # Get scattering settings from scene properties
        scene_props = context.scene.dumbtools_props
        scattering_method = scene_props.scattering_method

        print(f"Using scattering method: {scattering_method}")
        print(f"Grid rows: {scene_props.grid_rows}")
        print(f"Grid spacing: {scene_props.grid_spacing}")
        print(f"Object order: {scene_props.object_order}")

        # Simple - we're in Asset Browser context
        selected_assets = context.selected_assets

        # Note: Asset selection is preserved by the Asset Browser automatically

        if not selected_assets:
            self.report({'WARNING'}, "No assets selected. Please select assets in the Asset Browser first")
            return {'CANCELLED'}

        print(f"Found {len(selected_assets)} selected assets")

        # Get the 3D cursor location and rotation
        cursor_location = context.scene.cursor.location.copy()
        cursor_rotation = context.scene.cursor.rotation_euler.copy()
        cursor_matrix = mathutils.Matrix.Translation(cursor_location) @ cursor_rotation.to_matrix().to_4x4()

        # Get import method from current asset browser context
        asset_import_method = 'APPEND'  # Default fallback

        if hasattr(context.space_data, 'params') and hasattr(context.space_data.params, 'import_method'):
            raw_import_method = context.space_data.params.import_method

            # Handle "Follow Preferences" case
            if raw_import_method == 'FOLLOW_PREFS':
                # Get the preference setting
                prefs = context.preferences.filepaths
                if hasattr(prefs, 'asset_import_method'):
                    asset_import_method = prefs.asset_import_method
                else:
                    asset_import_method = 'APPEND'  # Default fallback
            else:
                asset_import_method = raw_import_method
        else:
            # Try alternative method to get asset browser settings
            for area in context.screen.areas:
                if area.type == 'FILE_BROWSER':
                    for space in area.spaces:
                        if space.type == 'FILE_BROWSER' and hasattr(space, 'params'):
                            if hasattr(space.params, 'import_method'):
                                asset_import_method = space.params.import_method
                                break

        imported_count = 0
        failed_count = 0

        print(f"Found {len(selected_assets)} selected assets")

        asset_index = 0
        imported_objects = []  # Track imported objects for bounding box calculation

        for asset in selected_assets:
            try:
                # Use Blender's Asset API - we have full_library_path available!
                print(f"Asset: {asset.name}")

                # Get the blend file path directly from the asset
                blend_file_path = None

                if hasattr(asset, 'full_library_path'):
                    blend_file_path = asset.full_library_path
                    print(f"Found blend file: {blend_file_path}")
                elif hasattr(asset, 'full_path'):
                    blend_file_path = asset.full_path
                    print(f"Found full path: {blend_file_path}")

                if not blend_file_path or not os.path.exists(blend_file_path):
                    self.report({'WARNING'}, f"Could not find blend file for asset: {asset.name}")
                    failed_count += 1
                    continue

                # Debug print (can be removed)
                # print(f"Importing asset: {asset.name} from {blend_file_path}")
                # print(f"Asset ID type: {asset.id_type}")
                # print(f"Import method: {import_method}")
                
                # Import the asset based on the import method
                imported_obj = None
                if asset_import_method == 'LINK':
                    imported_obj = self.link_asset(blend_file_path, asset)
                elif asset_import_method == 'APPEND_REUSE':
                    imported_obj = self.append_asset(blend_file_path, asset, reuse_data=True)
                else:  # 'APPEND' or default
                    imported_obj = self.append_asset(blend_file_path, asset, reuse_data=False)
                
                if imported_obj:
                    imported_objects.append(imported_obj)
                    imported_count += 1
                    asset_index += 1  # Only increment if successful
                else:
                    failed_count += 1
                    
            except Exception as e:
                self.report({'WARNING'}, f"Failed to import asset {asset.name}: {str(e)}")
                failed_count += 1
        
        # Store objects and enhanced data in scene properties
        if imported_objects:
            # Reset all imported objects to origin before scattering
            print(f"Resetting {len(imported_objects)} objects to origin...")
            for obj in imported_objects:
                if obj:
                    # Make linked objects local so we can transform them
                    if obj.library:
                        print(f"Making linked object local: {obj.name}")
                        obj.make_local()

                    # Reset location and rotation
                    obj.location = (0, 0, 0)
                    obj.rotation_euler = (0, 0, 0)
                    obj.scale = (1, 1, 1)  # Also reset scale for consistency
                    print(f"Reset object: {obj.name}")

            # Store object names
            scene_props = context.scene.dumbtools_props
            object_names = [obj.name for obj in imported_objects if obj]
            scene_props.imported_object_names = ','.join(object_names)

            # Store cursor transform
            scene_props.cursor_location = cursor_location
            scene_props.cursor_rotation = cursor_rotation

            # Calculate and store bounding box data
            bounds_data = []
            for obj in imported_objects:
                if obj and obj.type in {'MESH', 'CURVE', 'SURFACE', 'META', 'FONT', 'EMPTY'}:
                    # Use local bounding box (without world transformation) to avoid issues with reused objects
                    bbox = [mathutils.Vector(corner) for corner in obj.bound_box]
                    min_x = min(corner.x for corner in bbox)
                    max_x = max(corner.x for corner in bbox)
                    min_y = min(corner.y for corner in bbox)
                    max_y = max(corner.y for corner in bbox)
                    min_z = min(corner.z for corner in bbox)
                    max_z = max(corner.z for corner in bbox)

                    bounds_data.append({
                        "name": obj.name,
                        "width": max_x - min_x,
                        "height": max_y - min_y,
                        "depth": max_z - min_z
                    })
                else:
                    bounds_data.append({
                        "name": obj.name,
                        "width": 2.0,
                        "height": 2.0,
                        "depth": 2.0
                    })

            # Store bounds data as JSON
            scene_props.object_bounds_data = json.dumps(bounds_data)

            # Store initial random seed
            import time
            scene_props.initial_random_seed = int(time.time() * 1000) % 9999 + 1

            print(f"Stored {len(object_names)} objects with bounds data in scene properties")

            # Position objects using scene property settings
            print(f"Positioning objects using {scattering_method}")

            # Calculate assets per row for grid layout
            total_assets = len(imported_objects)
            if scene_props.grid_rows > 0:
                assets_per_row = max(1, int(math.ceil(total_assets / scene_props.grid_rows)))
            else:
                assets_per_row = max(1, int(math.ceil(math.sqrt(total_assets))))

            # Position objects using selected scattering method
            position_objects_with_layout(imported_objects, bounds_data, cursor_matrix, assets_per_row, scene_props, original_selection)

        # Report results
        if imported_count > 0:
            self.report({'INFO'}, f"Successfully imported {imported_count} assets")
        if failed_count > 0:
            self.report({'WARNING'}, f"Failed to import {failed_count} assets")

        # Restore original selection
        bpy.ops.object.select_all(action='DESELECT')
        for obj in original_selection:
            if obj and obj.name in bpy.data.objects:
                obj.select_set(True)
        if original_active and original_active.name in bpy.data.objects:
            context.view_layer.objects.active = original_active
        print(f"Restored selection: {len(original_selection)} objects")

        return {'FINISHED'}

    def link_asset(self, blend_file_path, asset):
        """Link an asset from a blend file and return the main object"""
        try:
            asset_name = asset.name
            asset_id_type = asset.id_type

            # Map asset ID types to their directory names in blend files
            type_mapping = {
                'OBJECT': 'Object',
                'MATERIAL': 'Material',
                'MESH': 'Mesh',
                'COLLECTION': 'Collection',
                'NODE_TREE': 'NodeTree',
                'IMAGE': 'Image',
                'TEXTURE': 'Texture'
            }

            if asset_id_type not in type_mapping:
                return None

            directory = type_mapping[asset_id_type]

            # Link the asset
            bpy.ops.wm.link(
                filepath=os.path.join(blend_file_path, directory, asset_name),
                directory=os.path.join(blend_file_path, directory) + os.sep,
                filename=asset_name
            )

            # Return the appropriate object for positioning
            if asset_id_type == 'OBJECT' and asset_name in bpy.data.objects:
                obj = bpy.data.objects[asset_name]
                # Add to scene if not already there
                if obj.name not in bpy.context.scene.collection.objects:
                    bpy.context.scene.collection.objects.link(obj)
                return obj
            elif asset_id_type == 'COLLECTION' and asset_name in bpy.data.collections:
                # Create an empty to instance the collection
                empty = bpy.data.objects.new(f"{asset_name}_instance", None)
                empty.instance_type = 'COLLECTION'
                empty.instance_collection = bpy.data.collections[asset_name]
                bpy.context.scene.collection.objects.link(empty)
                return empty

            return None  # For non-object assets like materials, images, etc.

        except Exception as e:
            print(f"Error linking asset {asset.name}: {e}")
            return None

    def append_asset(self, blend_file_path, asset, reuse_data=False):
        """Append an asset from a blend file and return the main object"""
        try:
            asset_name = asset.name
            asset_id_type = asset.id_type

            # Map asset ID types to their directory names in blend files
            type_mapping = {
                'OBJECT': 'Object',
                'MATERIAL': 'Material',
                'MESH': 'Mesh',
                'COLLECTION': 'Collection',
                'NODE_TREE': 'NodeTree',
                'IMAGE': 'Image',
                'TEXTURE': 'Texture'
            }

            if asset_id_type not in type_mapping:
                return None

            directory = type_mapping[asset_id_type]

            # Track existing objects before import
            existing_objects = set(bpy.data.objects.keys())
            existing_collections = set(bpy.data.collections.keys())

            # Import the asset using the detected method
            filepath = os.path.join(blend_file_path, directory, asset_name)
            directory_path = os.path.join(blend_file_path, directory) + os.sep

            print(f"Appending asset with reuse_data={reuse_data}: {asset_name}")
            bpy.ops.wm.append(
                filepath=filepath,
                directory=directory_path,
                filename=asset_name,
                do_reuse_local_id=reuse_data
            )

            # Find the newly appended object
            if asset_id_type == 'OBJECT':
                new_objects = set(bpy.data.objects.keys()) - existing_objects
                if new_objects:
                    # Get the newly appended object
                    new_obj_name = list(new_objects)[0]  # Should be only one
                    obj = bpy.data.objects[new_obj_name]
                    print(f"Found newly appended object: {new_obj_name}")
                    # Add to scene if not already there
                    if obj.name not in bpy.context.scene.collection.objects:
                        bpy.context.scene.collection.objects.link(obj)
                    return obj
                elif asset_name in bpy.data.objects:
                    # Fallback to original method if no new objects detected
                    obj = bpy.data.objects[asset_name]
                    if obj.name not in bpy.context.scene.collection.objects:
                        bpy.context.scene.collection.objects.link(obj)
                    return obj
            elif asset_id_type == 'COLLECTION':
                new_collections = set(bpy.data.collections.keys()) - existing_collections
                if new_collections:
                    new_collection_name = list(new_collections)[0]
                    collection = bpy.data.collections[new_collection_name]
                    print(f"Found newly appended collection: {new_collection_name}")
                elif asset_name in bpy.data.collections:
                    collection = bpy.data.collections[asset_name]
                else:
                    return None

                # Create an empty to instance the collection
                empty = bpy.data.objects.new(f"{collection.name}_instance", None)
                empty.instance_type = 'COLLECTION'
                empty.instance_collection = collection
                bpy.context.scene.collection.objects.link(empty)
                return empty

            return None  # For non-object assets like materials, images, etc.

        except Exception as e:
            print(f"Error appending asset {asset.name}: {e}")
            return None

    def import_asset_follow_prefs(self, blend_file_path, asset):
        """Import asset following user preferences"""
        # Check the actual user preferences for asset import method
        prefs = bpy.context.preferences
        if hasattr(prefs, 'filepaths') and hasattr(prefs.filepaths, 'asset_import_method'):
            pref_method = prefs.filepaths.asset_import_method
            print(f"User preference asset import method: {pref_method}")

            if pref_method == 'APPEND_REUSE':
                return self.append_asset(blend_file_path, asset)
            elif pref_method == 'LINK':
                return self.link_asset(blend_file_path, asset)
            else:
                # Default fallback
                print(f"Unknown preference method {pref_method}, defaulting to append")
                return self.append_asset(blend_file_path, asset)
        else:
            # Fallback if preferences not found
            print("Asset import preferences not found, defaulting to append")
            return self.append_asset(blend_file_path, asset)





class DUMBTOOLS_OT_rescatter_selected(Operator):
    """Re-scatter selected scene objects using current scattering settings"""
    bl_idname = "dumbtools.rescatter_selected"
    bl_label = "Re-Scatter Selected Scene Objects"
    bl_description = "Re-scatter currently selected objects using the current scattering method and settings"
    bl_options = {'REGISTER', 'UNDO'}

    @classmethod
    def poll(cls, context):
        # Re-scatter operator has different poll requirements than main import
        # Just check if we're in asset browser mode
        return (context.space_data and
                context.space_data.type == 'FILE_BROWSER' and
                context.space_data.browse_mode == 'ASSETS')

    def execute(self, context):
        print("=== RE-SCATTER SELECTED EXECUTE ===")

        # Get selected assets from asset browser
        selected_assets = context.selected_assets if hasattr(context, 'selected_assets') else []
        if not selected_assets:
            self.report({'WARNING'}, "No assets selected in Asset Browser. Please select assets to find matching scene objects.")
            return {'CANCELLED'}

        # Find matching objects in the scene based on asset names
        objects_to_scatter = []
        for asset in selected_assets:
            asset_name = asset.name
            # Try to find object with exact name or similar name in scene
            if asset_name in bpy.data.objects:
                obj = bpy.data.objects[asset_name]
                if obj.type in {'MESH', 'CURVE', 'SURFACE', 'META', 'FONT', 'EMPTY'}:
                    objects_to_scatter.append(obj)
                    print(f"Found matching scene object: {asset_name}")
            else:
                print(f"No matching scene object found for asset: {asset_name}")

        if not objects_to_scatter:
            self.report({'WARNING'}, "No matching scene objects found for selected assets.")
            return {'CANCELLED'}

        print(f"Re-scattering {len(objects_to_scatter)} matching scene objects")

        # Use 3D viewport selection as surface objects for conforming
        surface_objects = [obj for obj in context.selected_objects if obj not in objects_to_scatter]
        print(f"Using {len(surface_objects)} viewport-selected objects as surface targets")

        # Get scattering settings from scene properties
        scene_props = context.scene.dumbtools_props

        print(f"Using scattering method: {scene_props.scattering_method}")

        # Get the 3D cursor location and rotation
        cursor_location = context.scene.cursor.location.copy()
        cursor_rotation = context.scene.cursor.rotation_euler.copy()
        cursor_matrix = mathutils.Matrix.Translation(cursor_location) @ cursor_rotation.to_matrix().to_4x4()

        # Reset all objects to scatter to origin before scattering
        print(f"Resetting {len(objects_to_scatter)} objects to origin...")
        for obj in objects_to_scatter:
            obj.location = (0, 0, 0)
            obj.rotation_euler = (0, 0, 0)
            obj.scale = (1, 1, 1)

        # Calculate bounding box data for objects to scatter
        bounds_data = []
        for obj in objects_to_scatter:
            # Use local bounding box
            bbox = [mathutils.Vector(corner) for corner in obj.bound_box]
            min_x = min(corner.x for corner in bbox)
            max_x = max(corner.x for corner in bbox)
            min_y = min(corner.y for corner in bbox)
            max_y = max(corner.y for corner in bbox)
            min_z = min(corner.z for corner in bbox)
            max_z = max(corner.z for corner in bbox)

            bounds_data.append({
                "name": obj.name,
                "width": max_x - min_x,
                "height": max_y - min_y,
                "depth": max_z - min_z
            })

        # Calculate assets per row for grid-based methods
        total_objects = len(objects_to_scatter)
        if scene_props.scattering_method in ['GRID', 'GRID_RANDOM'] and scene_props.grid_rows > 0:
            assets_per_row = max(1, int(math.ceil(total_objects / scene_props.grid_rows)))
        else:
            assets_per_row = max(1, int(math.ceil(math.sqrt(total_objects))))

        # Use the same positioning logic as the main import operator
        position_objects_with_layout(objects_to_scatter, bounds_data, cursor_matrix, assets_per_row, scene_props, surface_objects)

        self.report({'INFO'}, f"Successfully re-scattered {len(objects_to_scatter)} objects")
        return {'FINISHED'}


class DUMBTOOLS_PT_asset_browser_tools(Panel):
    """Panel in Asset Browser's tools region"""
    bl_space_type = 'FILE_BROWSER'
    bl_region_type = 'TOOLS'
    bl_category = "Tool"
    bl_label = "DumbTools"

    @classmethod
    def poll(cls, context):
        # Only show in asset browser mode
        return context.space_data.browse_mode == 'ASSETS'

    def draw(self, context):
        layout = self.layout
        scene_props = context.scene.dumbtools_props

        # Browse Asset Folder button
        layout.operator("dumbtools.browse_asset_folder", text="Browse Asset Folder")

        # Import button - always show, let operator handle validation
        layout.separator()

        # Asset import button - let the operator's poll method handle validation
        layout.operator("dumbtools.import_assets", text="Scatter Selected Assets")

        # Scattering Settings (collapsed by default) - BELOW the button
        layout.separator()

        box = layout.box()
        col = box.column()

        # Header with expand/collapse
        row = col.row()
        row.prop(scene_props, "show_scattering_settings",
                icon="TRIA_DOWN" if scene_props.show_scattering_settings else "TRIA_RIGHT",
                icon_only=True, emboss=False)
        row.label(text="Scattering Settings")

        # Show settings if expanded
        if scene_props.show_scattering_settings:
            col.separator()

            # Main scattering method
            col.prop(scene_props, "scattering_method")
            col.separator()

            # Object ordering
            col.prop(scene_props, "object_order")

            # Show random seed only when using random order
            if scene_props.object_order == 'RANDOM':
                col.prop(scene_props, "random_seed")

            col.separator()

            # Method-specific settings
            if scene_props.scattering_method == 'GRID':
                col.prop(scene_props, "grid_rows")
                col.prop(scene_props, "grid_spacing")
            elif scene_props.scattering_method == 'CIRCLE':
                col.prop(scene_props, "circle_spacing")
            elif scene_props.scattering_method == 'SPIRAL':
                col.prop(scene_props, "spiral_density")
            elif scene_props.scattering_method == 'POISSON_DISK':
                col.prop(scene_props, "poisson_min_distance")
                col.prop(scene_props, "poisson_area_size")
            elif scene_props.scattering_method == 'NFP':
                if SHAPELY_AVAILABLE:
                    col.prop(scene_props, "nfp_spacing")
                else:
                    col.label(text="Shapely installing... restart Blender", icon='INFO')
            elif scene_props.scattering_method == 'SURFACE_PACK':
                col.prop(scene_props, "surface_pack_spacing")
                col.prop(scene_props, "surface_pack_density")
                col.label(text="Select surface objects before scattering", icon='INFO')
            else:
                # Other grid-based methods (VERTICAL_STACK)
                col.prop(scene_props, "grid_spacing")

            # Surface conforming option (not needed for SURFACE_PACK - it's built-in)
            if scene_props.scattering_method != 'SURFACE_PACK':
                layout.separator()
                layout.prop(scene_props, "conform_to_surface")

            # Re-scatter button for scene objects
            layout.separator()
            layout.operator("dumbtools.rescatter_selected", text="Re-Scatter Selected Scene Objects")





def register():
    # Register scene properties first
    bpy.utils.register_class(DumbToolsSceneProperties)
    bpy.types.Scene.dumbtools_props = bpy.props.PointerProperty(type=DumbToolsSceneProperties)

    # Register operators
    bpy.utils.register_class(DUMBTOOLS_OT_browse_asset_folder)
    bpy.utils.register_class(DUMBTOOLS_OT_import_assets)
    bpy.utils.register_class(DUMBTOOLS_OT_rescatter_selected)
    bpy.utils.register_class(DUMBTOOLS_PT_asset_browser_tools)

    print("DumbAssets Asset Browser Panel System registered successfully!")


def unregister():
    # Unregister operators
    bpy.utils.unregister_class(DUMBTOOLS_PT_asset_browser_tools)
    bpy.utils.unregister_class(DUMBTOOLS_OT_rescatter_selected)
    bpy.utils.unregister_class(DUMBTOOLS_OT_import_assets)
    bpy.utils.unregister_class(DUMBTOOLS_OT_browse_asset_folder)

    # Unregister scene properties
    del bpy.types.Scene.dumbtools_props
    bpy.utils.unregister_class(DumbToolsSceneProperties)

    print("DumbAssets Two-Operator System unregistered successfully!")


register()
