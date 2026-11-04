from collections.abc import Callable

from PySide6.QtCore import QPoint, Qt
from PySide6.QtWidgets import (
    QDialog,
    QHBoxLayout,
    QMenu,
    QMessageBox,
    QVBoxLayout,
    QWidget,
)

from work_scheduler.i18n import t
from work_scheduler.services import RuleSetData, RuleSetService, ServiceError
from work_scheduler.ui.components import Card, PlainLabel, icon_button, restyle
from work_scheduler.ui.icons import load_icon
from work_scheduler.ui.settings.rule_sets_dialog import RuleSetEditDialog, rule_description
from work_scheduler.ui.theme import METRICS, Palette


class RuleSetCard(Card):
    """One set, drawn like a schedule on the schedules screen.

    Name on top, what it holds underneath, the menu at the end. A click picks it, a
    double click edits it, the menu and the right button offer edit and delete.
    """

    def __init__(
        self,
        item: RuleSetData,
        people: dict[int, str],
        palette: Palette,
        on_edit: Callable[[RuleSetData], None],
        on_delete: Callable[[RuleSetData], None],
        on_pick: Callable[["RuleSetCard"], None],
    ) -> None:
        super().__init__()
        self.item = item
        self._on_edit, self._on_delete, self._on_pick = on_edit, on_delete, on_pick
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setAccessibleName(item.name)
        self.setToolTip("\n".join(rule_description(rule, people) for rule in item.rules))

        self._menu = icon_button("ellipsis", t("common.more"), palette)
        self._menu.clicked.connect(self._open_menu)

        title = PlainLabel(item.name)
        title.setObjectName("cardTitle")
        heading = QHBoxLayout()
        heading.setSpacing(METRICS.space_2)
        heading.addWidget(title)
        heading.addStretch()
        heading.addWidget(self._menu)

        parts = [t("rules.rule_count", count=len(item.rules))]
        if item.rules:
            parts.append(rule_description(item.rules[0], people))
        if len(item.rules) > 1:
            parts[-1] += " …"
        meta = PlainLabel("  ·  ".join(parts))
        meta.setObjectName("secondaryText")

        self.body().setSpacing(METRICS.space_2)
        self.body().addLayout(heading)
        self.body().addWidget(meta)

    def apply_palette(self, palette: Palette) -> None:
        self._menu.setIcon(load_icon("ellipsis", palette.text_secondary))

    def set_picked(self, picked: bool) -> None:
        self.setProperty("selected", "true" if picked else None)
        restyle(self)

    def _menu_at(self, position) -> None:  # noqa: ANN001 - a QPoint
        self._on_pick(self)
        menu = QMenu(self)
        menu.addAction(t("common.edit"), lambda: self._on_edit(self.item))
        menu.addSeparator()
        menu.addAction(t("common.delete"), lambda: self._on_delete(self.item))
        menu.exec(position)

    def _open_menu(self) -> None:
        self._menu_at(self._menu.mapToGlobal(QPoint(0, self._menu.height())))

    def mousePressEvent(self, event) -> None:  # noqa: N802, ANN001 - Qt API
        self._on_pick(self)
        super().mousePressEvent(event)

    def mouseDoubleClickEvent(self, event) -> None:  # noqa: N802, ANN001 - Qt API
        self._on_edit(self.item)
        super().mouseDoubleClickEvent(event)

    def contextMenuEvent(self, event) -> None:  # noqa: N802, ANN001 - Qt API
        self._menu_at(event.globalPos())


class RuleSetsPanel(QWidget):
    """The rule sets, listed where they are managed instead of behind a button."""

    def __init__(self, service: RuleSetService, palette: Palette) -> None:
        super().__init__()
        self._service = service
        self._palette = palette

        # Same spacing as the schedules screen, so the two lists read as one family.
        self._column = QVBoxLayout(self)
        self._column.setContentsMargins(0, 0, 0, 0)
        self._column.setSpacing(METRICS.space_3)
        self._empty = Card()
        note = PlainLabel(t("rules.empty"))
        note.setObjectName("mutedText")
        note.setWordWrap(True)
        self._empty.body().addWidget(note)
        self._column.addWidget(self._empty)
        self.reload()

    def add_set(self) -> None:
        """Called from the screen's header, where every other screen keeps its add."""
        self._edit(None)

    def cards(self) -> list[RuleSetCard]:
        return self.findChildren(RuleSetCard)

    def reload(self) -> None:
        for card in self.cards():
            self._column.removeWidget(card)
            card.setParent(None)
            card.deleteLater()

        people = dict(self._service.list_people())
        sets = self._service.list_sets()
        self._empty.setVisible(not sets)
        for item in sets:
            self._column.addWidget(
                RuleSetCard(item, people, self._palette, self._edit, self._delete, self._pick)
            )

    def apply_palette(self, palette: Palette) -> None:
        self._palette = palette
        for card in self.cards():
            card.apply_palette(palette)

    def _pick(self, picked: RuleSetCard) -> None:
        for card in self.cards():
            card.set_picked(card is picked)

    def _edit(self, item: RuleSetData | None) -> None:
        people = self._service.list_people()
        dialog = RuleSetEditDialog(self, item, self._palette, people)
        if dialog.exec() != QDialog.DialogCode.Accepted:
            return
        try:
            self._service.save(dialog.name.text(), dialog.rules, item.id if item else None)
        except ServiceError as error:
            QMessageBox.warning(self, t("common.failed"), str(error))
            return
        self.reload()

    def _delete(self, item: RuleSetData) -> None:
        answer = QMessageBox.question(
            self, t("rules.delete"), t("rules.delete_confirm", name=item.name)
        )
        if answer != QMessageBox.StandardButton.Yes:
            return
        try:
            self._service.delete(item.id)
        except ServiceError as error:
            QMessageBox.warning(self, t("common.failed"), str(error))
            return
        self.reload()
