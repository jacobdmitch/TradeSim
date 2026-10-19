"""Test setup: point the app at a throwaway SQLite file *before* it is imported
(app.db builds its engine from DATABASE_URL at import time)."""
import os
import sys
import tempfile
from pathlib import Path

os.environ["DATABASE_URL"] = f"sqlite:///{tempfile.mkdtemp()}/test.db"
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import pytest  # noqa: E402

from app import db  # noqa: E402
from app.market import MarketStat  # noqa: E402


@pytest.fixture
def session():
    """Fresh schema and singleton rows for every test."""
    db.Base.metadata.drop_all(db.ENGINE)
    db.init_db()
    s = db.SessionLocal()
    yield s
    s.close()


def stat(base: str, last: float) -> MarketStat:
    return MarketStat(product_id=f"{base}-USD", base=base, open=last, high=last,
                      low=last, last=last, volume=1_000_000.0)
