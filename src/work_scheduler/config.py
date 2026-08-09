from dataclasses import dataclass

from work_scheduler import __version__


@dataclass(frozen=True, slots=True)
class AppConfig:
    app_name: str = "Work Scheduler"
    organization_name: str = "Work Scheduler"
    version: str = __version__
