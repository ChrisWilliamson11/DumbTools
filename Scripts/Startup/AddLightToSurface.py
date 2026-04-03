# Tooltip: This script will add a light to the surface you click on.
import bpy
import bmesh
from bpy.props import FloatProperty, FloatVectorProperty, EnumProperty
from bpy_extras import view3d_utils
from mathutils import Vector

def get_view_ray(context, event):
    # Ensure that the context's space data is from a 3D view
    if context.area.type == 'VIEW_3D':
        region = context.region
        rv3d = context.space_data.region_3d
        coord = event.mouse_region_x, event.mouse_region_y
        view_vector = view3d_utils.region_2d_to_vector_3d(region, rv3d, coord)
        ray_origin = view3d_utils.region_2d_to_origin_3d(region, rv3d, coord)
        return ray_origin, view_vector
    else:
        # Return None or raise an error if the context is not from a 3D view
        return None, None, None


def ray_cast(context, event):
    ray_origin, view_vector = get_view_ray(context, event)  # Pass the standard context

    # Get the depsgraph from the context
    depsgraph = context.evaluated_depsgraph_get()

    # Perform the ray cast using the depsgraph
    result, location, normal, index, object, matrix = context.scene.ray_cast(depsgraph, ray_origin, view_vector)
    #print("Ray cast result:", result, "Location:", location, "Normal:", normal)  # Debugging line
    return result, location, normal


        
def get_3d_view_context():
    for area in bpy.context.screen.areas:
        if area.type == 'VIEW_3D':
            for region in area.regions:
                if region.type == 'WINDOW':
                    override_context = bpy.context.copy()
                    override_context['area'] = area
                    override_context['region'] = region
                    override_context['space_data'] = area.spaces.active
                    override_context['depsgraph'] = bpy.context.evaluated_depsgraph_get()  # Add this line
                    return override_context
    return None



