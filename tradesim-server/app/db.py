"""Database layer (SQLAlchemy). Uses Postgres via DATABASE_URL on Render,
falling back to a local SQLite file for development."""
from __future__ import annotations

import os
from typing import Optional
from datetime import datetime, timezone

from sqlalchemy import (
    Boolean, DateTime, Float, Integer, String, Text, create_engine,
)
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, sessionmaker

from . import config


def _database_url() -> str:
    url = os.environ.get("DATABASE_URL", "").strip()
    if not url:
        return "sqlite:///tradesim.db"
    # Render/Heroku style "postgres://" -> SQLAlchemy needs "postgresql://".
    if url.startswith("postgres://"):
        url = url.replace("postgres://", "postgresql://", 1)
    return url


ENGINE = create_engine(_database_url(), pool_pre_ping=True, future=True)
SessionLocal = sessionmaker(bind=ENGINE, expire_on_commit=False, future=True)


class Base(DeclarativeBase):
    pass


def _now() -> datetime:
    return datetime.now(timezone.utc)


class Settings(Base):
    """Singleton control row (id=1)."""
    __tablename__ = "settings"
    id: Mapped[int] = mapped_column(Integer, primary_key=True, default=1)
    enabled: Mapped[bool] = mapped_column(Boolean, default=False)      # master kill switch
    dry_run: Mapped[bool] = mapped_column(Boolean, default=True)       # paper vs live
    seeded: Mapped[bool] = mapped_column(Boolean, default=False)
    starting_balance: Mapped[float] = mapped_column(Float, default=23.17)
    balance_floor_usd: Mapped[float] = mapped_column(Float, default=0.0)
    audit_enabled: Mapped[bool] = mapped_column(Boolean, default=False)  # Claude pre-trade audit
    interval_minutes: Mapped[int] = mapped_column(Integer, default=15)   # effective cadence
    prev_rec_sig: Mapped[Optional[str]] = mapped_column(String(96), nullable=True)  # 2-scan confirm
    min_hold_hours: Mapped[int] = mapped_column(Integer, default=6)      # min hold before rotating
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now, onupdate=_now)


class Portfolio(Base):
    """Singleton portfolio row (id=1): cash plus at most one coin position."""
    __tablename__ = "portfolio"
    id: Mapped[int] = mapped_column(Integer, primary_key=True, default=1)
    cash: Mapped[float] = mapped_column(Float, default=0.0)
    pos_base: Mapped[Optional[str]] = mapped_column(String(32), nullable=True)
    pos_product_id: Mapped[Optional[str]] = mapped_column(String(48), nullable=True)
    pos_quantity: Mapped[float] = mapped_column(Float, default=0.0)
    pos_cost_basis_usd: Mapped[float] = mapped_column(Float, default=0.0)
    pos_mark_price: Mapped[float] = mapped_column(Float, default=0.0)
    pos_opened_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now, onupdate=_now)

    @property
    def has_position(self) -> bool:
        return bool(self.pos_base) and self.pos_quantity > 0

    @property
    def position_value(self) -> float:
        return self.pos_quantity * self.pos_mark_price if self.has_position else 0.0

    @property
    def total_value(self) -> float:
        return self.cash + self.position_value


class Trade(Base):
    __tablename__ = "trades"
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    ts: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)
    action: Mapped[str] = mapped_column(String(8))     # BUY | SELL
    base: Mapped[str] = mapped_column(String(32))
    price: Mapped[float] = mapped_column(Float)
    quantity: Mapped[float] = mapped_column(Float)
    cash_flow: Mapped[float] = mapped_column(Float)    # negative on buy, positive on sell
    realized_pnl: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    fee_usd: Mapped[float] = mapped_column(Float, default=0.0)   # trading cost on this leg
    mode: Mapped[str] = mapped_column(String(8), default="DRY")  # DRY | LIVE
    order_id: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)


class Recommendation(Base):
    __tablename__ = "recommendations"
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    ts: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)
    action: Mapped[str] = mapped_column(String(8))
    from_base: Mapped[Optional[str]] = mapped_column(String(32), nullable=True)
    to_base: Mapped[Optional[str]] = mapped_column(String(32), nullable=True)
    rationale: Mapped[str] = mapped_column(Text)
    edge_pct: Mapped[float] = mapped_column(Float)


class ScanLog(Base):
    __tablename__ = "scans"
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    ts: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)
    candidates: Mapped[int] = mapped_column(Integer, default=0)
    note: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    error: Mapped[Optional[str]] = mapped_column(Text, nullable=True)


class EquitySnapshot(Base):
    """Total portfolio value captured each cycle, for the equity curve chart."""
    __tablename__ = "equity"
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    ts: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)
    total_value: Mapped[float] = mapped_column(Float)
    cash: Mapped[float] = mapped_column(Float, default=0.0)
    position_value: Mapped[float] = mapped_column(Float, default=0.0)
    holding: Mapped[Optional[str]] = mapped_column(String(32), nullable=True)


class AuditLog(Base):
    """Record of each Claude pre-trade audit (approve or veto)."""
    __tablename__ = "audits"
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    ts: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)
    action: Mapped[str] = mapped_column(String(8))          # the pending action audited
    to_base: Mapped[Optional[str]] = mapped_column(String(32), nullable=True)
    verdict: Mapped[str] = mapped_column(String(12))        # APPROVE | VETO
    reason: Mapped[str] = mapped_column(Text)
    model: Mapped[Optional[str]] = mapped_column(String(48), nullable=True)


def _run_migrations() -> None:
    """Idempotently add columns introduced after a DB was first created.
    create_all() makes new tables but never alters existing ones."""
    from sqlalchemy import inspect, text
    insp = inspect(ENGINE)
    adds = {
        "settings": [
            ("audit_enabled", "BOOLEAN DEFAULT FALSE"),
            ("interval_minutes", "INTEGER DEFAULT 15"),
            ("prev_rec_sig", "VARCHAR(96)"),
            ("min_hold_hours", "INTEGER DEFAULT 6"),
        ],
        "portfolio": [
            ("pos_opened_at", "TIMESTAMP"),
        ],
        "trades": [
            ("fee_usd", "FLOAT DEFAULT 0"),
        ],
    }
    for table, cols_to_add in adds.items():
        try:
            existing = {c["name"] for c in insp.get_columns(table)}
        except Exception:
            continue  # table not created yet; create_all handles it
        for name, ddl in cols_to_add:
            if name not in existing:
                with ENGINE.begin() as conn:
                    conn.execute(text(f"ALTER TABLE {table} ADD COLUMN {name} {ddl}"))


def init_db() -> None:
    """Create tables and seed the singleton control rows if missing."""
    Base.metadata.create_all(ENGINE)
    _run_migrations()
    with SessionLocal() as s:
        if s.get(Settings, 1) is None:
            s.add(Settings(
                id=1,
                enabled=config.TRADING_ENABLED_DEFAULT,
                dry_run=config.DRY_RUN_DEFAULT,
                seeded=False,
                starting_balance=config.STARTING_BALANCE_DEFAULT,
                balance_floor_usd=config.BALANCE_FLOOR_DEFAULT,
                interval_minutes=config.INTERVAL_MINUTES_DEFAULT,
                min_hold_hours=config.MIN_HOLD_HOURS_DEFAULT,
            ))
        if s.get(Portfolio, 1) is None:
            s.add(Portfolio(id=1, cash=config.STARTING_BALANCE_DEFAULT))
        s.commit()


def get_settings(session) -> Settings:
    return session.get(Settings, 1)


def get_portfolio(session) -> Portfolio:
    return session.get(Portfolio, 1)
