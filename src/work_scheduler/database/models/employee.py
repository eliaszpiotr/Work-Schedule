from enum import StrEnum
from typing import TYPE_CHECKING

from sqlalchemy import Boolean, Enum, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from work_scheduler.database.base import Base, TimestampMixin

if TYPE_CHECKING:
    from work_scheduler.database.models.schedule_employee import ScheduleEmployee


class Profession(StrEnum):
    PHARMACIST = "PHARMACIST"
    TECHNICIAN = "TECHNICIAN"


class Employee(Base, TimestampMixin):
    __tablename__ = "employees"

    id: Mapped[int] = mapped_column(primary_key=True)
    first_name: Mapped[str] = mapped_column(String(80))
    last_name: Mapped[str] = mapped_column(String(80))
    profession: Mapped[Profession] = mapped_column(
        Enum(Profession, name="profession", create_constraint=True, validate_strings=True)
    )
    active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)

    schedule_entries: Mapped[list["ScheduleEmployee"]] = relationship(
        back_populates="employee", passive_deletes=True
    )

    @property
    def full_name(self) -> str:
        return f"{self.first_name} {self.last_name}"
