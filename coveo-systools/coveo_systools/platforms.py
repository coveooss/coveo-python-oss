import platform as _platform

WINDOWS: bool = _platform.system().startswith("Windows")
LINUX: bool = _platform.system().startswith("Linux")
IOS: bool = _platform.system().startswith("Darwin")

WSL: bool = LINUX and "microsoft" in _platform.release()
