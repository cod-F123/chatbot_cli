"""Database plumbing: declarative base, engine and session factory helpers."""

from sqlalchemy import create_engine
from sqlalchemy.orm import declarative_base, sessionmaker

Base = declarative_base()


def make_engine(url, **engine_options):
    """Create an engine for ``url`` (e.g. ``sqlite:///database.db``)."""
    return create_engine(url, **engine_options)


def make_session_factory(engine):
    """Return a session factory bound to ``engine``.

    ``expire_on_commit=False`` keeps loaded attributes readable after the
    session is closed, which the repository relies on.
    """
    return sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)


def create_tables(engine):
    """Create all tables that are registered on :data:`Base`."""
    # Imported here so the models register themselves on Base without a
    # circular import at module load time.
    from db import models  # noqa: F401

    Base.metadata.create_all(engine)
