from __future__ import annotations

from collections.abc import Generator
from pathlib import Path

from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from app.core.settings import get_settings
from app.models.entities import Base

settings = get_settings()

if settings.database_url.startswith("sqlite"):
    database_path = settings.storage_root / "compliance.db"
    database_path.parent.mkdir(parents=True, exist_ok=True)
    resolved_database_url = f"sqlite:///{database_path.as_posix()}"
    connect_args = {"check_same_thread": False}
else:
    resolved_database_url = settings.database_url
    connect_args = {}

engine = create_engine(resolved_database_url, connect_args=connect_args, future=True)
SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False, class_=Session)


def _run_migrations() -> None:
    """Apply additive schema migrations for columns added after initial create_all."""
    with engine.connect() as conn:
        # Add content_hash to playbook_versions if it doesn't exist yet
        cols = [row[1] for row in conn.execute(__import__("sqlalchemy").text("PRAGMA table_info(playbook_versions)"))]
        if "content_hash" not in cols:
            conn.execute(__import__("sqlalchemy").text("ALTER TABLE playbook_versions ADD COLUMN content_hash VARCHAR"))
            conn.commit()


def init_db() -> None:
    Base.metadata.create_all(bind=engine)
    _run_migrations()


def get_db() -> Generator[Session, None, None]:
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
