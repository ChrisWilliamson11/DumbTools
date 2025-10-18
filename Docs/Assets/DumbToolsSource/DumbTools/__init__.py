import bpy
import os
import hashlib
from bpy.types import AddonPreferences
from bpy.props import BoolProperty
from bpy.app.handlers import persistent
import webbrowser

bl_info = {
    "name": "DumbTools",
    "author": "Chris Williamson",
    "version": (1, 0, 1),
    "blender": (3, 60, 0),
    "location": "View3D > Toolshelf > DumbTools",
    "description": "Executes scripts from a predefined folder",
    "warning": "",
    "wiki_url": "",
    "category": "Development",
    "default" : True,
}

CUSTOM_SCRIPTS_FOLDER =""
CUSTOM_STARTUP_FOLDER = ""
CUSTOM_POSTLOAD_FOLDER = ""


def script_folder_default():
    # Get the absolute path to Blender's configuration directory
    user_script_path = bpy.utils.user_resource('SCRIPTS', path="addons", create=True)
    default_folder = os.path.join(user_script_path, "DumbToolsScripts")
    if not os.path.exists(default_folder):
        os.makedirs(default_folder, exist_ok=True)
    return default_folder


SUBMENU_CLASSES = []
SCRIPT_OPERATORS = {}  # A dictionary to store the operator classes

def report_message(message, icon='INFO', title="DumbTools Notification"):
    def draw(self, context):
        self.layout.label(text=message)
    bpy.context.window_manager.popup_menu(draw, title=title, icon=icon)


class DumbToolsPreferences(bpy.types.AddonPreferences):
    bl_idname = "DumbTools"

    script_folder: bpy.props.StringProperty(
        name="Scripts Folder",
        description="Path to your scripts' folder",
        subtype='DIR_PATH',
        default=script_folder_default()
    )

    menu_name: bpy.props.StringProperty(
        name="Menu Name",
        description="Custom name for the DumbTools menu",
        default="DumbTools"
    )

    deadline_path: bpy.props.StringProperty(
        name="Deadline Command Path",
        description="Path to the Deadline command executable",
        subtype='FILE_PATH',
        default="\\\\wlgsrvrnd\\DeadlineRepository10\\bin\\Windows\\64bit\\deadlinecommand.exe"
    )

    def draw(self, context):
        layout = self.layout
        box = layout.box()
        box.prop(self, "script_folder")
        box.prop(self, "menu_name")
        box.prop(self, "deadline_path")
        #print (self.__annotations__.keys())
        for prop_name in self.__annotations__.keys():
            if prop_name.startswith("enable_"):
                box.prop(self, prop_name)

def register_properties(CUSTOM_SCRIPTS_FOLDER, CUSTOM_STARTUP_FOLDER, CUSTOM_POSTLOAD_FOLDER):
    CUSTOM_STARTUP_FOLDER = os.path.join(CUSTOM_SCRIPTS_FOLDER, "Startup")
    CUSTOM_POSTLOAD_FOLDER = os.path.join(CUSTOM_SCRIPTS_FOLDER, "PostLoad")

    # Adding properties using annotations
    for folder in [CUSTOM_STARTUP_FOLDER, CUSTOM_POSTLOAD_FOLDER]:
        if os.path.isdir(folder):
            for fname in sorted(os.listdir(folder)):
                if fname.endswith(".py"):
                    prop_name = f"enable_{fname.replace('.py', '')}"
                    DumbToolsPreferences.__annotations__[prop_name] = BoolProperty(
                        name=f"Enable {fname}",
                        default=True,
                        description=f"Enable or disable the execution of {fname} at startup/post load"
                    )
                    #print(f"Registered property for {fname} into annotations")
    # Attempt to re-register the class to force update
    bpy.utils.unregister_class(DumbToolsPreferences)
    bpy.utils.register_class(DumbToolsPreferences)


                            
