from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QDialog,
    QHBoxLayout,
    QLineEdit,
    QVBoxLayout,
    QWidget,
)

from work_scheduler.database.models import Employee, Profession
from work_scheduler.ui.components import (
    PROFESSION_LABELS,
    PlainLabel,
    primary_button,
    secondary_button,
)
from work_scheduler.ui.theme import METRICS


class EmployeeDialog(QDialog):
    def __init__(self, parent: QWidget | None = None, employee: Employee | None = None) -> None:
        super().__init__(parent)
        self._employee = employee

        self.setWindowTitle("Edytuj pracownika" if employee else "Nowy pracownik")
        self.setModal(True)
        self.setFixedWidth(METRICS.dialog_width)

        self._first_name = QLineEdit()
        self._last_name = QLineEdit()
        self._profession = QComboBox()
        self._active = QCheckBox("Aktywny")

        for profession, label in PROFESSION_LABELS.items():
            self._profession.addItem(label, profession)

        self._build()
        self._fill(employee)

    def _build(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(*(METRICS.space_6,) * 4)
        layout.setSpacing(METRICS.space_4)

        for label, field in (
            ("Imię", self._first_name),
            ("Nazwisko", self._last_name),
            ("Stanowisko", self._profession),
        ):
            layout.addLayout(self._field(label, field))

        self._active.setToolTip("Nieaktywni nie pojawiają się przy tworzeniu nowego grafiku")
        layout.addWidget(self._active)
        layout.addStretch()

        cancel = secondary_button("Anuluj")
        cancel.clicked.connect(self.reject)
        save = primary_button("Zapisz")
        save.setDefault(True)
        save.clicked.connect(self.accept)

        buttons = QHBoxLayout()
        buttons.setSpacing(METRICS.space_2)
        buttons.addStretch()
        buttons.addWidget(cancel)
        buttons.addWidget(save)
        layout.addLayout(buttons)

    @staticmethod
    def _field(text: str, widget: QWidget) -> QVBoxLayout:
        column = QVBoxLayout()
        column.setSpacing(METRICS.space_2)

        label = PlainLabel(text)
        label.setObjectName("fieldLabel")
        label.setBuddy(widget)
        widget.setAccessibleName(text)

        column.addWidget(label)
        column.addWidget(widget)
        return column

    def _fill(self, employee: Employee | None) -> None:
        if employee is None:
            self._active.setChecked(True)
            self._first_name.setFocus(Qt.FocusReason.OtherFocusReason)
            return

        self._first_name.setText(employee.first_name)
        self._last_name.setText(employee.last_name)
        self._profession.setCurrentIndex(self._profession.findData(employee.profession))
        self._active.setChecked(employee.active)

    @property
    def first_name(self) -> str:
        return self._first_name.text()

    @property
    def last_name(self) -> str:
        return self._last_name.text()

    @property
    def profession(self) -> Profession:
        return self._profession.currentData()

    @property
    def active(self) -> bool:
        return self._active.isChecked()
