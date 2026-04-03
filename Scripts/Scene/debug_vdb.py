import bpy

o = bpy.context.object
if o:
    print(f"--- Inspecting {o.name} ({o.type}) ---")
    if o.type == 'VOLUME':
        d = o.data
        print(f"Data Type: {type(d)}")
        print("Properties in Data:")
        for p in dir(d):
            if 'frame' in p:
                try:
                    val = getattr(d, p)
                    print(f"  test.{p} = {val}")
                except:
                    pass
        
    if o.animation_data:
        print("Animation Data Found")
        if o.animation_data.action:
            act = o.animation_data.action
            print(f"Action: {act.name}")
            if hasattr(act, "layers"):
                print(f"Layers: {len(act.layers)}")
                for l in act.layers:
                    print(f"  Layer: {l.name}")
                    if hasattr(l, "strips"):
                        for i, s in enumerate(l.strips):
                            print(f"    Strip [{i}]: {type(s)}")
                            if hasattr(s, "channelbags"):
                                print(f"      ChannelBags: {len(s.channelbags)}")
                                for bag in s.channelbags:
                                    print(f"        Bag: {type(bag)}")
                                    print(f"        Bag Attributes: {[d for d in dir(bag) if not d.startswith('__')]}")
                                    if hasattr(bag, "fcurves"):
                                        print(f"          FCurves: {len(bag.fcurves)}")
                                        for fc in bag.fcurves:
                                            print(f"            {fc.data_path} points={len(fc.keyframe_points)}")
                                    if hasattr(bag, "channels"):
                                         print(f"          Channels: {len(bag.channels)}")
            if hasattr(act, "fcurves") and len(act.fcurves) > 0:
                 print(f"FCurves (Legacy/Base): {len(act.fcurves)}")
                 for fc in act.fcurves:
                     print(f"  {fc.data_path} points={len(fc.keyframe_points)}")
        else:
            print("No Action")
    else:
        print("No Animation Data")
else:
    print("No Active Object")
