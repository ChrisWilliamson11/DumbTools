# Tooltip: Increases Windows per-process file descriptor limit from 512 to 8192 (fixes VDB sequence loading)

import platform

if platform.system() == "Windows":
    import ctypes
    try:
        ucrt = ctypes.cdll.LoadLibrary("ucrtbase.dll")
        before = ucrt._getmaxstdio()
        ucrt._setmaxstdio(8192)
        after = ucrt._getmaxstdio()
        print(f"DumbTools: File descriptor limit raised from {before} to {after}")
    except Exception as e:
        print(f"DumbTools: Failed to raise file descriptor limit: {e}")
