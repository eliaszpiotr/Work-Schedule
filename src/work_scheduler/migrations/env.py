from logging.config import fileConfig

from alembic import context
from sqlalchemy import Engine

from work_scheduler.config import AppConfig
from work_scheduler.database.autogenerate import build_include_object
from work_scheduler.database.base import Base
from work_scheduler.database.session import (
    create_database_engine,
    create_engine_for_url,
    database_url,
)

# Importing the models registers every table on Base.metadata.
import work_scheduler.database.models  # noqa: F401  isort:skip

config = context.config

if config.config_file_name is not None and config.attributes.get("configure_logger", True):
    fileConfig(config.config_file_name)

target_metadata = Base.metadata
include_object = build_include_object(target_metadata)


def _url() -> str:
    """Whatever the caller configured, otherwise the application database."""
    return config.get_main_option("sqlalchemy.url") or database_url(AppConfig().database_path)


def _engine() -> Engine:
    configured = config.get_main_option("sqlalchemy.url")
    if configured:
        return create_engine_for_url(configured)
    # Going through the path creates the application data directory if it is missing.
    return create_database_engine(AppConfig().database_path)


def run_migrations_offline() -> None:
    context.configure(
        url=_url(),
        target_metadata=target_metadata,
        include_object=include_object,
        literal_binds=True,
        render_as_batch=True,
        dialect_opts={"paramstyle": "named"},
    )
    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    engine = _engine()
    with engine.connect() as connection:
        context.configure(
            connection=connection,
            target_metadata=target_metadata,
            include_object=include_object,
            # SQLite cannot ALTER most things; batch mode rebuilds the table instead.
            render_as_batch=True,
        )
        with context.begin_transaction():
            context.run_migrations()
    engine.dispose()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
