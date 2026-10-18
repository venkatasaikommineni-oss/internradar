import logging

from sqlalchemy import create_engine, event, inspect, text
from sqlalchemy.orm import DeclarativeBase, sessionmaker

from .config import settings

_is_sqlite = settings.database_url.startswith("sqlite")

engine = create_engine(
    settings.database_url,
    connect_args={"check_same_thread": False} if _is_sqlite else {},
    pool_pre_ping=True,
)

if _is_sqlite:

    @event.listens_for(engine, "connect")
    def _sqlite_pragmas(dbapi_conn, _):
        cur = dbapi_conn.cursor()
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
                ddl = f'ALTER TABLE "{table.name}" ADD COLUMN "{col.name}" {col.type.compile(dialect=bind.dialect)}'
                conn.execute(text(ddl))
                added.append(f"{table.name}.{col.name}")
    if added:
        log.info("added missing columns: %s", ", ".join(added))
    return added
