from PySide6.QtCore import QSize, Qt, QTime
from PySide6.QtGui import QColor, QFont, QPainter
from PySide6.QtWidgets import (
    QCheckBox,
    QDialog,
    QDoubleSpinBox,
    QFormLayout,
    QFrame,
    QHBoxLayout,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QMessageBox,
    QScrollArea,
    QSpinBox,
    QStackedWidget,
    QStyle,
    QStyledItemDelegate,
    QStyleOptionViewItem,
    QTimeEdit,
    QToolButton,
    QVBoxLayout,
    QWidget,
)

from work_scheduler.i18n import t, weekday_name, weekday_short
from work_scheduler.services import RuleSetData, RuleSetService, ServiceError
from work_scheduler.services.rule_sets import (
    BLOCK,
    CONSECUTIVE,
    COVERAGE,
    DAY_COUNT,
    HOURS,
    SATURDAYS,
    STAFFING,
    WARNING,
    validate_rules,
)
from work_scheduler.ui.components import (
    PlainLabel,
    StyledComboBox,
    primary_button,
    secondary_button,
)
from work_scheduler.ui.theme import LIGHT, METRICS, Palette


def _combo(items: list[tuple[str, str]], value: str, palette: Palette) -> StyledComboBox:
    field = StyledComboBox(palette)
    for label, data in items:
        field.addItem(label, data)
    field.setCurrentIndex(max(0, field.findData(value)))
    return field


def rule_description(rule: dict, people: dict[int, str] | None = None) -> str:
    scope = (
        (people or {}).get(rule["employee_id"], t("rules.person_missing", id=rule["employee_id"]))
        if "employee_id" in rule
        else t(f"rules.profession.{rule.get('profession', 'pharmacist')}")
    )
    if rule["kind"] == SATURDAYS:
        return t(
            "rules.description.saturdays",
            comparison=t(f"rules.comparison.{rule['comparison']}"),
            count=rule["count"],
            profession=scope,
        )
    if rule["kind"] in (COVERAGE, STAFFING):
        days = ", ".join(weekday_short(day) for day in rule["weekdays"])
        return t(
            f"rules.description.{rule['kind']}",
            days=days,
            start=rule["start"] or t("rules.opening"),
            end=rule["end"] or t("rules.closing"),
            count=rule.get("count", 1),
            profession=scope,
        )
    if rule["kind"] == DAY_COUNT:
        return t(
            "rules.description.day_count",
            profession=scope,
            comparison=t(f"rules.comparison.{rule['comparison']}"),
            count=rule["count"],
            days=", ".join(weekday_short(day) for day in rule["weekdays"]),
            period=t(f"rules.period.{rule['period']}"),
        )
    if rule["kind"] == HOURS:
        return t(
            "rules.description.hours",
            profession=scope,
            comparison=t(f"rules.comparison.{rule['comparison']}"),
            count=f"{rule['minutes'] / 60:g}",
            period=t(f"rules.period.{rule['period']}"),
        )
    return t(
        "rules.description.consecutive",
        profession=scope,
        count=rule["count"],
    )


