from enum import Enum

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QDialog,
    QHBoxLayout,
    QLabel,
    QScrollArea,
    QVBoxLayout,
    QWidget,
)

from work_scheduler.services.audit import Audit, Finding
from work_scheduler.ui.components import primary_button, secondary_button
from work_scheduler.ui.theme import METRICS, Palette

MAX_LIST_HEIGHT = 220


class Outcome(Enum):
    CANCEL = "CANCEL"
    CLOSE = "CLOSE"
    CLOSE_AND_SAVE = "CLOSE_AND_SAVE"


class FinalizeDialog(QDialog):
    """What the schedule looks like before it is closed, and the three ways out.

    Nothing here refuses to close a schedule. Problems only change what the window
    says first and which button the Enter key lands on.
    """

    def __init__(self, parent: QWidget | None, audit: Audit, palette: Palette) -> None:
        super().__init__(parent)
        self._audit = audit
        self._outcome = Outcome.CANCEL

        self.setWindowTitle("Zakończ grafik")
        self.setMinimumWidth(METRICS.dialog_width)
        self._build(palette)

    @property
    def outcome(self) -> Outcome:
        return self._outcome

    def _build(self, palette: Palette) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(
            METRICS.space_6, METRICS.space_5, METRICS.space_6, METRICS.space_5
        )
        layout.setSpacing(METRICS.space_3)

        heading = QLabel(self._headline())
        heading.setObjectName("emptyTitle")
        heading.setWordWrap(True)
        layout.addWidget(heading)

        summary = QLabel(self._summary())
        summary.setObjectName("mutedText")
        summary.setWordWrap(True)
        layout.addWidget(summary)

        if self._audit.findings:
            layout.addWidget(self._findings())

        layout.addLayout(self._buttons(palette))

    def _headline(self) -> str:
        if self._audit.problems:
            return "Grafik wygląda na niedokończony"
        if self._audit.notes:
            return "Grafik jest gotowy, ale zerknij na uwagi"
        return "Grafik jest gotowy"

    def _summary(self) -> str:
        if self._audit.problems:
            return (
                "Możesz go mimo to zamknąć — zamknięcie niczego nie blokuje i w każdej "
                "chwili da się wrócić do edycji."
            )
        if self._audit.notes:
            return "Żadna z uwag nie stoi na przeszkodzie, żeby grafik zamknąć i wydrukować."
        return "Sprawdzenie nie wykazało niczego. Można drukować."

    def _findings(self) -> QWidget:
        body = QWidget()
        column = QVBoxLayout(body)
        column.setContentsMargins(0, 0, 0, 0)
        column.setSpacing(METRICS.space_1)

        for finding in [*self._audit.problems, *self._audit.notes]:
            column.addWidget(self._line(finding))
        column.addStretch()

        area = QScrollArea()
        area.setWidget(body)
        area.setWidgetResizable(True)
        area.setFrameShape(QScrollArea.Shape.NoFrame)
        area.setMaximumHeight(MAX_LIST_HEIGHT)
        area.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        return area

    @staticmethod
    def _line(finding: Finding) -> QLabel:
        label = QLabel(f"·  {finding.text}")
        label.setWordWrap(True)
        # The same tone the grid already uses for a day that cannot stand as it is.
        label.setProperty("tone", "danger" if finding.blocking else None)
        label.setObjectName("" if finding.blocking else "mutedText")
        return label

    def _buttons(self, palette: Palette) -> QHBoxLayout:
        save = primary_button("Zamknij i zapisz PDF", "check", palette)
        close = secondary_button("Tylko zamknij")
        cancel = secondary_button("Anuluj")

        save.clicked.connect(lambda: self._finish(Outcome.CLOSE_AND_SAVE))
        close.clicked.connect(lambda: self._finish(Outcome.CLOSE))
        cancel.clicked.connect(self.reject)

        # With problems on the list, Enter must not close the schedule by accident.
        (cancel if self._audit.problems else save).setDefault(True)

        row = QHBoxLayout()
        row.setSpacing(METRICS.space_2)
        row.addWidget(cancel)
        row.addStretch()
        row.addWidget(close)
        row.addWidget(save)
        return row

    def _finish(self, outcome: Outcome) -> None:
        self._outcome = outcome
        self.accept()
