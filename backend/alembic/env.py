import logging
from logging.config import fileConfig

from alembic.script import ScriptDirectory
from sqlalchemy import create_engine, pool

from alembic import context
from app.config import get_settings
from app.db import Base, normalize_url
from app.models import Run  # noqa: F401  (registers the table on Base.metadata)

config = context.config
if config.config_file_name is not None:
    fileConfig(config.config_file_name)

logger = logging.getLogger("alembic.env")

# On Render the API only starts after migrations finish, and a deploy that doesn't open
# its port in time is rolled back. So a migration must never wait forever on a lock held
# by the old instance: fail fast with a clear error instead.
LOCK_TIMEOUT = "20s"
STATEMENT_TIMEOUT = "120s"

target_metadata = Base.metadata
url = normalize_url(get_settings().database_url)


def run_migrations_offline() -> None:
    context.configure(url=url, target_metadata=target_metadata, literal_binds=True)
    with context.begin_transaction():
        context.run_migrations()


def _known_revisions() -> set[str]:
    return {r.revision for r in ScriptDirectory.from_config(config).walk_revisions()}


def run_migrations_online() -> None:
    engine = create_engine(url, poolclass=pool.NullPool)
    with engine.connect() as connection:
        if connection.dialect.name == "postgresql":
            connection.exec_driver_sql(f"SET lock_timeout = '{LOCK_TIMEOUT}'")
            connection.exec_driver_sql(f"SET statement_timeout = '{STATEMENT_TIMEOUT}'")
            connection.commit()  # session settings; alembic then opens its own transaction
        context.configure(connection=connection, target_metadata=target_metadata)
        current = context.get_context().get_current_revision()
        logger.info(
            "Database at revision %s; code's latest is %s", current, context.get_head_revision()
        )
        if current is not None and current not in _known_revisions():
            logger.error(
                "The database is at migration %s, which this version of the code doesn't "
                "have. A newer deploy migrated the database and then an older version was "
                "started (often after a failed deploy rolled back). Deploy the latest commit.",
                current,
            )
        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
