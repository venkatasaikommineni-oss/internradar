#!/usr/bin/env python3
"""
SQLite-to-PostgreSQL Migration Script for InternRadar.

Safely migrates data from local SQLite database into PostgreSQL target.
Features:
- Foreign-key dependency ordering.
- Explicit primary key (id) preservation.
- PostgreSQL sequence synchronization post-migration.
- Type normalization for JSON and naive UTC DateTime fields.
- Atomic transaction with automatic rollback on error.
- Safety flags: skips development user accounts and tokens unless explicitly requested with --include-users.
- Dry-run validation mode (--dry-run).
"""

from __future__ import annotations

import argparse
import json
import logging
import os
import sqlite3
import sys
from datetime import datetime
from typing import Any

# Ensure project root is in sys.path
_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _ROOT not in sys.path:
    sys.path.insert(0, _ROOT)

from sqlalchemy import create_engine, inspect, text

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
log = logging.getLogger("migration")


def parse_datetime(val: Any) -> datetime | None:
    if not val:
        return None
    if isinstance(val, datetime):
        return val
    # Handle ISO or SQLite string formats
    clean = str(val).strip().replace("Z", "")
    for fmt in ("%Y-%m-%d %H:%M:%S.%f", "%Y-%m-%d %H:%M:%S", "%Y-%m-%dT%H:%M:%S.%f", "%Y-%m-%dT%H:%M:%S"):
        try:
            return datetime.strptime(clean, fmt)
        except ValueError:
            continue
    try:
        return datetime.fromisoformat(clean)
    except Exception:
        log.warning("Could not parse datetime string: %s", val)
        return None


def parse_json(val: Any, default: Any = None) -> Any:
    if val is None:
        return default
    if isinstance(val, (dict, list)):
        return val
    if isinstance(val, str):
        try:
            return json.loads(val)
        except Exception:
            return default
    return default


def normalize_postgres_url(url: str) -> str:
    if url.startswith("postgres://"):
        return url.replace("postgres://", "postgresql://", 1)
    return url


