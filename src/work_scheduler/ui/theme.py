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
    warning_surface: str
    success_surface: str
    holiday_surface: str
    holiday_ink: str
    danger_surface: str
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
    warning_surface="#FBF1DA",
    success_surface="#E9F3EC",
    holiday_surface="#E4EEFA",
    holiday_ink="#3F6295",
    danger_surface="#FBE7E5",
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
    warning_surface="#3B3018",
    success_surface="#1F3327",
    holiday_surface="#1F2E42",
    holiday_ink="#7FA3D4",
    danger_surface="#3E2422",
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

    badge_height: int = 22
    avatar_size: int = 32
    card_padding: int = 18
    segment_height: int = 28
    brand_mark: int = 28

    control_height: int = 34
    icon_button: int = 30
    nav_item_height: int = 34
    toolbar_height: int = 48
    table_row_height: int = 38
    employee_row_height: int = 52
    picker_row_height: int = 44
    lane_header_height: int = 50
    sidebar_width: int = 248
    sidebar_collapsed: int = 64
    dialog_width: int = 460
    weekday_label_width: int = 110
    time_field_width: int = 90
    people_list_height: int = 232
    calendar_header_height: int = 26
    grid_column_width: int = 132
    # Wide enough for "sb 15.08 · Wniebowzięcie NMP" to be worth reading.
    grid_date_width: int = 212


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
    QListWidget#navigation[collapsed="true"]::item {{ padding: 0; }}
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
    QLabel[tone="success"] {{ font-size: {m.font_secondary}px; color: {p.success}; }}
    QLabel[tone="danger"] {{ font-size: {m.font_secondary}px; color: {p.danger}; }}
    QLabel[tone="warning"] {{ font-size: {m.font_secondary}px; color: {p.warning}; }}

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
    QPushButton[variant="dangerFilled"] {{
        background: {p.danger};
        border: 1px solid {p.danger};
        color: #FFFFFF;
    }}
    QPushButton[variant="dangerFilled"]:hover {{
        background: {p.danger_hover};
        border-color: {p.danger_hover};
    }}
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
    QLineEdit, QComboBox, QDateEdit, QTimeEdit, QSpinBox {{
        min-height: {m.control_height}px;
        background: {p.elevated};
        border: 1px solid {p.border_strong};
        border-radius: {m.radius_sm}px;
        padding: 0 {m.space_3}px;
        selection-background-color: {p.accent};
        selection-color: {p.on_accent};
    }}
    QLineEdit:focus, QComboBox:focus, QDateEdit:focus, QTimeEdit:focus, QSpinBox:focus {{
        border-color: {p.accent};
    }}
    QLineEdit:disabled, QComboBox:disabled, QDateEdit:disabled,
    QTimeEdit:disabled, QSpinBox:disabled {{
        color: {p.text_muted};
        background: {p.surface};
        border-color: {p.border};
    }}
    QComboBox::drop-down, QDateEdit::drop-down {{
        border: none;
        width: {m.space_6}px;
        subcontrol-position: center right;
        right: {m.space_2}px;
    }}
    QComboBox::down-arrow, QDateEdit::down-arrow {{ width: 16px; height: 16px; {chevron} }}
    /* Time fields are typed into, not clicked up and down; the native arrows only
       break the shape of the field. */
    QAbstractSpinBox::up-button, QAbstractSpinBox::down-button {{
        width: 0;
        border: none;
    }}
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
    /* QListWidget items carry their own indicator, which QCheckBox rules do not reach. */
    QCheckBox::indicator, QListView::indicator {{
        width: 16px;
        height: 16px;
        border: 1px solid {p.border_strong};
        border-radius: {m.radius_sm}px;
        background: {p.elevated};
    }}
    QCheckBox::indicator:checked, QListView::indicator:checked {{
        background: {p.accent};
        border-color: {p.accent};
        {checked_mark}
    }}

    /* Tables ---------------------------------------------------------------
       Scoped to our own tables with the "data" property. A bare QTableView rule
       would also hit the table inside QCalendarWidget, take over its drawing and
       silently drop the colours the calendar sets on individual dates. */
    QTableView[data="true"] {{
        background: {p.background};
        alternate-background-color: {p.background};
        border: 1px solid {p.border};
        border-radius: {m.radius_md}px;
        gridline-color: transparent;
        outline: none;
        selection-background-color: {p.surface_active};
        selection-color: {p.text_primary};
    }}
    QTableView[data="true"]::item {{
        padding: 0 {m.space_3}px;
        border-bottom: 1px solid {p.border};
    }}
    QTableView[data="true"]::item:hover {{ background: {p.surface_hover}; }}
    QTableView[data="true"]::item:selected {{
        background: {p.surface_active};
        color: {p.text_primary};
    }}
    /* The grid draws its own cells, rules and cursor in the delegate, so nothing here
       may paint over them. Only the frame around the whole table is left to the sheet. */
    /* The table is the card: nesting a bordered view inside a bordered frame draws
       the outline twice, and Qt does not clip a child to its parent's rounded
       corners, so the square corners would sit on top of the round ones. */
    QTableView[role="grid"] {{
        background: {p.elevated};
        border: 1px solid {p.border};
        border-bottom: none;
        border-top-left-radius: {m.radius_lg}px;
        border-top-right-radius: {m.radius_lg}px;
        selection-background-color: transparent;
        outline: none;
    }}
    QTableView[role="grid"]::item {{
        border: none;
        padding: 0;
        background: transparent;
    }}
    QTableView[role="grid"]::item:selected {{ background: transparent; }}
    /* The editor sits exactly in the cell: square, flush, no frame of its own. */
    QTableView[role="grid"] QLineEdit {{
        border: 2px solid {p.accent};
        border-radius: 0;
        padding: 0;
        margin: 0;
        min-height: 0;
        background: {p.elevated};
        color: {p.text_primary};
    }}
    /* The stub above the dates: part of the same ruled table, not a stray grey box. */
    QTableView[role="grid"] QTableCornerButton::section {{
        background: {p.background};
        border: none;
        border-right: 1px solid {p.border};
        border-bottom: 1px solid {p.border};
    }}
    QTableView[role="grid"] QHeaderView::section {{
        background: {p.background};
        border: none;
        border-right: 1px solid {p.border};
        border-bottom: 1px solid {p.border};
        padding: 0 {m.space_3}px;
        font-size: {m.font_secondary}px;
        font-weight: 500;
        color: {p.text_secondary};
    }}
    /* Without this the header paints its own colour over the empty area below the last
       row, leaving a stray block under the grid. */
    QTableView[data="true"] QHeaderView {{ background: transparent; border: none; }}
    QTableView[data="true"] QHeaderView::section {{
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
    QTableView[data="true"] QTableCornerButton::section {{
        background: {p.background};
        border: none;
    }}
    /* The totals strip under the grid: its own view, so it never scrolls away. */
    QTableView[role="totals"] {{
        background: {p.surface};
        border: 1px solid {p.border};
        border-top: 1px solid {p.border_strong};
        border-bottom-left-radius: {m.radius_lg}px;
        border-bottom-right-radius: {m.radius_lg}px;
        font-weight: 600;
    }}
    QTableView[role="totals"]::item {{ border-bottom: none; }}

    /* Cards, badges, avatars -----------------------------------------------
       Qt has no box-shadow, so a card is told apart by its surface and its border
       rather than by lift. Components attach QGraphicsDropShadowEffect where a
       shadow is worth the repaint. */
    QFrame#card {{
        background: {p.elevated};
        border: 1px solid {p.border};
        border-radius: {m.radius_lg}px;
    }}
    QFrame#card:hover {{ border-color: {p.border_strong}; }}
    QFrame#card[selected="true"] {{ border-color: {p.accent}; }}
    QLabel#cardTitle {{ font-size: 17px; font-weight: 600; }}
    QLabel#sectionTitle {{ font-size: 15px; font-weight: 600; }}

    /* Badges carry a state in one glance: the dot and the word say the same thing,
       so colour alone never has to. */
    QLabel[badge] {{
        min-height: {m.badge_height}px;
        max-height: {m.badge_height}px;
        border-radius: {m.badge_height // 2}px;
        padding: 0 9px;
        font-size: 11px;
        font-weight: 500;
    }}
    QLabel[badge="neutral"] {{
        background: {p.surface_hover};
        border: 1px solid {p.border_strong};
        color: {p.text_secondary};
    }}
    QLabel[badge="success"] {{
        background: {p.success_surface};
        border: 1px solid {p.success};
        color: {p.success};
    }}
    QLabel[badge="info"] {{
        background: {p.holiday_surface};
        border: 1px solid {p.holiday_surface};
        color: {p.holiday_ink};
    }}
    QLabel[badge="muted"] {{
        background: {p.surface_active};
        border: 1px solid {p.surface_active};
        color: {p.text_secondary};
    }}

    QLabel[avatar="plain"], QLabel[avatar="accent"] {{
        min-width: {m.avatar_size}px;
        max-width: {m.avatar_size}px;
        min-height: {m.avatar_size}px;
        max-height: {m.avatar_size}px;
        border-radius: {m.avatar_size // 2}px;
        font-size: 11px;
        font-weight: 600;
    }}
    QLabel[avatar="plain"] {{ background: {p.surface_active}; color: {p.text_secondary}; }}
    QLabel[avatar="accent"] {{ background: {p.holiday_surface}; color: {p.holiday_ink}; }}

    /* The application mark in the sidebar: a filled square holding one icon. */
    /* The coloured square in a dialog, holding the one icon that says what is about
       to happen. Read before the title is, which is the point. */
    QLabel[glyph] {{
        min-width: 38px;
        max-width: 38px;
        min-height: 38px;
        max-height: 38px;
    }}
    QLabel[glyph="danger"] {{ background: {p.danger_surface}; border-radius: 10px; }}
    QLabel[glyph="warning"] {{ background: {p.warning_surface}; border-radius: 10px; }}
    QLabel[glyph="info"] {{ background: {p.holiday_surface}; border-radius: 10px; }}
    QLabel#dialogTitle {{ font-size: {m.font_section}px; font-weight: 600; }}
    QLabel#dialogBody {{ font-size: {m.font_secondary}px; color: {p.text_secondary}; }}

    QLabel#brandMark {{
        min-width: {m.brand_mark}px;
        max-width: {m.brand_mark}px;
        min-height: {m.brand_mark}px;
        max-height: {m.brand_mark}px;
        border-radius: {m.radius_md}px;
        background: {p.accent};
    }}

    /* Segmented filter ------------------------------------------------------
       One control instead of a dropdown: every option is visible, so nobody has to
       open a list to find out what the choices are. */
    QWidget#segmented {{
        background: {p.surface_active};
        border-radius: {m.radius_md}px;
    }}
    QPushButton[segment="true"] {{
        min-height: {m.segment_height}px;
        max-height: {m.segment_height}px;
        padding: 0 14px;
        border: 1px solid transparent;
        border-radius: {m.radius_sm}px;
        background: transparent;
        color: {p.text_secondary};
        font-weight: 400;
    }}
    QPushButton[segment="true"]:hover {{ color: {p.text_primary}; }}
    QPushButton[segment="true"]:checked {{
        background: {p.elevated};
        border-color: {p.border};
        color: {p.text_primary};
        font-weight: 500;
    }}
    QPushButton[segment="true"]:focus {{ border-color: {p.accent}; }}

    /* Scrolling card lists -------------------------------------------------- */
    QListWidget[role="picker"] {{
        background: {p.elevated};
        border: 1px solid {p.border_strong};
        border-radius: {m.radius_md}px;
        outline: none;
    }}
    QListWidget[role="picker"]::item {{ border: none; padding: 0; background: transparent; }}
    QListWidget[role="picker"]::item:selected {{ background: transparent; }}
    QListWidget[role="picker"]::indicator {{ width: 0; height: 0; }}

    QScrollArea#cardList {{ background: transparent; border: none; }}
    QScrollArea#cardList > QWidget > QWidget {{ background: transparent; }}
    QFrame#workspaceBody {{ background: {p.surface}; border: none; }}
    QFrame#gridCard {{ background: transparent; border: none; }}

    /* Calendar popup ------------------------------------------------------- */
    /* Only the navigation bar is styled. The month grid inside a QCalendarWidget is a
       QTableView, and any ::item rule aimed at it makes Qt draw the cells itself and
       ignore the colours the calendar puts on individual dates — which is how holidays
       stop showing. Everything the table rules above do is scoped away from it. */
    QCalendarWidget QWidget#qt_calendar_navigationbar {{
        background: {p.elevated};
        border-bottom: 1px solid {p.border};
    }}
    QCalendarWidget QToolButton {{
        background: transparent;
        border: none;
        color: {p.text_primary};
        font-size: {m.font_secondary}px;
        font-weight: 600;
        padding: {m.space_1}px {m.space_2}px;
    }}
    QCalendarWidget QToolButton:hover {{ background: {p.surface_hover}; }}
    QCalendarWidget QToolButton::menu-indicator {{ image: none; }}
    QCalendarWidget QSpinBox {{ min-height: 0; }}
    /* Qt's documented handle for the month grid: :disabled is how it paints the days
       that spill in from the neighbouring months. */
    QCalendarWidget QAbstractItemView:enabled {{
        background: {p.elevated};
        color: {p.text_primary};
        selection-background-color: {p.accent};
        selection-color: {p.on_accent};
        outline: none;
    }}
    QCalendarWidget QAbstractItemView:disabled {{ color: {p.text_muted}; }}

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
