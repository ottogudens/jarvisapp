import os
from types import SimpleNamespace

os.environ.setdefault("DATABASE_URL", "postgresql://test:test@localhost:5432/jarvis_test")

from backend.auth import invalidar_sesiones


def test_invalidating_sessions_increments_the_version():
    user = SimpleNamespace(session_version=4)

    invalidar_sesiones(user)

    assert user.session_version == 5


def test_invalidating_sessions_handles_legacy_null_version():
    user = SimpleNamespace(session_version=None)

    invalidar_sesiones(user)

    assert user.session_version == 1
