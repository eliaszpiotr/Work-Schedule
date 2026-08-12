import tempfile
from pathlib import Path

ASSETS_DIR = Path(__file__).resolve().parent / "assets"
FONT_FILE = ASSETS_DIR / "fonts" / "InterVariable.ttf"
ICONS_DIR = ASSETS_DIR / "icons"

# Window and dock icon. The .icns and .ico next to it are for packaged builds.
APP_ICON = ASSETS_DIR / "app_icon.png"

# Stylesheets can only point at icons by path, so recoloured copies are cached here.
ICON_CACHE_DIR = Path(tempfile.gettempdir()) / "work-scheduler-icons"
