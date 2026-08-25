from PySide6.QtWidgets import QLabel, QVBoxLayout, QWidget

from work_scheduler.services import OpeningHoursService, ServiceError
from work_scheduler.ui.components import PageHeader, primary_button, restyle
from work_scheduler.ui.settings.opening_hours_editor import OpeningHoursEditor
from work_scheduler.ui.theme import METRICS, Palette


class SettingsView(QWidget):
    def __init__(self, service: OpeningHoursService, palette: Palette) -> None:
        super().__init__()
        self.setObjectName("workspace")
        self._service = service
        self._palette = palette

        self._editor = OpeningHoursEditor(service.week())
        self._save = primary_button("Zapisz")
        self._status = QLabel()
        self._build()

    def _build(self) -> None:
        header = PageHeader("Ustawienia")
        self._save.clicked.connect(self.save)
        header.add_action(self._save)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)
        layout.addWidget(header)

        section = QLabel("Godziny otwarcia")
        section.setObjectName("emptyTitle")
        hint = QLabel(
            "Nowe grafiki dostają te godziny jako punkt wyjścia. "
            "Zmiana tutaj nie rusza grafików już utworzonych."
        )
        hint.setObjectName("mutedText")
        hint.setWordWrap(True)

        body = QVBoxLayout()
        body.setContentsMargins(METRICS.space_6, METRICS.space_5, METRICS.space_6, METRICS.space_6)
        body.setSpacing(METRICS.space_3)
        body.addWidget(section)
        body.addWidget(hint)
        body.addSpacing(METRICS.space_2)
        body.addWidget(self._editor)
        body.addSpacing(METRICS.space_2)
        body.addWidget(self._status)
        body.addStretch()
        layout.addLayout(body)

    def apply_palette(self, palette: Palette) -> None:
        self._palette = palette

    def reload(self) -> None:
        self._editor.set_week(self._service.week())
        self._say("", tone="")

    def save(self) -> None:
        try:
            self._service.save(self._editor.week())
        except ServiceError as error:
            self._say(str(error), tone="danger")
            return

        self._say("Zapisano godziny otwarcia.", tone="success")

    def _say(self, message: str, *, tone: str) -> None:
        """A line under the form rather than a modal box; saving is not worth a click."""
        self._status.setText(message)
        self._status.setProperty("tone", tone)
        restyle(self._status)
