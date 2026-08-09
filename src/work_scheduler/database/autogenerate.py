from typing import Any

from sqlalchemy import Enum, MetaData


def enum_constraint_names(metadata: MetaData) -> frozenset[str]:
    return frozenset(
        column.type.name
        for table in metadata.tables.values()
        for column in table.columns
        if isinstance(column.type, Enum) and column.type.name
    )


def build_include_object(metadata: MetaData) -> Any:
    """Callable for Alembic's ``include_object`` option."""
    skipped = enum_constraint_names(metadata)

    def include_object(
        _object: Any, name: str | None, type_: str, _reflected: bool, _compare_to: Any
    ) -> bool:
        return not (type_ == "check_constraint" and name in skipped)

    return include_object
