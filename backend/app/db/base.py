"""Shared SQLAlchemy metadata root."""

from sqlalchemy.orm import DeclarativeBase


class Base(DeclarativeBase):
    pass
