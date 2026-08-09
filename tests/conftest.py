import os

# Qt must run headless in tests; set before PySide6 is imported anywhere.
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import pytest  # noqa: E402

from work_scheduler.main import create_application  # noqa: E402


@pytest.fixture(scope="session")
def application():
    """The single QApplication plus its main window, shared by all tests."""
    app, window = create_application([])
    yield app, window
    window.close()
