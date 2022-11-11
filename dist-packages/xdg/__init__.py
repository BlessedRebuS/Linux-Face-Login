__all__ = [ "BaseDirectory", "DesktopEntry", "Menu", "Exceptions", "IniFile", "IconTheme", "Locale", "Config", "Mime", "RecentFiles", "MenuEditor" ]

__version__ = "0.27"

# Compatibility with xdg 5

from pathlib import Path
from typing import Optional, List
import os

from . import BaseDirectory

def xdg_cache_home() -> Path:
    return Path(BaseDirectory.xdg_cache_home)

def xdg_config_dirs() -> List[Path]:
    return [Path(path) for path in BaseDirectory.xdg_config_dirs]

def xdg_config_home() -> Path:
    return Path(BaseDirectory.xdg_config_home)

def xdg_data_dirs() -> List[Path]:
    return [Path(path) for path in BaseDirectory.xdg_data_dirs]

def xdg_data_home() -> Path:
    return Path(BaseDirectory.xdg_data_home)

def xdg_runtime_dir() -> Optional[Path]:
    try:
        return Path(os.environ['XDG_RUNTIME_DIR'])
    except KeyError:
        return None

XDG_CACHE_HOME = xdg_cache_home()
XDG_CONFIG_DIRS = xdg_config_dirs()
XDG_CONFIG_HOME = xdg_config_home()
XDG_DATA_DIRS = xdg_data_dirs()
XDG_DATA_HOME = xdg_data_home()
XDG_RUNTIME_DIR = xdg_runtime_dir()
