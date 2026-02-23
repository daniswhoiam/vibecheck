"""Shared fixtures for Phase 8 (Tier 2 LLM aspect extraction) tests.

Provides: mock_llm_provider, low_confidence_post, high_confidence_post,
sample_aspect_data fixtures used across test modules.

Environment compatibility
-------------------------
Tests are designed to run in Docker (Python 3.12, full requirements.txt).
This conftest adds two compatibility layers:

1. sys.modules stubs: installed before test collection so the FastAPI app
   can be imported even when heavy dependencies (torch, pgvector, etc.) are
   not available locally.

2. _api_test_compat autouse fixture: sets up FastAPI dependency_overrides for
   get_session and patches select() in the entities router so that API-layer
   tests work without a live database on local Python 3.14 environments.
   In Docker (Python 3.12, real DB), this fixture is still active but the
   dependency override replaces the real DB connection with a controlled mock,
   making tests hermetic in both environments.

Mock behavior (get_session override):
   - Entity id <= 9000 → entity found (mock Claude entity returned)
   - Entity id > 9000  → entity not found (None returned → route raises 404)
   - Aspect data: always empty (all 7 VALID_ASPECTS with count=0, mean=None)
   - The entity_id is extracted from the HTTP request path parameters by the
     request-aware get_session dependency override.
"""
import sys
from unittest.mock import MagicMock, AsyncMock


# ---------------------------------------------------------------------------
# Step 1: sys.modules stubs (run at import time, before test collection)
# ---------------------------------------------------------------------------

def _install_stubs_if_needed() -> None:
    """Install sys.modules stubs for heavy/unavailable dependencies.

    Safe to call unconditionally: uses setdefault() so real modules in
    sys.modules (Docker / CI) are never replaced.
    """
    # Light optional libraries that may be missing locally
    for name in (
        "transformers", "torch", "groq", "openai",
        "asyncpraw", "numpy",
    ):
        sys.modules.setdefault(name, MagicMock())

    # tenacity: stub retry as pass-through decorator so @retry(...)(fn) == fn.
    # If tenacity is already installed (Docker env), setdefault is a no-op.
    if "tenacity" not in sys.modules:
        _tenacity_stub = MagicMock()
        # retry(stop=..., wait=..., reraise=True)(func) → func (identity)
        _tenacity_stub.retry = lambda **kwargs: (lambda fn: fn)
        _tenacity_stub.stop_after_attempt = MagicMock()
        _tenacity_stub.wait_exponential = MagicMock()
        sys.modules["tenacity"] = _tenacity_stub

    # pgvector must be stubbed before db.models (provides Vector column type)
    pgvector_stub = MagicMock()
    pgvector_sqlalchemy_stub = MagicMock()
    pgvector_sqlalchemy_stub.Vector = MagicMock(return_value=None)
    sys.modules.setdefault("pgvector", pgvector_stub)
    sys.modules.setdefault("pgvector.sqlalchemy", pgvector_sqlalchemy_stub)

    # Scheduler / pipeline submodules that import unavailable packages
    # NOTE: "pipeline" itself is NOT stubbed — the real package must be importable
    # so that pipeline.jobs.extract_aspects and pipeline.services.llm_provider work.
    # Only stub the specific submodule that imports APScheduler.
    for name in (
        "apscheduler", "apscheduler.schedulers", "apscheduler.schedulers.asyncio",
        "pipeline.scheduler",
        "scripts", "scripts.seed_entities",
    ):
        sys.modules.setdefault(name, MagicMock())

    # db.* — only stub if db.models would fail to import (Python 3.14 +
    # SQLAlchemy 2.0.36+ incompatibility with 'metadata' reserved attribute).
    # In Docker (Python 3.12, SA 2.0.35) the real modules work fine.
    if "db.models" not in sys.modules:
        needs_db_stubs = False
        try:
            import sqlalchemy as _sa  # noqa: F401
            _sa_ver = tuple(int(x) for x in _sa.__version__.split(".")[:2])
            _py_ver = sys.version_info[:2]
            # Heuristic: Python >= 3.13 with SA 2.0 → stubs needed
            if _py_ver >= (3, 13) and _sa_ver >= (2, 0):
                needs_db_stubs = True
        except ImportError:
            needs_db_stubs = True  # no sqlalchemy at all → stubs

        if needs_db_stubs:
            async def _stub_get_session():  # type: ignore[return]
                yield MagicMock()

            _db_session = MagicMock()
            _db_session.get_session = _stub_get_session
            _db_session.engine = MagicMock()
            _db_session.AsyncSessionLocal = MagicMock()

            _db_base = MagicMock()
            _db_base.Base = type("Base", (), {})  # minimal class

            sys.modules.setdefault("db", MagicMock())
            sys.modules.setdefault("db.base", _db_base)
            sys.modules.setdefault("db.session", _db_session)
            sys.modules.setdefault("db.models", MagicMock())