class BaseScriptOperator(bpy.types.Operator):
    """Base operator for executing scripts."""
    bl_idname = "dumbtools.base_script_operator"
    bl_label = "Execute Script"  # Generic label for the base operator
    filepath: bpy.props.StringProperty()

    def execute(self, context):
        if not self.filepath:
            self.report({'ERROR'}, "No script path specified")
            return {'CANCELLED'}
        execute_script(self.filepath)
        return {'FINISHED'}

def register_script_operators():
    if os.path.isdir(CUSTOM_SCRIPTS_FOLDER):
        for subdir in os.scandir(CUSTOM_SCRIPTS_FOLDER):
            if subdir.is_dir() and subdir.name != "Startup" and subdir.name != "PostLoad":
                subfolder_path = subdir.path
                for fname in sorted(os.listdir(subfolder_path)):
                    if fname.endswith(".py"):
                        path = os.path.join(subfolder_path, fname)
                        tooltip = "Execute the script"  # Default tooltip
                        with open(path, 'r') as file:
                            first_line = file.readline().strip()
                            if first_line.startswith("# Tooltip:"):
                                tooltip = first_line[len("# Tooltip:"):].strip()
                        op_class = create_script_operator(path, tooltip)
                        # Store the operator class in the dictionary with the script path as key
                        SCRIPT_OPERATORS[path] = op_class

def get_operator_idname_from_path(path):
    # Retrieve the operator class from the dictionary and return its ID name
    op_class = SCRIPT_OPERATORS.get(path)
    if op_class:
        return op_class.bl_idname
    else:
        # print(f"No operator found for script: {path}")
        return ""
    
def create_script_operator(filepath, tooltip):
    # Hash the filepath to create a unique but short identifier
    hashed_name = hashlib.md5(filepath.encode()).hexdigest()[:10]

    # Create a unique class name based on the hashed filepath to avoid duplicates
    class_name = "OT_execute_" + hashed_name
    bl_idname = f"dumbtools.execute_{hashed_name}"
    bl_label = os.path.basename(filepath)[:-3]  # Specific label for this operator

    # Inherit from BaseScriptOperator
    op_class = type(
        class_name,
        (BaseScriptOperator,),
        {
            "bl_idname": bl_idname,
            "bl_label": bl_label,  # Use the specific label here
            "bl_description": tooltip,
            # 'filepath' property is already included in BaseScriptOperator
        }
    )

    # Register the operator class
    bpy.utils.register_class(op_class)

    return op_class

def create_submenus(base_path=None, parent_menu_idname=None):
    if base_path is None:
        base_path = CUSTOM_SCRIPTS_FOLDER

    if not os.path.isdir(base_path):
        # print(f"Invalid base path: {base_path}")
        return

    exclude_folders = {"Startup", "PostLoad", ".git", "Docs", ".vscode", "assets", "lib"}
    processed_menus = set()

    for folder_name in os.listdir(base_path):
        folder_path = os.path.join(base_path, folder_name)

        if not os.path.isdir(folder_path) or folder_name in exclude_folders:
            continue

        menu_idname = f"MENU_MT_{folder_name.replace(' ', '_').lower()}"

        if menu_idname in processed_menus:
            continue

        processed_menus.add(menu_idname)

        def create_draw_function(current_folder_path):
            def draw(self, context):
                layout = self.layout
                for fname in sorted(os.listdir(current_folder_path)):
                    file_path = os.path.join(current_folder_path, fname)
                    if os.path.isfile(file_path) and fname.endswith(".py"):
                        operator_idname = get_operator_idname_from_path(file_path)
                        if operator_idname:
                            op = layout.operator(operator_idname, text=fname[:-3])
                            op.filepath = file_path
                    elif os.path.isdir(file_path) and fname not in exclude_folders:
                        submenu_idname = f"MENU_MT_{fname.replace(' ', '_').lower()}"
                        layout.menu(submenu_idname)
            return draw

        menu_type = type(
            menu_idname,
            (bpy.types.Menu,),
            {
                "bl_idname": menu_idname,
                "bl_label": folder_name,
                "draw": create_draw_function(folder_path),
            }
        )

        bpy.utils.register_class(menu_type)
        SUBMENU_CLASSES.append(menu_type)

        create_submenus(folder_path, menu_idname)