class RuleEditorDialog(QDialog):
    def __init__(
        self,
        parent: QWidget | None,
        rule: dict | None = None,
        palette: Palette = LIGHT,
        people: list[tuple[int, str]] | None = None,
    ) -> None:
        super().__init__(parent)
        self.setWindowTitle(t("rules.edit_rule"))
        self.setMinimumWidth(560)
        rule = rule or {
            "kind": SATURDAYS,
            "severity": WARNING,
            "comparison": "min",
            "count": 2,
            "profession": "all",
        }

        self.kind = _combo(
            [
                (t(f"rules.kind.{kind}"), kind)
                for kind in (SATURDAYS, DAY_COUNT, HOURS, CONSECUTIVE, COVERAGE, STAFFING)
            ],
            rule["kind"],
            palette,
        )
        self.severity = _combo(
            [(t("rules.severity.warning"), WARNING), (t("rules.severity.block"), BLOCK)],
            rule["severity"],
            palette,
        )
        comparisons = [(t(f"rules.comparison.{key}"), key) for key in ("min", "exact", "max")]
        professions = [
            (t(f"rules.profession.{key}"), key) for key in ("all", "pharmacist", "technician")
        ]
        people = list(people or [])
        if "employee_id" in rule and rule["employee_id"] not in {id for id, _ in people}:
            people.append((rule["employee_id"], t("rules.person_missing", id=rule["employee_id"])))
        scopes = [
            *professions,
            *((t("rules.person", name=name), f"person:{id}") for id, name in people),
        ]
        selected_scope = (
            f"person:{rule['employee_id']}"
            if "employee_id" in rule
            else rule.get("profession", "all")
        )
        periods = [(t(f"rules.period.{key}"), key) for key in ("week", "month")]
        self.comparison = _combo(comparisons, rule.get("comparison", "min"), palette)
        self.count = QSpinBox()
        self.count.setRange(0, 5)
        self.count.setValue(rule.get("count", 2))
        self.profession = _combo(scopes, selected_scope, palette)
        self.days = self._day_checks(rule.get("weekdays", list(range(6))))
        self.start_enabled = QCheckBox(t("rules.from_time"))
        self.start_enabled.setChecked(rule.get("start", "08:00") is not None)
        self.start = QTimeEdit(QTime.fromString(rule.get("start") or "08:00", "HH:mm"))
        self.start.setDisplayFormat("HH:mm")
        self.end_enabled = QCheckBox(t("rules.until_time"))
        self.end_enabled.setChecked(rule.get("end") is not None)
        self.end = QTimeEdit(QTime.fromString(rule.get("end") or "20:00", "HH:mm"))
        self.end.setDisplayFormat("HH:mm")
        self.start.setFixedWidth(105)
        self.end.setFixedWidth(105)
        self.start_enabled.toggled.connect(self.start.setEnabled)
        self.end_enabled.toggled.connect(self.end.setEnabled)
        self.start.setEnabled(self.start_enabled.isChecked())
        self.end.setEnabled(self.end_enabled.isChecked())

        self.day_period = _combo(periods, rule.get("period", "month"), palette)
        self.day_comparison = _combo(comparisons, rule.get("comparison", "min"), palette)
        self.day_count = QSpinBox()
        self.day_count.setRange(0, 31)
        self.day_count.setValue(rule.get("count", 2))
        self.day_profession = _combo(scopes, selected_scope, palette)
        self.day_weekdays = self._day_checks(rule.get("weekdays", list(range(7))))
        self.day_period.currentIndexChanged.connect(self._day_limit)
        self._day_limit()

        self.hours_period = _combo(periods, rule.get("period", "month"), palette)
        self.hours_comparison = _combo(comparisons, rule.get("comparison", "min"), palette)
        self.hours_value = QDoubleSpinBox()
        self.hours_value.setRange(0, 744)
        self.hours_value.setDecimals(2)
        self.hours_value.setSingleStep(0.5)
        self.hours_value.setValue(rule.get("minutes", 9600) / 60)
        self.hours_profession = _combo(scopes, selected_scope, palette)
        self.hours_period.currentIndexChanged.connect(self._hours_limit)
        self._hours_limit()

        self.consecutive_count = QSpinBox()
        self.consecutive_count.setRange(1, 31)
        self.consecutive_count.setValue(rule.get("count", 6))
        self.consecutive_profession = _combo(scopes, selected_scope, palette)

        self.staff_count = QSpinBox()
        self.staff_count.setRange(1, 30)
        self.staff_count.setValue(rule.get("count", 2))
        self.staff_profession = _combo(professions, rule.get("profession", "all"), palette)
        self.staff_days = self._day_checks(rule.get("weekdays", list(range(6))))
        self.staff_start_enabled = QCheckBox(t("rules.from_time"))
        self.staff_start_enabled.setChecked(rule.get("start") is not None)
        self.staff_start = QTimeEdit(QTime.fromString(rule.get("start") or "08:00", "HH:mm"))
        self.staff_start.setDisplayFormat("HH:mm")
        self.staff_end_enabled = QCheckBox(t("rules.until_time"))
        self.staff_end_enabled.setChecked(rule.get("end") is not None)
        self.staff_end = QTimeEdit(QTime.fromString(rule.get("end") or "20:00", "HH:mm"))
        self.staff_end.setDisplayFormat("HH:mm")
        self.staff_start.setFixedWidth(105)
        self.staff_end.setFixedWidth(105)
        self.staff_start_enabled.toggled.connect(self.staff_start.setEnabled)
        self.staff_end_enabled.toggled.connect(self.staff_end.setEnabled)
        self.staff_start.setEnabled(self.staff_start_enabled.isChecked())
        self.staff_end.setEnabled(self.staff_end_enabled.isChecked())

        for field in (
            self.count,
            self.day_count,
            self.hours_value,
            self.consecutive_count,
            self.staff_count,
        ):
            field.setFixedWidth(110)

        saturday = QWidget()
        sat_form = self._form(saturday)
        sat_form.addRow(t("rules.comparison"), self.comparison)
        sat_form.addRow(t("rules.count"), self.count)
        sat_form.addRow(t("rules.profession"), self.profession)
        self._align_labels(sat_form)

        coverage = QWidget()
        cov_form = self._form(coverage)
        cov_form.addRow(t("rules.weekdays"), self._day_row(self.days))
        cov_form.addRow("", self._time_row(self.start_enabled, self.start))
        cov_form.addRow("", self._time_row(self.end_enabled, self.end))
        cov_form.addRow("", self._hint(t("rules.coverage_hint")))
        self._align_labels(cov_form)

        day_page = QWidget()
        day_form = self._form(day_page)
        day_form.addRow(t("rules.period"), self.day_period)
        day_form.addRow(t("rules.weekdays"), self._day_row(self.day_weekdays))
        day_form.addRow(t("rules.comparison"), self.day_comparison)
        day_form.addRow(t("rules.day_count"), self.day_count)
        day_form.addRow(t("rules.profession"), self.day_profession)
        day_form.addRow("", self._hint(t("rules.complete_period_hint")))
        self._align_labels(day_form)

        hours_page = QWidget()
        hours_form = self._form(hours_page)
        hours_form.addRow(t("rules.period"), self.hours_period)
        hours_form.addRow(t("rules.comparison"), self.hours_comparison)
        hours_form.addRow(t("rules.hours_count"), self.hours_value)
        hours_form.addRow(t("rules.profession"), self.hours_profession)
        hours_form.addRow("", self._hint(t("rules.complete_period_hint")))
        self._align_labels(hours_form)

        consecutive_page = QWidget()
        consecutive_form = self._form(consecutive_page)
        consecutive_form.addRow(t("rules.max_days"), self.consecutive_count)
        consecutive_form.addRow(t("rules.profession"), self.consecutive_profession)
        self._align_labels(consecutive_form)

        staff_page = QWidget()
        staff_form = self._form(staff_page)
        staff_form.addRow(t("rules.staff_count"), self.staff_count)
        staff_form.addRow(t("rules.profession"), self.staff_profession)
        staff_form.addRow(t("rules.weekdays"), self._day_row(self.staff_days))
        staff_form.addRow("", self._time_row(self.staff_start_enabled, self.staff_start))
        staff_form.addRow("", self._time_row(self.staff_end_enabled, self.staff_end))
        staff_form.addRow("", self._hint(t("rules.staffing_hint")))
        self._align_labels(staff_form)

        self.options = QStackedWidget()
        self.options.addWidget(saturday)
        self.options.addWidget(day_page)
        self.options.addWidget(hours_page)
        self.options.addWidget(consecutive_page)
        self.options.addWidget(coverage)
        self.options.addWidget(staff_page)
        self.kind.currentIndexChanged.connect(self.options.setCurrentIndex)
        self.options.setCurrentIndex(self.kind.currentIndex())

        form = self._form()
        form.addRow(t("rules.kind"), self.kind)
        form.addRow(t("rules.severity"), self.severity)
        self._align_labels(form)
        buttons = QHBoxLayout()
        buttons.addStretch()
        cancel = secondary_button(t("common.cancel"))
        save = primary_button(t("common.save"))
        cancel.clicked.connect(self.reject)
        save.clicked.connect(self._accept_valid)
        buttons.addWidget(cancel)
        buttons.addWidget(save)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(*(METRICS.space_6,) * 4)
        layout.setSpacing(METRICS.space_5)
        layout.addLayout(form)
        layout.addWidget(self.options)
        layout.addStretch()
        layout.addLayout(buttons)

    @staticmethod
    def _form(widget: QWidget | None = None) -> QFormLayout:
        form = QFormLayout(widget)
        form.setContentsMargins(0, 0, 0, 0)
        form.setHorizontalSpacing(METRICS.space_3)
        form.setVerticalSpacing(METRICS.space_3)
        form.setLabelAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
        form.setFieldGrowthPolicy(QFormLayout.FieldGrowthPolicy.AllNonFixedFieldsGrow)
        return form

    @staticmethod
    def _align_labels(form: QFormLayout) -> None:
        for row in range(form.rowCount()):
            item = form.itemAt(row, QFormLayout.ItemRole.LabelRole)
            if item is not None and item.widget() is not None:
                item.widget().setFixedWidth(166)

    @staticmethod
    def _hint(message: str) -> PlainLabel:
        label = PlainLabel(message)
        label.setObjectName("mutedText")
        label.setWordWrap(True)
        return label

    @staticmethod
    def _day_checks(selected: list[int]) -> list[QToolButton]:
        checks = []
        for day in range(7):
            button = QToolButton()
            button.setText(weekday_short(day))
            button.setToolTip(weekday_name(day))
            button.setAccessibleName(weekday_name(day))
            button.setProperty("ruleDay", True)
            button.setCheckable(True)
            button.setFixedSize(36, METRICS.control_height)
            button.setCursor(Qt.CursorShape.PointingHandCursor)
            checks.append(button)
        for day, check in enumerate(checks):
            check.setChecked(day in selected)
        return checks

    @staticmethod
    def _day_row(checks: list[QToolButton]) -> QWidget:
        widget = QWidget()
        row = QHBoxLayout(widget)
        row.setContentsMargins(0, 0, 0, 0)
        row.setSpacing(METRICS.space_1)
        for check in checks:
            row.addWidget(check)
        return widget

    @staticmethod
    def _time_row(toggle: QCheckBox, field: QTimeEdit) -> QWidget:
        widget = QWidget()
        row = QHBoxLayout(widget)
        row.setContentsMargins(0, 0, 0, 0)
        row.setSpacing(METRICS.space_3)
        row.addWidget(toggle)
        row.addWidget(field)
        row.addStretch()
        return widget

    def _day_limit(self) -> None:
        self.day_count.setMaximum(7 if self.day_period.currentData() == "week" else 31)

    def _hours_limit(self) -> None:
        self.hours_value.setMaximum(168 if self.hours_period.currentData() == "week" else 744)

    def value(self) -> dict:
        shared = {"kind": self.kind.currentData(), "severity": self.severity.currentData()}
        if shared["kind"] == SATURDAYS:
            return {
                **shared,
                "comparison": self.comparison.currentData(),
                "count": self.count.value(),
                **self._scope(self.profession),
            }
        if shared["kind"] == DAY_COUNT:
            return {
                **shared,
                "period": self.day_period.currentData(),
                "weekdays": self._selected(self.day_weekdays),
                "comparison": self.day_comparison.currentData(),
                "count": self.day_count.value(),
                **self._scope(self.day_profession),
            }
        if shared["kind"] == HOURS:
            return {
                **shared,
                "period": self.hours_period.currentData(),
                "comparison": self.hours_comparison.currentData(),
                "minutes": round(self.hours_value.value() * 60),
                **self._scope(self.hours_profession),
            }
        if shared["kind"] == CONSECUTIVE:
            return {
                **shared,
                "count": self.consecutive_count.value(),
                **self._scope(self.consecutive_profession),
            }
        if shared["kind"] == STAFFING:
            return {
                **shared,
                "weekdays": self._selected(self.staff_days),
                "start": self.staff_start.time().toString("HH:mm")
                if self.staff_start_enabled.isChecked()
                else None,
                "end": self.staff_end.time().toString("HH:mm")
                if self.staff_end_enabled.isChecked()
                else None,
                "count": self.staff_count.value(),
                "profession": self.staff_profession.currentData(),
            }
        return {
            **shared,
            "weekdays": self._selected(self.days),
            "start": self.start.time().toString("HH:mm")
            if self.start_enabled.isChecked()
            else None,
            "end": self.end.time().toString("HH:mm") if self.end_enabled.isChecked() else None,
        }

    @staticmethod
    def _selected(checks: list[QToolButton]) -> list[int]:
        return [day for day, check in enumerate(checks) if check.isChecked()]

    @staticmethod
    def _scope(combo: StyledComboBox) -> dict:
        selected = combo.currentData()
        return (
            {"profession": "all", "employee_id": int(selected.split(":", 1)[1])}
            if selected.startswith("person:")
            else {"profession": selected}
        )

    def _accept_valid(self) -> None:
        try:
            validate_rules([self.value()])
        except ServiceError as error:
            QMessageBox.warning(self, t("common.failed"), str(error))
            return
        self.accept()


