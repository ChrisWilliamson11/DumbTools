import urllib.request
import re

url = 'https://docs.blender.org/api/master/bpy.types.html'
req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0'})
try:
    html = urllib.request.urlopen(req).read().decode('utf-8')
    menus = re.findall(r'href=\"(bpy\.types\.([A-Z_]+_MT_[a-zA-Z_]+))\.html\"', html)
    for m in set(m[1] for m in menus if 'DOPESHEET_MT' in m[1] or 'GRAPH_MT' in m[1]):
        print(m)
except Exception as e:
    print(e)