def execute_script(filepath):
    if not filepath or not os.path.exists(filepath):
        # print(f"Invalid script path: {filepath}")
        return
        
    try:
        with open(filepath, 'r') as file:
            exec(compile(file.read(), filepath, 'exec'), {})
        # print(f"Executed '{filepath}' successfully.")
    except Exception as e:
        # print(f"Failed to execute '{filepath}': {e}")
        pass

class DumbToolsMenu(bpy.types.Menu):
    bl_idname = "DUMBTOOLS_MT_menu"
    bl_label = "DumbTools"  # Required attribute for Menu classes

    @classmethod
    def poll(cls, context):
        return True

    def draw(self, context):
        layout = self.layout
        
        exclude_folders = {"Startup", "PostLoad", ".git", "Docs", ".vscode", "assets", "lib"}
        
        if CUSTOM_SCRIPTS_FOLDER and os.path.isdir(CUSTOM_SCRIPTS_FOLDER):
            for folder_name in sorted(os.listdir(CUSTOM_SCRIPTS_FOLDER)):
                folder_path = os.path.join(CUSTOM_SCRIPTS_FOLDER, folder_name)
                if os.path.isdir(folder_path) and folder_name not in exclude_folders:
                    menu_idname = f"MENU_MT_{folder_name.replace(' ', '_').lower()}"
                    layout.menu(menu_idname)
            
            for fname in sorted(os.listdir(CUSTOM_SCRIPTS_FOLDER)):
                if fname.endswith(".py"):
                    path = os.path.join(CUSTOM_SCRIPTS_FOLDER, fname)
                    operator_idname = get_operator_idname_from_path(path)
                    if operator_idname:
                        op = layout.operator(operator_idname, text=fname[:-3])
                        op.filepath = path
        layout.operator("dumbtools.open_docs", text="DumbTools Docs")

class DumbToolsDocsOperator(bpy.types.Operator):
    """Open the DumbTools documentation."""
    bl_idname = "dumbtools.open_docs"
    bl_label = "DumbTools Documentation"

    @classmethod
    def poll(cls, context):
        # Check if the documentation file exists
        if CUSTOM_SCRIPTS_FOLDER:
            docs_path = os.path.join(os.path.dirname(CUSTOM_SCRIPTS_FOLDER), "Docs", "index.html")
            return os.path.exists(docs_path)

    def execute(self, context):
        if CUSTOM_SCRIPTS_FOLDER:
            docs_path = os.path.join(os.path.dirname(CUSTOM_SCRIPTS_FOLDER), "Docs", "index.html")
            webbrowser.open(f"file://{docs_path}")
            return {'FINISHED'}


def execute_startup_scripts():
    preferences = bpy.context.preferences.addons[__name__].preferences
    #print("Executing startup scripts...")
    if CUSTOM_STARTUP_FOLDER and os.path.isdir(CUSTOM_STARTUP_FOLDER):
        for fname in os.listdir(CUSTOM_STARTUP_FOLDER):
            prop_check = f"enable_{fname.replace('.py', '')}"
            if fname.endswith(".py") and getattr(preferences, prop_check, True):
                script_path = os.path.join(CUSTOM_STARTUP_FOLDER, fname)
                execute_script(script_path)
                
@persistent
def load_handler(dummy):
    preferences = bpy.context.preferences.addons[__name__].preferences
    #print("Running load handler for post-load scripts...")
    if CUSTOM_POSTLOAD_FOLDER and os.path.isdir(CUSTOM_POSTLOAD_FOLDER):
        for fname in os.listdir(CUSTOM_POSTLOAD_FOLDER):
            prop_check = f"enable_{fname.replace('.py', '')}"
            if fname.endswith(".py") and getattr(preferences, prop_check, True):
                script_path = os.path.join(CUSTOM_POSTLOAD_FOLDER, fname)
                execute_script(script_path)

# Function to draw the menu (this is the function you append to TOPBAR_MT_editor_menus)
def draw_dumbtools_menu(self, context):
    menu_name = context.preferences.addons[__name__].preferences.menu_name
    self.layout.menu(DumbToolsMenu.bl_idname, text=menu_name)
         
