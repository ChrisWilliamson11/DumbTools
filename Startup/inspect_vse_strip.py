import bpy

def inspect_strip():
    se = bpy.context.scene.sequence_editor
    if not se:
        print("No Sequence Editor found.")
        return

    strip = se.active_strip
    if not strip:
        print("No active strip selected.")
        return

    print(f"Inspecting Strip: {strip.name} (Type: {strip.type})")
    print("-" * 30)

    # 1. Check direct attributes
    print("Direct Attributes:")
    for attr in dir(strip):
        if not attr.startswith("__"):
            try:
                val = getattr(strip, attr)
                # Filter out standard bulky stuff if needed, but for now print all non-callable
                if not callable(val):
                    print(f"  .{attr} = {str(val)[:100]}") # Truncate long values
            except:
                pass

    # 2. Check elements (for image sequences)
    if hasattr(strip, "elements") and len(strip.elements) > 0:
        print("\nFirst Element Attributes:")
        elem = strip.elements[0]
        for attr in dir(elem):
            if not attr.startswith("__"):
                try:
                    val = getattr(elem, attr)
                    if not callable(val):
                        print(f"  .{attr} = {str(val)[:100]}")
                except:
                    pass

    # 3. Check for 'metadata' or 'tags' specifically in nested objects
    print("\nLooking for 'metadata' keyword in nested data...")
    if hasattr(strip, "image"): # Some types might have an image block directly?
         print(f"  strip.image: {strip.image}")
         if hasattr(strip.image, "metadata"):
             print(f"  strip.image.metadata: {list(strip.image.metadata.keys())}")


if __name__ == "__main__":
    inspect_strip()
