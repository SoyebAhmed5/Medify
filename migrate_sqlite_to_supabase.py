
import os
import sys
from pathlib import Path

from sqlalchemy import create_engine, inspect, MetaData, select, text
from sqlalchemy.engine import make_url

# Import model metadata only; do not import app.py (it creates the Flask app).
from models import db

ROOT = Path(__file__).resolve().parent
SOURCE_DB = Path(os.getenv("SQLITE_SOURCE", ROOT / "instance" / "donation.db"))
TARGET_URL = os.getenv("SUPABASE_DATABASE_URL", "").strip()
BATCH_SIZE = 500


def normalize_target_url(raw_url: str) -> str:
    if not raw_url:
        raise RuntimeError("Set SUPABASE_DATABASE_URL before running the migration.")
    url = make_url(raw_url)
    if url.drivername in ("postgres", "postgresql"):
        url = url.set(drivername="postgresql+psycopg")
    if not url.drivername.startswith("postgresql"):
        raise RuntimeError("Target must be a PostgreSQL connection URL from Supabase.")
    # Require encrypted database connections.
    query = dict(url.query)
    query.setdefault("sslmode", "require")
    return url.set(query=query).render_as_string(hide_password=False)


def main():
    if not SOURCE_DB.is_file():
        raise FileNotFoundError(f"SQLite database not found: {SOURCE_DB}")
    target_url = normalize_target_url(TARGET_URL)

    source_engine = create_engine(f"sqlite:///{SOURCE_DB.as_posix()}")
    target_engine = create_engine(target_url, pool_pre_ping=True)

    try:
        source_meta = MetaData()
        source_meta.reflect(bind=source_engine)
        model_tables = list(db.metadata.sorted_tables)

        expected = {table.name for table in model_tables}
        available = set(source_meta.tables)
        missing = expected - available
        if missing:
            raise RuntimeError("SQLite database is missing expected tables: " + ", ".join(sorted(missing)))

        # Create model-defined tables in Supabase if they do not already exist.
        db.metadata.create_all(target_engine)

        # Do not merge into an existing populated database: this prevents accidental
        # duplicate records or overwriting data during a repeated run.
        target_inspector = inspect(target_engine)
        for table in model_tables:
            if table.name in target_inspector.get_table_names(schema="public"):
                with target_engine.connect() as conn:
                    count = conn.execute(text(f'SELECT COUNT(*) FROM public."{table.name}"')).scalar_one()
                if count:
                    raise RuntimeError(
                        f"Target table public.{table.name} already contains {count} rows. "
                        "Use a fresh/empty Supabase database or plan a separate merge."
                    )

        print("Starting SQLite -> Supabase copy...")
        with target_engine.begin() as target_conn:
            for target_table in model_tables:
                source_table = source_meta.tables[target_table.name]
                source_columns = {column.name for column in source_table.columns}
                target_columns = {column.name for column in target_table.columns}
                if source_columns != target_columns:
                    raise RuntimeError(
                        f"Column mismatch in {target_table.name}: "
                        f"SQLite={sorted(source_columns)}, model={sorted(target_columns)}"
                    )

                rows_result = source_engine.connect()
                try:
                    result = rows_result.execute(select(source_table))
                    copied = 0
                    while True:
                        batch = result.fetchmany(BATCH_SIZE)
                        if not batch:
                            break
                        payload = [
                            {column.name: row._mapping[column.name] for column in target_table.columns}
                            for row in batch
                        ]
                        target_conn.execute(target_table.insert(), payload)
                        copied += len(payload)
                finally:
                    rows_result.close()
                print(f"  {target_table.name}: {copied} rows")

            # Reset PostgreSQL identity/serial sequences to the imported maximum IDs.
            for table in model_tables:
                primary_keys = list(table.primary_key.columns)
                if len(primary_keys) == 1 and isinstance(primary_keys[0].type.python_type, type):
                    pk = primary_keys[0]
                    if pk.type.python_type is int:
                        max_id = target_conn.execute(
                            text(f'SELECT MAX("{pk.name}") FROM public."{table.name}"')
                        ).scalar_one()
                        if max_id is not None:
                            sequence = target_conn.execute(
                                text("SELECT pg_get_serial_sequence(:table_name, :column_name)"),
                                {"table_name": f"public.{table.name}", "column_name": pk.name},
                            ).scalar_one()
                            if sequence:
                                target_conn.execute(
                                    text("SELECT setval(CAST(:sequence_name AS regclass), :last_id, true)"),
                                    {"sequence_name": sequence, "last_id": max_id},
                                )

        print("\nMigration completed. Verify row counts in Supabase Table Editor.")
        print("SQLite source was left unchanged.")
    finally:
        source_engine.dispose()
        target_engine.dispose()


if __name__ == "__main__":
    try:
        main()
    except Exception as exc:
        print(f"\nMIGRATION STOPPED: {exc}", file=sys.stderr)
        sys.exit(1)