class RuleSetEditDialog(QDialog):
    def __init__(
        self,
        parent: QWidget | None,
        source: RuleSetData | None = None,
        palette: Palette = LIGHT,
        people: list[tuple[int, str]] | None = None,
    ) -> None:
        super().__init__(parent)
        self.setWindowTitle(t("rules.edit_set"))
        self.setMinimumWidth(540)
        self._palette = palette
        self._people = list(people or [])
        self.name = QLineEdit(source.name if source else "")
        self.name.setMaxLength(120)
        self.rules = [dict(rule) for rule in source.rules] if source else []
        self.rows = QListWidget()
        self.rows.setFrameShape(QFrame.Shape.NoFrame)
        self.rows.setSpacing(METRICS.space_1)
        self.rows.setStyleSheet("QListWidget { background: transparent; border: none; }")
        self.rows.setItemDelegate(RuleSetDelegate(palette, self.rows))
        self.rows.currentRowChanged.connect(self._selection_changed)
        self.rows.itemDoubleClicked.connect(lambda _: self._edit())
        self._empty_rules = PlainLabel(t("rules.empty_rules"))
        self._empty_rules.setObjectName("mutedText")
        self._empty_rules.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._empty_rules.setMinimumHeight(72)
        self._refresh()
        add = secondary_button(t("rules.add_rule"))
        self._edit_button = secondary_button(t("common.edit"))
        self._remove_button = secondary_button(t("common.delete"))
        add.clicked.connect(self._add)
        self._edit_button.clicked.connect(self._edit)
        self._remove_button.clicked.connect(self._remove)
        buttons = QHBoxLayout()
        for button in (add, self._edit_button, self._remove_button):
            buttons.addWidget(button)
        buttons.addStretch()
        cancel = secondary_button(t("common.cancel"))
        save = primary_button(t("common.save"))
        cancel.clicked.connect(self.reject)
        save.clicked.connect(self._accept_valid)
        actions = QHBoxLayout()
        actions.addStretch()
        actions.addWidget(cancel)
        actions.addWidget(save)
        layout = QVBoxLayout(self)
        label = PlainLabel(t("rules.name"))
        label.setBuddy(self.name)
        layout.addWidget(label)
        layout.addWidget(self.name)
        layout.addWidget(PlainLabel(t("rules.rules")))
        layout.addWidget(self._empty_rules)
        layout.addWidget(self.rows)
        layout.addLayout(buttons)
        layout.addLayout(actions)
        self._selection_changed(self.rows.currentRow())

    def _refresh(self) -> None:
        self.rows.clear()
        for rule in self.rules:
            severity = t(f"rules.severity.{rule['severity']}")
            row = QListWidgetItem(rule_description(rule, dict(self._people)))
            row.setData(Qt.ItemDataRole.UserRole, severity)
            self.rows.addItem(row)
        self.rows.setFixedHeight(min(180, max(80, len(self.rules) * 74 + 8)))
        self._empty_rules.setVisible(not self.rules)
        self.rows.setVisible(bool(self.rules))
        if self.rules:
            self.rows.setCurrentRow(0)

    def _selection_changed(self, index: int) -> None:
        if hasattr(self, "_edit_button"):
            self._edit_button.setEnabled(index >= 0)
            self._remove_button.setEnabled(index >= 0)

    def _add(self) -> None:
        dialog = RuleEditorDialog(self, palette=self._palette, people=self._people)
        if dialog.exec() == QDialog.DialogCode.Accepted:
            self.rules.append(dialog.value())
            self._refresh()

    def _edit(self) -> None:
        index = self.rows.currentRow()
        if index < 0:
            return
        dialog = RuleEditorDialog(self, self.rules[index], self._palette, self._people)
        if dialog.exec() == QDialog.DialogCode.Accepted:
            self.rules[index] = dialog.value()
            self._refresh()
            self.rows.setCurrentRow(index)

    def _remove(self) -> None:
        index = self.rows.currentRow()
        if index >= 0:
            self.rules.pop(index)
            self._refresh()

    def _accept_valid(self) -> None:
        try:
            if not self.name.text().strip():
                raise ValueError(t("rules.error.name"))
            if not self.rules:
                raise ValueError(t("rules.error.empty"))
            validate_rules(self.rules)
        except (ServiceError, ValueError) as error:
            QMessageBox.warning(self, t("common.failed"), str(error))
            return
        self.accept()


