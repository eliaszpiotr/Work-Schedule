from sqlalchemy import JSON, String
from sqlalchemy.orm import Mapped, mapped_column

from work_scheduler.database.base import Base, TimestampMixin


class RuleSet(Base, TimestampMixin):
    """Reusable rule definitions. Schedules keep a separate snapshot."""

    __tablename__ = "rule_sets"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(120), unique=True)
    rules: Mapped[list[dict]] = mapped_column(JSON, nullable=False, default=list)
