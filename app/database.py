import logging

from sqlalchemy import create_engine, event, inspect, text
from sqlalchemy.orm import DeclarativeBase, sessionmaker

from .config import settings

def normalize_database_url(url: str) -> str:
    """Normalize database connection string.

    Two transformations are applied for PostgreSQL URLs:
    1. Render (and other PaaS) supply 'postgres://' which SQLAlchemy 2.0 rejects
       — normalize to 'postgresql://'.
    2. Pin the psycopg2 driver explicitly ('postgresql+psycopg2://') so that
       SQLAlchemy 2.0 never auto-selects psycopg (v3), which is not installed.

    SQLite URLs are returned unchanged.
    """
    if url.startswith("postgres://"):
        url = url.replace("postgres://", "postgresql://", 1)
    if url.startswith("postgresql://"):
        url = url.replace("postgresql://", "postgresql+psycopg2://", 1)
    return url


_db_url = normalize_database_url(settings.database_url)
_is_sqlite = _db_url.startswith("sqlite")

engine = create_engine(
    _db_url,
    connect_args={"check_same_thread": False, "timeout": 30} if _is_sqlite else {},
    pool_pre_ping=True,
)

if _is_sqlite:

    @event.listens_for(engine, "connect")
    def _sqlite_pragmas(dbapi_conn, _):
        cur = dbapi_conn.cursor()
        cur.execute("PRAGMA busy_timeout=30000")
        cur.execute("PRAGMA journal_mode=WAL")
        cur.execute("PRAGMA synchronous=NORMAL")
        cur.execute("PRAGMA foreign_keys=ON")
        cur.close()



SessionLocal = sessionmaker(engine, autoflush=False, expire_on_commit=False)


class Base(DeclarativeBase):
    pass


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


log = logging.getLogger("internradar.db")


def backfill_defaults(bind=None) -> None:
    """Safe, idempotent migration update for existing user rows across SQLite and PostgreSQL.
    Guarantees boolean flags (is_admin, email_verified, is_active, is_onboarded,
    notify_new_matches, notify_deadline) are never NULL in production."""
    bind = bind or engine
    insp = inspect(bind)
    if not insp.has_table("users"):
        return
    try:
        with bind.begin() as conn:
            val_false = 0 if bind.dialect.name == "sqlite" else False
            val_true = 1 if bind.dialect.name == "sqlite" else True
            conn.execute(
                text("UPDATE users SET is_admin = :f WHERE is_admin IS NULL"),
                {"f": val_false},
            )
            conn.execute(
                text("UPDATE users SET email_verified = :f WHERE email_verified IS NULL"),
                {"f": val_false},
            )
            conn.execute(
                text("UPDATE users SET is_active = :t WHERE is_active IS NULL"),
                {"t": val_true},
            )
            conn.execute(
                text("UPDATE users SET is_onboarded = :f WHERE is_onboarded IS NULL"),
                {"f": val_false},
            )
            conn.execute(
                text("UPDATE users SET notify_new_matches = :t WHERE notify_new_matches IS NULL"),
                {"t": val_true},
            )
            conn.execute(
                text("UPDATE users SET notify_deadline = :t WHERE notify_deadline IS NULL"),
                {"t": val_true},
            )
    except Exception as e:
        log.warning("backfill_defaults error (ignoring if columns still migrating): %s", e)


def ensure_columns(bind=None) -> list[str]:
    """create_all() never alters existing tables, so a database created by an older
    version would lack newly added columns. Add any missing NULLABLE column (safe on
    SQLite and PostgreSQL). Returns what it added. Replace with Alembic before production."""
    bind = bind or engine
    insp = inspect(bind)
    added = []
    with bind.begin() as conn:
        for table in Base.metadata.sorted_tables:
            if not insp.has_table(table.name):
                continue
            have = {c["name"] for c in insp.get_columns(table.name)}
            for col in table.columns:
                if col.name in have:
                    continue
                if not col.nullable and col.server_default is None:
                    log.warning("cannot auto-add NOT NULL column %s.%s - migrate manually", table.name, col.name)
                    continue
                default_clause = ""
                if col.server_default is not None:
                    arg = col.server_default.arg
                    default_text = arg.text if hasattr(arg, "text") else str(arg)
                    default_clause = f" DEFAULT {default_text}"
                ddl = f'ALTER TABLE "{table.name}" ADD COLUMN "{col.name}" {col.type.compile(dialect=bind.dialect)}{default_clause}'
                conn.execute(text(ddl))
                added.append(f"{table.name}.{col.name}")
    if added:
        log.info("added missing columns: %s", ", ".join(added))
    backfill_defaults(bind)
    return added

