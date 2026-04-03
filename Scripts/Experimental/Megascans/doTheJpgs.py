import os
from PIL import Image

def process_preview_images(root_dir):
    print(f"Starting search in root directory: {root_dir}")
    # Walk through all subdirectories
    for dirpath, dirnames, filenames in os.walk(root_dir):
        print(f"Checking directory: {dirpath}")
        #print(f"Files found: {filenames}")
        # Look for preview PNG files
        for filename in filenames:
            if '_preview.png' in filename.lower() or '_Preview.png' in filename:
                print(f"Found PNG: {filename}")
                # Full path to the source file
                input_path = os.path.join(dirpath, filename)
                
                # Create output filename (change extension to jpg)
                output_filename = filename.replace('_Preview.png', '_Preview.jpg')
                if '_Preview.png' not in filename:  # if it was lowercase
                    output_filename = filename.replace('_preview.png', '_preview.jpg')
                output_path = os.path.join(dirpath, output_filename)
                
                # Skip if output file already exists
                if os.path.exists(output_path):
                    print(f"Skipping {input_path} - output already exists")
                    continue
                
                try:
                    # Open and resize image
                    with Image.open(input_path) as img:
                        # Create a black background
                        bg = Image.new('RGB', img.size, (0, 0, 0))
                        # Paste the image using its alpha channel as mask
                        if img.mode == 'RGBA':
                            bg.paste(img, mask=img.split()[3])
                        else:
                            bg.paste(img)
                        # Resize to 256x256 with LANCZOS resampling for better quality
                        bg = bg.resize((256, 256), Image.Resampling.LANCZOS)
                        # Save as JPG with quality 70
                        bg.save(output_path, 'JPEG', quality=70)
                        print(f"Processed: {input_path} -> {output_path}")
                except Exception as e:
                    print(f"Error processing {input_path}: {str(e)}")

if __name__ == "__main__":
    process_preview_images(r"F:\Megascans\3DPlants")
    print("Processing complete!")
