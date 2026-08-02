# Tooltip: Optimise the vertex groups of selected mesh objects by removing any vertex groups that have zero effect.
import bpy

def survey(obj):
    maxWeight = {}
    for i in obj.vertex_groups:
        maxWeight[i.index] = 0

    for v in obj.data.vertices:
        for g in v.groups:
            gn = g.group
            w = obj.vertex_groups[g.group].weight(v.index)
            if (maxWeight.get(gn) is None or w>maxWeight[gn]):
                maxWeight[gn] = w
    return maxWeight

for obj in bpy.context.selected_objects:
    if obj.type != 'MESH':
        continue

    maxWeight = survey(obj)
    # fix bug pointed out by user2859
    ka = []
    ka.extend(maxWeight.keys())
    ka.sort(key=lambda gn: -gn)
    print(f"Processing {obj.name}: {ka}")
    for gn in ka:
        if maxWeight[gn]<=0:
            print("delete %d"%gn)
            obj.vertex_groups.remove(obj.vertex_groups[gn]) # actually remove the group