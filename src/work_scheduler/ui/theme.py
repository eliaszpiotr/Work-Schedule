from dataclasses import dataclass
from pathlib import Path

from PySide6.QtCore import QObject, Qt, Signal
from PySide6.QtGui import QFontDatabase, QGuiApplication

from work_scheduler.ui.icons import icon_file
from work_scheduler.ui.resources import FONT_FILE

FALLBACK_FONT = "-apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif"


@dataclass(frozen=True, slots=True)
class Palette:
    background: str
    surface: str
    elevated: str
    surface_hover: str
    surface_active: str
    text_primary: str
    text_secondary: str
    text_muted: str
    border: str
    border_strong: str
    accent: str
    accent_hover: str
    on_accent: str
    success: str
    warning: str
    danger: str
    danger_hover: str


LIGHT = Palette(
    background="#FFFFFF",
    surface="#F7F7F6",
    elevated="#FFFFFF",
    surface_hover="#F2F2F0",
    surface_active="#ECECEA",
    text_primary="#1F1F1F",
    text_secondary="#666666",
    text_muted="#8A8A8A",
    border="#E5E5E3",
    border_strong="#D5D5D2",
    accent="#1F1F1F",
    accent_hover="#383838",
    on_accent="#FFFFFF",
    success="#3F8F5B",
    warning="#B07B24",
    danger="#C2453C",
    danger_hover="#A93A32",
)

DARK = Palette(
    background="#1E1E1E",
    surface="#252525",
    elevated="#2A2A2A",
    surface_hover="#303030",
    surface_active="#353535",
    text_primary="#ECECEC",
    text_secondary="#A8A8A8",
    text_muted="#777777",
    border="#343434",
    border_strong="#454545",
    # Black would vanish on a dark background, so the primary action inverts instead.
    accent="#ECECEC",
    accent_hover="#FFFFFF",
    on_accent="#1E1E1E",
    success="#68B183",
    warning="#D3A353",
    danger="#E0736B",
    danger_hover="#E88880",
)


@dataclass(frozen=True, slots=True)
class Metrics:
    space_1: int = 4
    space_2: int = 8
    space_3: int = 12
    space_4: int = 16
    space_5: int = 20
    space_6: int = 24
    space_8: int = 32

    radius_sm: int = 6
    radius_md: int = 8
    radius_lg: int = 12

    font_page_title: int = 20
    font_section: int = 16
    font_body: int = 14
    font_secondary: int = 13
    font_metadata: int = 12

    control_height: int = 34
    icon_button: int = 30
    nav_item_height: int = 34
    toolbar_height: int = 48
    table_row_height: int = 38
    sidebar_width: int = 248
    dialog_width: int = 460


METRICS = Metrics()


def load_font_family() -> str:
    """Inter ships with the application so it looks the same on every machine."""
    if not FONT_FILE.is_file():
        return FALLBACK_FONT

    font_id = QFontDatabase.addApplicationFont(str(FONT_FILE))
    families = QFontDatabase.applicationFontFamilies(font_id)
    return families[0] if families else FALLBACK_FONT


