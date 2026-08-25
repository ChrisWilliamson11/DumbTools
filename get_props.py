import urllib.request
import re

url = 'https://docs.blender.org/api/master/bpy.types.FModifierStepped.html'
req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0'})
try:
    html = urllib.request.urlopen(req).read().decode('utf-8')
    props = re.findall(r'id=\"bpy\.types\.FModifierStepped\.([a-zA-Z_]+)\"', html)
    print(list(set(props)))
except Exception as e:
    print(e)