class RuleSetDelegate(QStyledItemDelegate):
    """Compact two-line rows with the app's selection colours on every platform."""

    def __init__(self, palette: Palette, parent: QWidget) -> None:
        super().__init__(parent)
        self._palette = palette

    def sizeHint(self, option: QStyleOptionViewItem, index) -> QSize:  # noqa: ANN001, N802
        return QSize(option.rect.width(), 68)

    def paint(self, painter: QPainter, option: QStyleOptionViewItem, index) -> None:  # noqa: ANN001
        p = self._palette
        selected = bool(option.state & QStyle.StateFlag.State_Selected)
        hovered = bool(option.state & QStyle.StateFlag.State_MouseOver)
        rect = option.rect.adjusted(2, 2, -2, -2)
        painter.save()
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        painter.setPen(QColor(p.accent if selected else p.border))
        background = p.surface_active if selected else p.surface_hover if hovered else p.elevated
        painter.setBrush(QColor(background))
        painter.drawRoundedRect(rect, METRICS.radius_md, METRICS.radius_md)

        text_rect = rect.adjusted(METRICS.space_3, 0, -METRICS.space_3, 0)
        title_font = QFont(option.font)
        title_font.setWeight(QFont.Weight.DemiBold)
        painter.setFont(title_font)
        painter.setPen(QColor(p.text_primary))
        title = option.fontMetrics.elidedText(
            str(index.data(Qt.ItemDataRole.DisplayRole)),
            Qt.TextElideMode.ElideRight,
            text_rect.width(),
        )
        painter.drawText(
            text_rect.adjusted(0, METRICS.space_2, 0, -24),
            Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter,
            title,
        )

        subtitle_font = QFont(option.font)
        subtitle_font.setPointSize(max(9, subtitle_font.pointSize() - 1))
        painter.setFont(subtitle_font)
        painter.setPen(QColor(p.text_secondary))
        subtitle = painter.fontMetrics().elidedText(
            str(index.data(Qt.ItemDataRole.UserRole)),
            Qt.TextElideMode.ElideRight,
            text_rect.width(),
        )
        painter.drawText(
            text_rect.adjusted(0, 31, 0, -METRICS.space_2),
            Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter,
            subtitle,
        )
        painter.restore()