def stylesheet(
    palette: Palette,
    font_family: str,
    metrics: Metrics = METRICS,
    check_icon: Path | None = None,
    chevron_icon: Path | None = None,
) -> str:
    p, m = palette, metrics
    checked_mark = f"image: url({check_icon.as_posix()});" if check_icon else ""
    chevron = f"image: url({chevron_icon.as_posix()});" if chevron_icon else ""
    return f"""
    * {{
        font-family: "{font_family}";
        font-size: {m.font_body}px;
        color: {p.text_primary};
    }}
    QWidget#window, QWidget#workspace {{ background: {p.background}; }}
    QToolTip {{
        background: {p.elevated};
        color: {p.text_primary};
        border: 1px solid {p.border_strong};
        border-radius: {m.radius_sm}px;
        padding: {m.space_1}px {m.space_2}px;
    }}

    /* Sidebar ------------------------------------------------------------- */
    QFrame#sidebar {{
        background: {p.surface};
        border: none;
        border-right: 1px solid {p.border};
    }}
    QLabel#brand {{
        font-size: {m.font_section}px;
        font-weight: 600;
        color: {p.text_primary};
    }}
    QLabel#sectionLabel {{
        font-size: {m.font_metadata}px;
        font-weight: 500;
        color: {p.text_muted};
        padding: {m.space_2}px {m.space_2}px {m.space_1}px {m.space_2}px;
    }}
    QListWidget#navigation {{
        background: transparent;
        border: none;
        outline: none;
    }}
    QListWidget#navigation::item {{
        min-height: {m.nav_item_height}px;
        border-radius: {m.radius_sm}px;
        padding: 0 {m.space_3}px;
        color: {p.text_secondary};
    }}
    QListWidget#navigation::item:hover {{
        background: {p.surface_hover};
        color: {p.text_primary};
    }}
    QListWidget#navigation::item:selected {{
        background: {p.surface_active};
        color: {p.text_primary};
        font-weight: 500;
    }}

    /* Toolbar and headings ------------------------------------------------ */
    QFrame#toolbar {{
        background: {p.background};
        border: none;
        border-bottom: 1px solid {p.border};
    }}
    QLabel#pageTitle {{
        font-size: {m.font_page_title}px;
        font-weight: 600;
    }}
    QLabel#secondaryText {{
        font-size: {m.font_secondary}px;
        color: {p.text_secondary};
    }}
    QLabel#mutedText {{
        font-size: {m.font_secondary}px;
        color: {p.text_muted};
    }}
    QLabel#emptyTitle {{
        font-size: {m.font_section}px;
        font-weight: 600;
    }}

    /* Buttons ------------------------------------------------------------- */
    QPushButton {{
        min-height: {m.control_height}px;
        border-radius: {m.radius_sm}px;
        padding: 0 {m.space_3}px;
        background: {p.elevated};
        border: 1px solid {p.border_strong};
        color: {p.text_primary};
        font-size: {m.font_secondary}px;
        font-weight: 500;
    }}
    QPushButton:hover {{ background: {p.surface_hover}; }}
    QPushButton:pressed {{ background: {p.surface_active}; }}
    QPushButton:disabled {{ color: {p.text_muted}; border-color: {p.border}; }}
    QPushButton:focus {{ border: 1px solid {p.accent}; }}

    QPushButton[variant="primary"] {{
        background: {p.accent};
        border: 1px solid {p.accent};
        color: {p.on_accent};
    }}
    QPushButton[variant="primary"]:hover {{
        background: {p.accent_hover};
        border-color: {p.accent_hover};
    }}
    QPushButton[variant="ghost"] {{ background: transparent; border: 1px solid transparent; }}
    QPushButton[variant="ghost"]:hover {{ background: {p.surface_hover}; }}
    QPushButton[variant="danger"] {{ color: {p.danger}; border-color: {p.border_strong}; }}
    QPushButton[variant="danger"]:hover {{
        background: {p.danger};
        border-color: {p.danger};
        color: {p.on_accent};
    }}

    QToolButton {{
        background: transparent;
        border: 1px solid transparent;
        border-radius: {m.radius_sm}px;
    }}
    QToolButton:hover {{ background: {p.surface_hover}; }}
    QToolButton:pressed {{ background: {p.surface_active}; }}
    QToolButton:focus {{ border-color: {p.accent}; }}

    /* Inputs -------------------------------------------------------------- */
    QLineEdit, QComboBox, QDateEdit, QSpinBox {{
        min-height: {m.control_height}px;
        background: {p.elevated};
        border: 1px solid {p.border_strong};
        border-radius: {m.radius_sm}px;
        padding: 0 {m.space_3}px;
        selection-background-color: {p.accent};
        selection-color: {p.on_accent};
    }}
    QLineEdit:focus, QComboBox:focus, QDateEdit:focus, QSpinBox:focus {{
        border-color: {p.accent};
    }}
    QLineEdit:disabled, QComboBox:disabled {{ color: {p.text_muted}; background: {p.surface}; }}
    QComboBox::drop-down {{
        border: none;
        width: {m.space_6}px;
        subcontrol-position: center right;
        right: {m.space_2}px;
    }}
    QComboBox::down-arrow {{ width: 16px; height: 16px; {chevron} }}
    QComboBox QAbstractItemView {{
        background: {p.elevated};
        border: 1px solid {p.border_strong};
        border-radius: {m.radius_sm}px;
        padding: {m.space_1}px;
        selection-background-color: {p.surface_active};
        selection-color: {p.text_primary};
        outline: none;
    }}
    QLabel#fieldLabel {{
        font-size: {m.font_secondary}px;
        color: {p.text_secondary};
        font-weight: 500;
    }}
    QCheckBox {{ spacing: {m.space_2}px; }}
    QCheckBox::indicator {{
        width: 16px;
        height: 16px;
        border: 1px solid {p.border_strong};
        border-radius: {m.radius_sm}px;
        background: {p.elevated};
    }}
    QCheckBox::indicator:checked {{
        background: {p.accent};
        border-color: {p.accent};
        {checked_mark}
    }}

    /* Tables -------------------------------------------------------------- */
    QTableView {{
        background: {p.background};
        alternate-background-color: {p.background};
        border: 1px solid {p.border};
        border-radius: {m.radius_md}px;
        gridline-color: transparent;
        outline: none;
        selection-background-color: {p.surface_active};
        selection-color: {p.text_primary};
    }}
    QTableView::item {{
        padding: 0 {m.space_3}px;
        border-bottom: 1px solid {p.border};
    }}
    QTableView::item:hover {{ background: {p.surface_hover}; }}
    QTableView::item:selected {{ background: {p.surface_active}; color: {p.text_primary}; }}
    QHeaderView::section {{
        background: {p.background};
        color: {p.text_muted};
        border: none;
        border-bottom: 1px solid {p.border};
        padding: 0 {m.space_3}px;
        height: {m.table_row_height}px;
        font-size: {m.font_metadata}px;
        font-weight: 600;
        text-align: left;
    }}
    QTableCornerButton::section {{ background: {p.background}; border: none; }}

    /* Dialogs, menus, status ---------------------------------------------- */
    QDialog {{ background: {p.background}; }}
    QMenu {{
        background: {p.elevated};
        border: 1px solid {p.border_strong};
        border-radius: {m.radius_md}px;
        padding: {m.space_1}px;
    }}
    QMenu::item {{
        padding: {m.space_2}px {m.space_3}px;
        border-radius: {m.radius_sm}px;
        color: {p.text_primary};
    }}
    QMenu::item:selected {{ background: {p.surface_hover}; }}
    QMenu::separator {{ height: 1px; background: {p.border}; margin: {m.space_1}px 0; }}
    QStatusBar {{
        background: {p.background};
        border-top: 1px solid {p.border};
        color: {p.text_muted};
        font-size: {m.font_metadata}px;
    }}
    QStatusBar::item {{ border: none; }}

    /* Scrollbars ----------------------------------------------------------- */
    QScrollBar:vertical, QScrollBar:horizontal {{
        background: transparent;
        width: 10px;
        height: 10px;
    }}
    QScrollBar::handle:vertical, QScrollBar::handle:horizontal {{
        background: {p.border_strong};
        border-radius: 5px;
        min-height: {m.space_6}px;
        min-width: {m.space_6}px;
    }}
    QScrollBar::handle:hover {{ background: {p.text_muted}; }}
    QScrollBar::add-line, QScrollBar::sub-line {{ height: 0; width: 0; }}
    QScrollBar::add-page, QScrollBar::sub-page {{ background: transparent; }}
    """


class ThemeManager(QObject):
    """Holds the active palette and tells the interface when the system theme flips."""

    changed = Signal()

    def __init__(self) -> None:
        super().__init__()
        self._font_family = load_font_family()
        self._palette = self._palette_for_system()

    @property
    def palette(self) -> Palette:
        return self._palette

    @property
    def font_family(self) -> str:
        return self._font_family

    @staticmethod
    def _palette_for_system() -> Palette:
        hints = QGuiApplication.styleHints()
        return DARK if hints.colorScheme() == Qt.ColorScheme.Dark else LIGHT

    def apply(self, app: QGuiApplication) -> None:
        self._palette = self._palette_for_system()
        app.setStyleSheet(
            stylesheet(
                self._palette,
                self._font_family,
                check_icon=icon_file("check", self._palette.on_accent),
                chevron_icon=icon_file("chevron-down", self._palette.text_secondary),
            )
        )

    def follow_system(self, app: QGuiApplication) -> None:
        self.apply(app)
        QGuiApplication.styleHints().colorSchemeChanged.connect(lambda _: self._reapply(app))

    def _reapply(self, app: QGuiApplication) -> None:
        self.apply(app)
        self.changed.emit()
