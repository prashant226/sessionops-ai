"""Minimal SQLite column migration.

There's no Alembic in this prototype -- Base.metadata.create_all() only
creates missing *tables*, never adds columns to a table that already
exists. Since the dev database persists real state across restarts (the
Google OAuth token, in particular), wiping it on every schema change isn't
an option. This adds any columns the current models define but the live
database is missing, using SQLite's ADD COLUMN support. Safe to run every
startup: a no-op once the columns already exist.
"""

from __future__ import annotations

from sqlalchemy import inspect, text
from sqlalchemy.engine import Engine


def add_missing_columns(engine: Engine, base) -> None:
    inspector = inspect(engine)
    existing_tables = set(inspector.get_table_names())

    with engine.begin() as conn:
        for table in base.metadata.sorted_tables:
            if table.name not in existing_tables:
                continue  # brand-new table, create_all() already handled it
            existing_cols = {c["name"] for c in inspector.get_columns(table.name)}
            for column in table.columns:
                if column.name in existing_cols:
                    continue
                col_type = column.type.compile(engine.dialect)
                conn.execute(text(f'ALTER TABLE "{table.name}" ADD COLUMN "{column.name}" {col_type}'))
