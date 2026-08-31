import sys
from pathlib import Path

from PyInstaller.building.api import COLLECT, EXE, PYZ
from PyInstaller.building.build_main import Analysis
from PyInstaller.building.osx import BUNDLE

PROJECT_ROOT = Path(SPECPATH).parent
PACKAGE_ROOT = PROJECT_ROOT / "src" / "work_scheduler"
ASSETS = PACKAGE_ROOT / "ui" / "assets"

version = (PACKAGE_ROOT / "__init__.py").read_text().split('"')[1]
icon = ASSETS / ("app_icon.icns" if sys.platform == "darwin" else "app_icon.ico")

# Migrations and assets are read from disk at runtime, so they have to travel with
# the bundle rather than being imported.
datas = [
    (str(PACKAGE_ROOT / "migrations"), "work_scheduler/migrations"),
    (str(ASSETS), "work_scheduler/ui/assets"),
    (str(PROJECT_ROOT / "LICENSE"), "."),
    (str(PROJECT_ROOT / "THIRD_PARTY_NOTICES.md"), "."),
]

analysis = Analysis(
    [str(PACKAGE_ROOT / "__main__.py")],
    pathex=[str(PROJECT_ROOT / "src")],
    datas=datas,
    hiddenimports=["work_scheduler.migrations.env"],
    # Qt ships modules this application never opens; leaving them out keeps the
    # bundle small and the launch quick.
    excludes=[
        "PySide6.QtWebEngineCore",
        "PySide6.QtWebEngineWidgets",
        "PySide6.Qt3DCore",
        "PySide6.QtMultimedia",
        "PySide6.QtQuick",
        "PySide6.QtQml",
        "tkinter",
        "pytest",
    ],
    noarchive=False,
)
pyz = PYZ(analysis.pure)

executable = EXE(
    pyz,
    analysis.scripts,
    exclude_binaries=True,
    name="Work Scheduler",
    console=False,
    icon=str(icon) if icon.is_file() else None,
)

collection = COLLECT(
    executable,
    analysis.binaries,
    analysis.datas,
    name="Work Scheduler",
)

if sys.platform == "darwin":
    bundle = BUNDLE(
        collection,
        name="Work Scheduler.app",
        icon=str(icon),
        bundle_identifier="com.eliaszpiotr.work-scheduler",
        version=version,
        info_plist={
            "CFBundleShortVersionString": version,
            "CFBundleVersion": version,
            "NSHighResolutionCapable": True,
            "LSMinimumSystemVersion": "13.0",
        },
    )