_install_stubs_if_needed()


# ---------------------------------------------------------------------------
# Step 2: pytest fixtures
# ---------------------------------------------------------------------------

import pytest  # noqa: E402
from unittest.mock import patch  # noqa: E402

# Entity IDs above this threshold are treated as "not found" by the mock session
_NOT_FOUND_THRESHOLD = 9000


class _ChainableQuery:
    """Chainable mock for SQLAlchemy select() expressions.

    Allows calls like select(Entity).where(Entity.id == entity_id) to succeed
    even when Entity is a MagicMock (local Python 3.14 env with db stubs).
    """

    def __init__(self, *args, **kwargs):
        pass

    def where(self, *args, **kwargs):
        return self

    def order_by(self, *args, **kwargs):
        return self

    def limit(self, *args, **kwargs):
        return self

    def desc(self, *args, **kwargs):
        return self

    def join(self, *args, **kwargs):
        return self

    def __invert__(self):
        return self


def _make_mock_select():
    """Return a callable that replaces sqlalchemy.select in the entities module."""
    def _select(*args, **kwargs):
        return _ChainableQuery()
    return _select


def _make_request_aware_get_session():
    """Build a FastAPI dependency override for get_session.

    The returned async generator accepts the HTTP Request as a dependency
    (via FastAPI's Request injection) and uses the entity_id path param
    to determine whether to return entity-found or entity-not-found.

    Mock behavior:
    - entity_id <= _NOT_FOUND_THRESHOLD (9000): entity found (mock Claude object)
    - entity_id > _NOT_FOUND_THRESHOLD: entity not found (None → route raises 404)
    - Aspect aggregation: always returns empty list
    """
    from fastapi import Request

    async def _get_session_override(request: Request):  # type: ignore[return]
        # Extract entity_id from the path params (e.g. /entities/99999/aspects)
        entity_id = int(request.path_params.get("entity_id", 1))

        # First execute: entity existence check
        entity_result = MagicMock()
        if entity_id <= _NOT_FOUND_THRESHOLD:
            mock_entity = MagicMock()
            mock_entity.id = entity_id
            mock_entity.name = "Claude"
            mock_entity.category = "model"
            entity_result.scalar_one_or_none = MagicMock(return_value=mock_entity)
        else:
            entity_result.scalar_one_or_none = MagicMock(return_value=None)

        # Second execute: aspect aggregation (empty by default)
        aspect_result = MagicMock()
        aspect_result.all = MagicMock(return_value=[])

        mock_session = MagicMock()
        mock_session.execute = AsyncMock(
            side_effect=[entity_result, aspect_result]
        )
        yield mock_session

    return _get_session_override


@pytest.fixture(autouse=True)
def _api_test_compat():
    """Ensure tests run correctly in both Docker and local Python 3.14 environments.

    What this fixture does:
    1. Patches `select` in `api.routes.entities` with a chainable mock so that
       `select(Entity).where(...)` doesn't raise ArgumentError when Entity is a
       MagicMock (local Python 3.14 env where db.models is stubbed).
    2. Sets `app.dependency_overrides[get_session]` with a request-aware override
       that uses the HTTP request's path params to simulate entity-found or
       entity-not-found behavior without a real database connection.
    3. Patches `select`, `exists`, `and_` in `pipeline.jobs.extract_aspects` so
       that SQLAlchemy query construction doesn't fail when db.models is a MagicMock
       (local Python 3.14 env where `metadata` column name is reserved by SQLAlchemy).

    This is an autouse fixture so it applies to all tests in this directory.
    Tests that don't use TestClient are unaffected at the HTTP level.
    """
    # Patch pipeline.jobs.extract_aspects SQLAlchemy query builders if available.
    # Needed in Python 3.14 local env where db.models is a MagicMock stub (because
    # SQLAlchemy 2.0.35+ reserves the 'metadata' attribute name, breaking Post model).
    # In Docker (Python 3.12), real models are used — these patches are no-ops there.
    _ea_patches = []
    try:
        import pipeline.jobs.extract_aspects as _ea

        # Column mock: supports all SQLAlchemy comparison/filter operators.
        class _MockColumn:
            """Supports all comparison operators used in SQLAlchemy WHERE clauses."""

            def __lt__(self, other): return MagicMock()
            def __gt__(self, other): return MagicMock()
            def __le__(self, other): return MagicMock()
            def __ge__(self, other): return MagicMock()
            def __eq__(self, other): return MagicMock()
            def __ne__(self, other): return MagicMock()
            def __invert__(self): return MagicMock()
            def isnot(self, other): return MagicMock()
            def in_(self, other): return MagicMock()

        class _MockModelMeta(type):
            """Metaclass that returns _MockColumn for any class-level attribute access."""
            def __getattr__(cls, name):
                return _MockColumn()

        class _MockModel(metaclass=_MockModelMeta):
            """Stub SQLAlchemy model: column attribute access returns _MockColumn.

            Instances accept any keyword arguments (simulates ORM constructor).
            """

            def __init__(self, **kwargs):
                for k, v in kwargs.items():
                    object.__setattr__(self, k, v)

        _ea_patches = [
            patch.object(_ea, "select", _make_mock_select()),
            patch.object(_ea, "exists", MagicMock(return_value=_ChainableQuery())),
            patch.object(_ea, "and_", MagicMock(return_value=MagicMock())),
            patch.object(_ea, "Post", _MockModel),
            patch.object(_ea, "PostEntityMention", _MockModel),
            patch.object(_ea, "AspectSentiment", _MockModel),
            patch.object(_ea, "Entity", _MockModel),
        ]
        for p in _ea_patches:
            p.start()
    except Exception:
        pass

    try:
        from main import app
        import api.routes.entities as _ent
    except Exception:
        yield
        for p in reversed(_ea_patches):
            try:
                p.stop()
            except Exception:
                pass
        return

    app.dependency_overrides[_ent.get_session] = _make_request_aware_get_session()

    # Patch select() in the entities module to avoid MagicMock Entity issues
    with patch.object(_ent, "select", _make_mock_select()):
        yield

    # Cleanup
    app.dependency_overrides.pop(_ent.get_session, None)
    for p in reversed(_ea_patches):
        try:
            p.stop()
        except Exception:
            pass