def migrate(sqlite_path: str, target_url: str, include_users: bool = False, dry_run: bool = False) -> None:
    if not os.path.exists(sqlite_path):
        log.error("SQLite database file not found: %s", sqlite_path)
        sys.exit(1)

    target_url = normalize_postgres_url(target_url)
    log.info("Connecting to target database...")
    target_engine = create_engine(target_url, pool_pre_ping=True)

    # Initialize target tables if needed
    import app.models  # noqa: F401 - registers models on Base.metadata
    from app.database import Base
    Base.metadata.create_all(target_engine)

    # Validate target connection
    insp = inspect(target_engine)
    target_tables = set(insp.get_table_names())
    log.info("Target database connected. Found tables: %s", ", ".join(sorted(target_tables)) or "none")

    # Connect to source SQLite
    sqlite_conn = sqlite3.connect(sqlite_path)
    sqlite_conn.row_factory = sqlite3.Row
    sqlite_cur = sqlite_conn.cursor()

    source_tables = {
        row[0]
        for row in sqlite_cur.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%'"
        ).fetchall()
    }
    log.info("Source SQLite tables: %s", ", ".join(sorted(source_tables)))

    # Define table ordering for referential integrity
    # Table specifications: (table_name, requires_users_flag, json_columns, date_columns)
    table_specs = [
        ("internships", False, ["skills", "grad_years"], ["deadline", "collected_at", "updated_at", "last_seen_at", "last_checked_at"]),
        ("import_runs", False, ["reject_reasons"], ["started_at", "finished_at"]),
        ("users", True, ["skills", "specializations", "desired_roles", "work_types", "resume_skills"], ["created_at", "updated_at", "last_login"]),
        ("email_verifications", True, [], ["expires_at", "token_expires_at", "created_at"]),
        ("refresh_tokens", True, [], ["expires_at", "created_at"]),
        ("saved_internships", True, [], ["saved_at"]),
        ("user_activities", True, [], ["timestamp"]),
        ("user_connections", True, [], ["created_at", "updated_at"]),
    ]

    total_migrated = 0

    try:
        with target_engine.begin() as conn:
            for table_name, requires_users, json_cols, date_cols in table_specs:
                if table_name not in source_tables:
                    log.info("Skipping '%s': table not found in source SQLite.", table_name)
                    continue

                if requires_users and not include_users:
                    log.info("Skipping '%s': user data omitted (use --include-users to migrate accounts).", table_name)
                    continue

                if table_name not in target_tables:
                    log.warning("Table '%s' does not exist in target database. Ensure Base.metadata.create_all has run.", table_name)
                    continue

                # Query all rows from SQLite
                rows = sqlite_cur.execute(f'SELECT * FROM "{table_name}" ORDER BY id ASC').fetchall()
                if not rows:
                    log.info("Table '%s' has 0 rows in source. Nothing to copy.", table_name)
                    continue

                col_names = [col[0] for col in sqlite_cur.description]
                log.info("Migrating '%s': %d row(s)...", table_name, len(rows))

                # Check existing target IDs to prevent duplicate PK errors
                existing_ids_res = conn.execute(text(f'SELECT id FROM "{table_name}"')).fetchall()
                existing_ids = {r[0] for r in existing_ids_res}

                inserted_count = 0
                for row in rows:
                    row_dict = dict(row)
                    row_id = row_dict.get("id")

                    if row_id in existing_ids:
                        continue  # Skip existing record without failure

                    # Normalize JSON fields
                    for jcol in json_cols:
                        if jcol in row_dict:
                            default_val = [] if jcol != "reject_reasons" else {}
                            parsed = parse_json(row_dict[jcol], default=default_val)
                            row_dict[jcol] = json.dumps(parsed) if not target_engine.dialect.name == "postgresql" else parsed

                    # Normalize DateTime fields
                    for dcol in date_cols:
                        if dcol in row_dict:
                            row_dict[dcol] = parse_datetime(row_dict[dcol])

                    # Build parameterized insert
                    cols = [c for c in col_names if c in row_dict]
                    col_placeholders = ", ".join(f'"{c}"' for c in cols)
                    val_placeholders = ", ".join(f":{c}" for c in cols)
                    insert_stmt = text(f'INSERT INTO "{table_name}" ({col_placeholders}) VALUES ({val_placeholders})')

                    if not dry_run:
                        conn.execute(insert_stmt, row_dict)
                    inserted_count += 1

                log.info("  ✓ '%s': %d inserted (%d previously existed)", table_name, inserted_count, len(existing_ids))
                total_migrated += inserted_count

                # Synchronize PostgreSQL auto-increment sequences so future inserts don't collide
                if not dry_run and target_engine.dialect.name == "postgresql" and inserted_count > 0:
                    seq_sync_stmt = text(
                        f"""
                        SELECT setval(
                            pg_get_serial_sequence('"{table_name}"', 'id'),
                            COALESCE(MAX(id), 1),
                            MAX(id) IS NOT NULL
                        ) FROM "{table_name}";
                        """
                    )
                    try:
                        conn.execute(seq_sync_stmt)
                    except Exception as seq_err:
                        log.debug("Note: Could not update sequence on %s: %s", table_name, seq_err)

            if dry_run:
                log.info("[DRY RUN] Completed simulation. No changes were committed.")
            else:
                log.info("Migration transaction completed successfully. Total records copied: %d", total_migrated)

    except Exception:
        log.exception("Migration failed! Entire transaction has been rolled back.")
        sys.exit(1)
    finally:
        sqlite_conn.close()


def main():
    parser = argparse.ArgumentParser(description="InternRadar SQLite to PostgreSQL migration tool")
    parser.add_argument("--sqlite-path", default="internradar.db", help="Path to local SQLite database (default: internradar.db)")
    parser.add_argument("--target-url", default=os.getenv("TARGET_DATABASE_URL", ""), help="Target PostgreSQL connection string")
    parser.add_argument("--include-users", action="store_true", help="Include development user accounts and tokens")
    parser.add_argument("--dry-run", action="store_true", help="Simulate migration without committing changes")

    args = parser.parse_args()

    if not args.target_url:
        print("Error: --target-url or TARGET_DATABASE_URL environment variable is required.")
        print("Example: python scripts/migrate_sqlite_to_postgres.py --target-url postgresql://user:pass@host:5432/dbname")
        sys.exit(1)

    migrate(args.sqlite_path, args.target_url, include_users=args.include_users, dry_run=args.dry_run)


if __name__ == "__main__":
    main()
