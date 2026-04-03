# Tooltip:  Randomise all noise modifiers on all f-curves of selected objects

import bpy
import random

def iter_fcurves(action):
    if not action:
        return
    if hasattr(action, "fcurves") and action.fcurves:
        for fc in action.fcurves:
            yield fc
    if hasattr(action, "layers"):
        for layer in action.layers:
            if hasattr(layer, "strips"):
                for strip in layer.strips:
                    if hasattr(strip, "channelbags"):
                         for bag in strip.channelbags:
                             if hasattr(bag, "fcurves"):
                                 for fc in bag.fcurves:
                                     yield fc
                    if hasattr(strip, "fcurves"):
                        for fc in strip.fcurves:
                            yield fc
                    elif hasattr(strip, "channels"):
                         for fc in strip.channels:
                             yield fc

def main():
    # Range for randomizing the phase
    min_phase, max_phase = -10000, 10000

    # Iterate over all selected objects
    for obj in bpy.context.selected_objects:
        # Check if the object has animation data and fcurves
        if obj.animation_data and obj.animation_data.action:
            for fcurve in iter_fcurves(obj.animation_data.action):
                randomize_noise_phase(fcurve, min_phase, max_phase)

def randomize_noise_phase(fcurve, min_phase, max_phase):
    # Iterate over all modifiers of the fcurve
    for modifier in fcurve.modifiers:
        # Check if the modifier is a Noise Modifier
        if modifier.type == 'NOISE':
            # Randomize the phase value
            modifier.phase = random.uniform(min_phase, max_phase)


main()

 