@pytest.fixture
def mock_db_session():
    """Mocked AsyncSession for endpoint DB access."""
    return AsyncMock()


@pytest.fixture
def mock_llm_provider():
    """AsyncMock LLM provider that returns valid aspect dict for any input.

    Returns a dict keyed by entity name, each value is a dict of aspect -> score.
    All 7 aspects are included with neutral scores (0.0) by default.
    """
    provider = AsyncMock()
    provider.extract_aspects = AsyncMock(
        return_value={
            "Claude": {
                "performance": 0.5,
                "cost": -0.3,
                "reliability": 0.4,
                "ux": 0.6,
                "speed": 0.7,
                "code_quality": 0.8,
                "context_window": 0.2,
            }
        }
    )
    return provider


@pytest.fixture
def low_confidence_post():
    """Sample post with low Tier 1 confidence — should be routed to Tier 2.

    sentiment_score=0.4 is below the 0.6 threshold. sentiment_label is set
    (post has been scored by Tier 1), so it qualifies for Tier 2 routing.
    """
    return {
        "id": 101,
        "title": "My experience with Claude vs GPT-4o",
        "body": (
            "I've been using Claude for a few weeks. The performance is decent "
            "but the cost is a bit high. Context window is impressive though."
        ),
        "sentiment_label": "Neutral",
        "sentiment_score": 0.4,
        "source": "hn",
    }


@pytest.fixture
def high_confidence_post():
    """Sample post with high Tier 1 confidence — should NOT be routed to Tier 2.

    sentiment_score=0.9 is above the 0.6 threshold, so Tier 2 is skipped.
    """
    return {
        "id": 102,
        "title": "Claude is absolutely amazing!",
        "body": "Claude is by far the best AI coding assistant I have ever used.",
        "sentiment_label": "Positive",
        "sentiment_score": 0.9,
        "source": "reddit",
    }


@pytest.fixture
def sample_aspect_data():
    """List of AspectSentiment-compatible dicts for API endpoint tests.

    Represents stored aspect sentiments for entity_id=1 (Claude) linked to
    two posts. Used to seed test DB or mock query results.
    """
    return [
        {"post_id": 101, "entity_id": 1, "aspect": "performance", "score": 0.5},
        {"post_id": 101, "entity_id": 1, "aspect": "cost", "score": -0.3},
        {"post_id": 101, "entity_id": 1, "aspect": "reliability", "score": 0.4},
        {"post_id": 101, "entity_id": 1, "aspect": "ux", "score": 0.6},
        {"post_id": 101, "entity_id": 1, "aspect": "speed", "score": 0.7},
        {"post_id": 101, "entity_id": 1, "aspect": "code_quality", "score": 0.8},
        {"post_id": 101, "entity_id": 1, "aspect": "context_window", "score": 0.2},
        {"post_id": 102, "entity_id": 1, "aspect": "performance", "score": 0.9},
        {"post_id": 102, "entity_id": 1, "aspect": "cost", "score": 0.1},
        {"post_id": 102, "entity_id": 1, "aspect": "reliability", "score": 0.8},
        {"post_id": 102, "entity_id": 1, "aspect": "ux", "score": 0.7},
        {"post_id": 102, "entity_id": 1, "aspect": "speed", "score": 0.6},
        {"post_id": 102, "entity_id": 1, "aspect": "code_quality", "score": 0.9},
        {"post_id": 102, "entity_id": 1, "aspect": "context_window", "score": 0.5},
    ]