class RuleSetsDialog(QDialog):
    def __init__(
        self, parent: QWidget | None, service: RuleSetService, palette: Palette = LIGHT
    ) -> None:
        super().__init__(parent)
        self.setWindowTitle(t("rules.title"))
        self.setMinimumWidth(540)
        self._service = service
        self._palette = palette
        self._people = service.list_people()
        self._rows = QListWidget()
        self._rows.setObjectName("ruleSetsList")
        self._rows.setFrameShape(QFrame.Shape.NoFrame)
        self._rows.setSpacing(METRICS.space_1)
        self._rows.setStyleSheet(
            "QListWidget#ruleSetsList { background: transparent; border: none; }"
        )
        self._rows.setItemDelegate(RuleSetDelegate(palette, self._rows))
        self._rows.currentRowChanged.connect(self._update_preview)
        self._rows.itemDoubleClicked.connect(lambda _: self._edit())

        heading = PlainLabel(t("rules.manage_heading"))
        heading.setObjectName("sectionTitle")
        hint = PlainLabel(t("rules.manage_hint"))
        hint.setObjectName("mutedText")
        hint.setWordWrap(True)
        add = primary_button(t("rules.add_set"))
        add.clicked.connect(self._add)
        top = QHBoxLayout()
        words = QVBoxLayout()
        words.setSpacing(METRICS.space_1)
        words.addWidget(heading)
        words.addWidget(hint)
        top.addLayout(words, stretch=1)
        top.addWidget(add, alignment=Qt.AlignmentFlag.AlignTop)

        self._empty = PlainLabel(t("rules.empty"))
        self._empty.setObjectName("mutedText")
        self._empty.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._empty.setWordWrap(True)
        self._empty.setMinimumHeight(110)

        self._preview = QFrame()
        self._preview.setObjectName("card")
        self._preview_title = PlainLabel(t("rules.in_set"))
        self._preview_title.setObjectName("sectionTitle")
        self._preview_content = QWidget()
        self._preview_list = QVBoxLayout(self._preview_content)
        self._preview_list.setContentsMargins(0, 0, 0, 0)
        self._preview_list.setSpacing(METRICS.space_3)
        self._preview_area = QScrollArea()
        self._preview_area.setFrameShape(QFrame.Shape.NoFrame)
        self._preview_area.setWidgetResizable(True)
        self._preview_area.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self._preview_area.setStyleSheet(
            "QScrollArea { background: transparent; border: none; } "
            "QScrollArea > QWidget > QWidget { background: transparent; }"
        )
        self._preview_area.setWidget(self._preview_content)
        self._edit_button = secondary_button(t("common.edit"))
        self._remove_button = secondary_button(t("common.delete"))
        self._edit_button.clicked.connect(self._edit)
        self._remove_button.clicked.connect(self._remove)
        preview_header = QHBoxLayout()
        preview_header.addWidget(self._preview_title)
        preview_header.addStretch()
        preview_header.addWidget(self._edit_button)
        preview_header.addWidget(self._remove_button)
        preview_layout = QVBoxLayout(self._preview)
        preview_layout.setContentsMargins(*(METRICS.space_4,) * 4)
        preview_layout.setSpacing(METRICS.space_2)
        preview_layout.addLayout(preview_header)
        preview_layout.addWidget(self._preview_area)

        close = secondary_button(t("rules.done"))
        close.clicked.connect(self.accept)
        footer = QHBoxLayout()
        footer.addStretch()
        footer.addWidget(close)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(*(METRICS.space_5,) * 4)
        layout.setSpacing(METRICS.space_4)
        layout.addLayout(top)
        layout.addWidget(self._empty)
        layout.addWidget(self._rows)
        layout.addWidget(self._preview)
        layout.addLayout(footer)
        self._refresh()

    def _refresh(self, selected_id: int | None = None) -> None:
        self._sets = self._service.list_sets()
        self._rows.clear()
        for item in self._sets:
            row = QListWidgetItem(item.name)
            row.setData(Qt.ItemDataRole.UserRole, t("rules.rule_count", count=len(item.rules)))
            row.setToolTip(
                "\n".join(rule_description(rule, dict(self._people)) for rule in item.rules)
            )
            self._rows.addItem(row)
        self._rows.setFixedHeight(min(180, max(80, len(self._sets) * 74 + 8)))
        has_sets = bool(self._sets)
        self._empty.setVisible(not has_sets)
        self._rows.setVisible(has_sets)
        self._preview.setVisible(has_sets)
        if has_sets:
            index = next((i for i, item in enumerate(self._sets) if item.id == selected_id), 0)
            self._rows.setCurrentRow(index)
        else:
            self._update_preview(-1)

    def _update_preview(self, index: int) -> None:
        item = self._sets[index] if 0 <= index < len(self._sets) else None
        self._edit_button.setEnabled(item is not None)
        self._remove_button.setEnabled(item is not None)
        if item is None:
            return
        while self._preview_list.count():
            entry = self._preview_list.takeAt(0)
            if widget := entry.widget():
                widget.deleteLater()
        for rule in item.rules:
            row = QWidget()
            column = QVBoxLayout(row)
            column.setContentsMargins(0, 0, 0, 0)
            column.setSpacing(0)
            description = PlainLabel(f"•  {rule_description(rule, dict(self._people))}")
            description.setWordWrap(True)
            severity = PlainLabel(t(f"rules.severity.{rule['severity']}"))
            severity.setProperty("tone", "danger" if rule["severity"] == BLOCK else "warning")
            column.addWidget(description)
            column.addWidget(severity)
            self._preview_list.addWidget(row)
        self._preview_area.setFixedHeight(min(180, max(70, len(item.rules) * 55)))

    def _selected(self) -> RuleSetData | None:
        index = self._rows.currentRow()
        return self._sets[index] if 0 <= index < len(self._sets) else None

    def _add(self) -> None:
        self._edit_item(None)

    def _edit(self) -> None:
        if item := self._selected():
            self._edit_item(item)

    def _edit_item(self, item: RuleSetData | None) -> None:
        dialog = RuleSetEditDialog(self, item, self._palette, self._people)
        if dialog.exec() != QDialog.DialogCode.Accepted:
            return
        try:
            saved = self._service.save(dialog.name.text(), dialog.rules, item.id if item else None)
        except ServiceError as error:
            QMessageBox.warning(self, t("common.failed"), str(error))
            return
        self._refresh(saved.id)

    def _remove(self) -> None:
        item = self._selected()
        if item is None:
            return
        if (
            QMessageBox.question(self, t("rules.delete"), t("rules.delete_confirm", name=item.name))
            != QMessageBox.StandardButton.Yes
        ):
            return
        try:
            self._service.delete(item.id)
        except ServiceError as error:
            QMessageBox.warning(self, t("common.failed"), str(error))
            return
        self._refresh()


