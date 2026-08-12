import hashlib
from functools import lru_cache
from pathlib import Path

from PySide6.QtCore import QByteArray, QRectF, QSize, Qt
from PySide6.QtGui import QIcon, QPainter, QPixmap
from PySide6.QtSvg import QSvgRenderer

from work_scheduler.ui.resources import ICON_CACHE_DIR, ICONS_DIR

DEFAULT_SIZE = 18
RENDER_SCALE = 2  # rendered larger, then marked as high-dpi, so edges stay crisp


class IconNotFoundError(LookupError):
    pass


def available_icons() -> list[str]:
    return sorted(path.stem for path in ICONS_DIR.glob("*.svg"))


def _markup(name: str, color: str) -> str:
    # Lucide files use stroke="currentColor", which Qt does not resolve.
    path = ICONS_DIR / f"{name}.svg"
    if not path.is_file():
        raise IconNotFoundError(f"Brak ikony '{name}' w {ICONS_DIR}")
    return path.read_text(encoding="utf-8").replace("currentColor", color)


@lru_cache(maxsize=256)
def load_icon(name: str, color: str, size: int = DEFAULT_SIZE) -> QIcon:
    renderer = QSvgRenderer(QByteArray(_markup(name, color).encode("utf-8")))

    pixmap = QPixmap(QSize(size, size) * RENDER_SCALE)
    pixmap.fill(Qt.GlobalColor.transparent)
    painter = QPainter(pixmap)
    painter.setRenderHint(QPainter.RenderHint.Antialiasing)
    renderer.render(painter, QRectF(pixmap.rect()))
    painter.end()

    pixmap.setDevicePixelRatio(RENDER_SCALE)
    return QIcon(pixmap)


@lru_cache(maxsize=64)
def icon_file(name: str, color: str) -> Path:
    """A recoloured copy on disk, for stylesheet rules that take a file path."""
    markup = _markup(name, color)
    ICON_CACHE_DIR.mkdir(parents=True, exist_ok=True)

    digest = hashlib.sha256(f"{name}{color}".encode()).hexdigest()[:12]
    target = ICON_CACHE_DIR / f"{name}-{digest}.svg"
    if not target.is_file():
        target.write_text(markup, encoding="utf-8")
    return target