class ModalLightPlacingOperator(bpy.types.Operator):
    bl_idname = "object.modal_lightplacingoperator"
    bl_label = "Add or Adjust Light"

    # Operator properties
    light_distance: FloatProperty(
        name="Distance",
        description="Distance of the light from the surface",
        default=2.0,
        min=0.1,
        max=10.0
    )
    light_size: FloatProperty(
        name="Size",
        description="Size of the light",
        default=1.0,
        min=0.1,
        max=10.0
    )
    light_color: FloatVectorProperty(
        name="Color",
        description="Color of the light",
        subtype='COLOR',
        min=0.0,
        max=1.0,
        default=(1.0, 1.0, 1.0)
    )
    light_shape: EnumProperty(
        name="Shape",
        description="Shape of the light",
        items=[
            ('SQUARE', "Square", ""),
            ('RECTANGLE', "Rectangle", ""),
            ('DISK', "Disk", ""),
            ('ELLIPSE', "Ellipse", "")
        ],
        default='SQUARE'
    )
    light_type: EnumProperty(
        name="Type",
        description="Type of the light",
        items=[
            ('POINT', "Point", ""),
            ('SUN', "Sun", ""),
            ('SPOT', "Spot", ""),
            ('AREA', "Area", "")
        ],
        default='AREA'
    )
    
    light_intensity: FloatProperty(
        name="Intensity",
        description="Intensity of the light",
        default=5.0,
        min=0.0,
        max=100000.0
    )

    # Class variables for state tracking
    mouse_held: bool = False
    operator_running: bool = False
    light_location = None
    light_normal = None
    last_mouse_x: int = 0

    def modal(self, context, event):
        if event.type == 'LEFTMOUSE':
            if event.value == 'PRESS':
                self.mouse_held = True
                self.last_mouse_x = event.mouse_x
                result, location, normal = ray_cast(context, event)
                if result:
                    self.light_location = location
                    self.light_normal = normal
                    if context.active_object and context.active_object.type == 'LIGHT' and context.active_object.select_get():
                        # Adjust based on the light type
                        light = context.active_object.data
                        if light.type == 'AREA':
                            self.light_size = light.size if light.shape != 'RECTANGLE' else light.size_x
                        elif light.type == 'POINT':
                            self.light_size = light.shadow_soft_size
                        elif light.type == 'SPOT':
                            self.light_size = light.spot_size
                        elif light.type == 'SUN':
                            self.light_size = light.angle
                        self.light_intensity = light.energy
                        self.light_distance = (context.active_object.location - location).length
                    self.create_or_adjust_light(context, location, normal)
            elif event.value == 'RELEASE':
                self.mouse_held = False
                context.window.cursor_modal_restore()
                return {'FINISHED'}
            return {'RUNNING_MODAL'}
        
        elif self.mouse_held and event.type == 'MOUSEMOVE':
            # Adjust distance or size based on modifier keys while dragging
            mouse_move_delta = event.mouse_x - self.last_mouse_x
            if event.shift:
                # Shift held: Adjust light intensity
                self.light_intensity += mouse_move_delta * 0.1
            elif event.ctrl:
                # Ctrl held: Adjust light distance
                self.light_distance += mouse_move_delta * 0.01
            elif event.alt:
                # Alt held: Adjust light size
                self.light_size += mouse_move_delta * 0.01
            else:
                # No modifier: Update light's position
                result, location, normal = ray_cast(context, event)
                if result:
                    self.light_location = location
                    self.light_normal = normal
            
            self.create_or_adjust_light(context, self.light_location, self.light_normal)
            self.last_mouse_x = event.mouse_x
            return {'RUNNING_MODAL'}

        elif self.operator_running and event.type == 'MOUSEMOVE':
            # Adjust distance or size based on modifier keys while dragging
            mouse_move_delta = event.mouse_x - self.last_mouse_x
            if event.shift:
                # Shift held: Adjust light intensity
                self.light_intensity += mouse_move_delta * 0.1
            elif event.ctrl:
                if context.active_object and context.active_object.type == 'LIGHT' and context.active_object.select_get():
                    context.active_object.location += context.active_object.matrix_world.to_quaternion() @ Vector((0, 0, mouse_move_delta * 0.01))
        
            elif event.alt:
                # Alt held: Adjust light size
                self.light_size += mouse_move_delta * 0.01
            else:
                # No modifier: Update light's position
                result, location, normal = ray_cast(context, event)
                if result:
                    self.light_location = location
                    self.light_normal = normal
            
            self.create_or_adjust_light(context, self.light_location, self.light_normal)
            self.last_mouse_x = event.mouse_x
            return {'RUNNING_MODAL'}

        elif event.type in {'RIGHTMOUSE', 'ESC'}:
            context.window.cursor_modal_restore()
            return {'CANCELLED'}

        return {'PASS_THROUGH'}



    def invoke(self, context, event):
        # Change the cursor to indicate interactive mode
        context.window.cursor_modal_set('CROSSHAIR')
        
        # Check if a light is active and selected
        if context.active_object and context.active_object.type == 'LIGHT' and context.active_object.select_get():
            self.operator_running = True
            self.last_mouse_x = event.mouse_x
            self.light_normal = context.active_object.rotation_euler.to_quaternion() @ Vector((0.0, 0.0, 1.0))
            
            # Initialize based on the type of light
            light = context.active_object.data
            if light.type == 'AREA':
                self.light_size = light.size if light.shape != 'RECTANGLE' else light.size_x
            elif light.type == 'POINT':
                self.light_size = light.shadow_soft_size
            elif light.type == 'SPOT':
                self.light_size = light.spot_size
            elif light.type == 'SUN':
                self.light_size = light.angle
            
            self.light_intensity = light.energy
            self.light_distance = context.active_object.location.length
        
        context.window_manager.modal_handler_add(self)
        return {'RUNNING_MODAL'}


    def create_or_adjust_light(self, context, location, normal):
        # View direction
        view_direction = context.region_data.view_rotation @ Vector((0.0, 0.0, -1.0))

        # Calculate the reflection vector
        reflection = view_direction - 2 * (view_direction.dot(normal)) * normal

        # Create or adjust the light
        if context.active_object and context.active_object.type == 'LIGHT' and context.active_object.select_get():
            light = context.active_object
        else:
            bpy.ops.object.light_add(type=self.light_type, location=location)
            light = context.active_object

        # Adjust light properties
        if self.mouse_held:
            # Adjust light location
            light.location = location + reflection.normalized() * self.light_distance
            # Point the light along the reflection vector
            light.rotation_mode = 'QUATERNION'
            light.rotation_quaternion = reflection.to_track_quat('Z', 'Y')
        
        # Adjust light type-specific properties
        if light.data.type == 'AREA':
            if self.light_shape == 'RECTANGLE':
                light.data.shape = 'RECTANGLE'
                light.data.size = self.light_size
                light.data.size_y = self.light_size * 0.5  # Example scaling, adjust as needed
            else:
                light.data.shape = self.light_shape
                light.data.size = self.light_size
        elif light.data.type == 'POINT':
            light.data.shadow_soft_size = self.light_size  # Point lights use shadow_soft_size instead of size
        elif light.data.type == 'SPOT':
            light.data.spot_size = self.light_size  # Spot lights use spot_size
            light.data.spot_blend = self.light_size * 0.1  # Adjust the blend based on size, adjust as needed
        elif light.data.type == 'SUN':
            light.data.angle = self.light_size * 0.1  # Sun lights use angle, scale as needed

        # Set common light properties
        light.data.color = self.light_color
        light.data.energy = self.light_intensity

        



def menu_draw(self, context):
    self.layout.operator(ModalLightPlacingOperator.bl_idname, text="Place Light on Surface", icon='LIGHT_AREA')

def register():
    try:
        bpy.utils.unregister_class(ModalLightPlacingOperator)
    except RuntimeError:
        pass
    bpy.utils.register_class(ModalLightPlacingOperator)
    bpy.types.VIEW3D_MT_light_add.append(menu_draw)

def unregister():
    bpy.utils.unregister_class(ModalLightPlacingOperator)
    bpy.types.VIEW3D_MT_light_add.remove(menu_draw)


register()