class RuleSetPickerDialog(QDialog):
    """Small themed picker used from an already open schedule."""

    def __init__(
        self, parent: QWidget | None, sets: list[RuleSetData], current: str | None, palette: Palette
    ) -> None:
        super().__init__(parent)
        self.setWindowTitle(t("rules.rule_set"))
        self.setMinimumWidth(420)
        self.choice = StyledComboBox(palette)
        self.choice.addItem(t("rules.none"), None)
        for item in sets:
            self.choice.addItem(item.name, item.id)
        self.choice.setCurrentIndex(
            next(
                (
                    index
                    for index in range(self.choice.count())
                    if self.choice.itemText(index) == current
                ),
                0,
            )
        )
        label = PlainLabel(t("rules.rule_set"))
        label.setObjectName("sectionTitle")
        hint = PlainLabel(t("rules.picker_hint"))
        hint.setObjectName("mutedText")
        hint.setWordWrap(True)
        cancel = secondary_button(t("common.cancel"))
        apply = primary_button(t("rules.apply"))
        cancel.clicked.connect(self.reject)
        apply.clicked.connect(self.accept)
        actions = QHBoxLayout()
        actions.addStretch()
        actions.addWidget(cancel)
        actions.addWidget(apply)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(*(METRICS.space_6,) * 4)
        layout.setSpacing(METRICS.space_4)
        layout.addWidget(label)
        layout.addWidget(hint)
        layout.addWidget(self.choice)
        layout.addSpacing(METRICS.space_2)
        layout.addLayout(actions)

    @property
    def rule_set_id(self) -> int | None:
        return self.choice.currentData()
