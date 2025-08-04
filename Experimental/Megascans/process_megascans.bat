
@echo off
:loop
blender -b -P CreateMegascansSurfaces.py
if errorlevel 1 (
    echo Blender crashed, waiting 2 seconds before restart...
    timeout /t 2
    goto loop
)
