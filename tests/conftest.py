import os
import sys
import tempfile
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

# isolate test runs: temp sqlite DB + temp storage dir, no external keys
_tmp = tempfile.mkdtemp(prefix="wallart-test-")
os.environ["DATABASE_URL"] = f"sqlite:///{Path(_tmp) / 'test.db'}"
os.environ["STORAGE_DIR"] = str(Path(_tmp) / "storage")
os.environ.pop("ANTHROPIC_API_KEY", None)
os.environ.pop("ETSY_API_KEY", None)

from app.database import Base, engine, SessionLocal  # noqa: E402
from app import models  # noqa: E402, F401


@pytest.fixture()
def db():
    Base.metadata.drop_all(bind=engine)
    Base.metadata.create_all(bind=engine)
    session = SessionLocal()
    try:
        yield session
    finally:
        session.close()
