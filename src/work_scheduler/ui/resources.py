from pathlib import Path

from work_scheduler.config import default_data_dir

ASSETS_DIR = Path(__file__).resolve().parent / "assets"
FONT_FILE = ASSETS_DIR / "fonts" / "InterVariable.ttf"
ICONS_DIR = ASSETS_DIR / "icons"

# Window and dock icon. The .icns and .ico next to it are for packaged builds.
APP_ICON = ASSETS_DIR / "app_icon.png"

# Stylesheets can only point at icons by path, so recoloured copies are cached here.
# Deliberately not the shared temporary directory: on Linux that is writable by every
# account, and the file names are predictable, so somebody else could leave their own
# markup exactly where a stylesheet is about to read ours.
ICON_CACHE_DIR = default_data_dir() / "icon-cache"
