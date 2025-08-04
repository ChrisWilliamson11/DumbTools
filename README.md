# DumbTools - Blender Script Collection

**Author:** Chris Williamson  
**Version:** 1.0.1  
**Blender Compatibility:** 3.60.0+

DumbTools is a comprehensive Blender addon that provides a dynamic script execution system, allowing you to organize and run custom Python scripts directly from Blender's interface. It transforms your script collection into an organized, accessible menu system within Blender.

## 🚀 Features

- **Dynamic Menu System**: Automatically organizes scripts into categorized submenus
- **Script Auto-Discovery**: Automatically detects and registers Python scripts from organized folders
- **Startup & Post-Load Scripts**: Execute scripts automatically when Blender starts or loads files

## 🛠️ Installation

### Method 1: Addon Installation (Recommended)
1. Download the `DumbTools.zip` file from the releases
2. In Blender, go to `Edit > Preferences > Add-ons`
3. Click `Install...` and select the downloaded zip file
4. Enable the "DumbTools" addon
5. Configure the scripts folder path in addon preferences


## ⚙️ Configuration

After installation, configure DumbTools in `Edit > Preferences > Add-ons > DumbTools`:

- **Scripts Folder**: Path to your script collection
- **Menu Name**: Custom name for the DumbTools menu
- **Startup Scripts**: Enable/disable individual startup scripts
- **Post-Load Scripts**: Control which scripts run after file loading

## 🎯 Usage

### Accessing Scripts
- **Main Menu**: `Top Bar > DumbTools`
- **Documentation**: `DumbTools > Documentation` (opens interactive HTML docs)
- **Categories**: Scripts are automatically organized by folder structure

### Script Structure
Each script includes:
- **Tooltip Comment**: `# Tooltip: Description of what the script does`
- **Automatic Registration**: Scripts self-register when executed
- **Error Handling**: Built-in error reporting and logging

### Creating Custom Scripts
1. Add your `.py` file to the appropriate category folder
2. Include a tooltip comment at the top: `# Tooltip: Your description`
3. The script will automatically appear in the DumbTools menu

## 🔧 Dependencies

Some scripts require additional Python packages:
- **Photoshop Integration**: `photoshop-connection`, `pillow`
- **File Monitoring**: `watchdog`
- **Computer Vision**: `opencv-python`
- **PSD Import**: `psd-tools`

## 📄 License

This project is open source. Please respect the author's work and provide attribution when using or modifying these scripts.


## 🎉 Acknowledgments

Special thanks to the Blender community for inspiration and feedback that helped shape this comprehensive tool collection.

