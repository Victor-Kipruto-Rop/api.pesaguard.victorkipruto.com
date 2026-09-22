"""Alembic environment configuration for PesaGuard database migrations."""

from __future__ import annotations

import os
import sys
from logging.config import fileConfig
from pathlib import Path

from sqlalchemy import engine_from_config, make_url, pool
from alembic import context
from alembic.ddl.impl import _impls
from alembic.ddl.postgresql import PostgresqlImpl
from sqlalchemy import Column, MetaData, PrimaryKeyConstraint, String, Table


class PesaGuardPostgresqlImpl(PostgresqlImpl):
    """Allow descriptive migration IDs longer than Alembic's 32-char default."""

    def version_table_impl(self, *, version_table, version_table_schema, version_table_pk, **kw):
        table = Table(
            version_table,
            MetaData(),
            Column("version_num", String(255), nullable=False),
            schema=version_table_schema,
        )
        if version_table_pk:
            table.append_constraint(
                PrimaryKeyConstraint("version_num", name=f"{version_table}_pkc")
            )
        return table


_impls["postgresql"] = PesaGuardPostgresqlImpl

# this is the Alembic Config object, which provides
# access to the values within the .ini file in use.
config = context.config

# Interpret the config file for Python logging.
if config.config_file_name is not None:
    fileConfig(config.config_file_name)

# Ensure application modules can be resolved for autogenerate support.
project_root = str(Path(__file__).resolve().parents[1])
if project_root not in sys.path:
    sys.path.insert(0, project_root)

from pesaguard_backend_pipeline.models import Base
from pesaguard_backend_pipeline.communications import models as communications_models  # noqa: F401

target_metadata = Base.metadata


def get_database_url() -> str:
    """Resolve the migration URL consistently for offline and online modes."""
    if not (url := os.environ.get("DATABASE_URL") or config.get_main_option("sqlalchemy.url")):
        raise ValueError("Database URL not specified. Set DATABASE_URL or sqlalchemy.url.")
    return url


def run_migrations_offline() -> None:
    """Run migrations in 'offline' mode.

    Configures the context with just a URL and not an Engine, though an
    Engine is acceptable here as well. By skipping engine creation
    we don't even need a DB connection to generate SQL scripts.
    """
    url = get_database_url()

    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
    )

    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    """Run migrations in 'online' mode.

    In this scenario we need to create an Engine and associate a connection
    with the context.
    """
    database_url = get_database_url()
    drivername = make_url(database_url).drivername
    if drivername.endswith(("+asyncpg", "+aiomysql", "+aiosqlite", "_async")):
        raise ValueError(
            "Alembic online migrations require a synchronous database driver; "
            f"got {drivername!r}."
        )

    ini_section = config.get_section(config.config_ini_section) or {}
    ini_section["sqlalchemy.url"] = database_url

    connectable = engine_from_config(
        ini_section,
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )

    with connectable.connect() as connection:
        context.configure(
            connection=connection,
            target_metadata=target_metadata,
            compare_type=True,  # Detect column type changes during autogenerate
        )

        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