def register():
    bpy.utils.register_class(DumbToolsPreferences)
    global CUSTOM_SCRIPTS_FOLDER
    CUSTOM_SCRIPTS_FOLDER = bpy.context.preferences.addons[__name__].preferences.script_folder
    if not os.path.exists(CUSTOM_SCRIPTS_FOLDER):
        os.makedirs(CUSTOM_SCRIPTS_FOLDER, exist_ok=True)
    global CUSTOM_STARTUP_FOLDER, CUSTOM_POSTLOAD_FOLDER

    # Initialize the script folder paths correctly before registering properties

    CUSTOM_STARTUP_FOLDER = os.path.join(CUSTOM_SCRIPTS_FOLDER, "Startup")
    CUSTOM_POSTLOAD_FOLDER = os.path.join(CUSTOM_SCRIPTS_FOLDER, "PostLoad")

    # Check if the folders actually exist before proceeding
    if os.path.isdir(CUSTOM_SCRIPTS_FOLDER):
        # print(f"Custom scripts folder found: {CUSTOM_SCRIPTS_FOLDER}")
        register_properties(CUSTOM_SCRIPTS_FOLDER, CUSTOM_STARTUP_FOLDER, CUSTOM_POSTLOAD_FOLDER)
    else:
        # print(f"Custom scripts folder does not exist: {CUSTOM_SCRIPTS_FOLDER}. Please check its path in DumbToolsPreferences.")
        pass

    bpy.utils.register_class(BaseScriptOperator)
    bpy.utils.register_class(DumbToolsMenu)
    register_script_operators()  # Register all script operators
    create_submenus()  # Create and register submenus
    bpy.types.TOPBAR_MT_editor_menus.append(draw_dumbtools_menu)
    execute_startup_scripts()  # Execute startup scripts immediately
    bpy.app.handlers.load_post.append(load_handler)
    bpy.utils.register_class(DumbToolsDocsOperator)





def unregister():
    # Clean up dynamic properties added via annotations
    for prop_name in list(DumbToolsPreferences.__annotations__.keys()):
        if prop_name.startswith("enable_"):
            try:
                DumbToolsPreferences.__annotations__.pop(prop_name, None)
            except Exception:
                pass
    # Unregister the preferences class (ignore if already unregistered)
    try:
        bpy.utils.unregister_class(DumbToolsPreferences)
    except Exception:
        pass
    if load_handler in bpy.app.handlers.load_post:
        bpy.app.handlers.load_post.remove(load_handler)
    # If the addon is disabled, remove the menu from the editor
    bpy.types.TOPBAR_MT_editor_menus.remove(draw_dumbtools_menu)
    bpy.utils.unregister_class(DumbToolsDocsOperator)
    
    # Unregister the script operators
    for op_class in reversed(list(SCRIPT_OPERATORS.values())):
        bpy.utils.unregister_class(op_class)
    SCRIPT_OPERATORS.clear()
    
    # Unregister submenus
    for menu_class in reversed(SUBMENU_CLASSES):
        bpy.utils.unregister_class(menu_class)
    SUBMENU_CLASSES.clear()
    
    # Unregister the base script operator and the main menu
    bpy.utils.unregister_class(DumbToolsMenu)
    bpy.utils.unregister_class(BaseScriptOperator)
    
    #print("DumbTools Add-on unregistered.")  # Indicates the add-on is unregistered
    # Clear CUSTOM_SCRIPTS_FOLDER, CUSTOM_STARTUP_FOLDER, CUSTOM_POSTLOAD_FOLDER
    global CUSTOM_SCRIPTS_FOLDER, CUSTOM_STARTUP_FOLDER, CUSTOM_POSTLOAD_FOLDER
    CUSTOM_SCRIPTS_FOLDER = None
    CUSTOM_STARTUP_FOLDER = None
    CUSTOM_POSTLOAD_FOLDER = None


if __name__ == "__main__":
    unregister()
    register()
                   


