from concurrent.futures import ThreadPoolExecutor
from threading import Barrier
from types import SimpleNamespace

import pytest
from fastapi import HTTPException
from fastapi.security import HTTPAuthorizationCredentials

from backend.api import dependencies as auth


def credentials(token):
    return HTTPAuthorizationCredentials(scheme="Bearer", credentials=token)


def test_different_tokens_validate_in_parallel(monkeypatch):
    auth._AUTH_CACHE.clear()
    barrier = Barrier(2)
    def get_user(token):
        barrier.wait(timeout=2)
        return SimpleNamespace(user=SimpleNamespace(id=token, user_metadata={}))
    monkeypatch.setattr(auth, "get_supabase_client", lambda: SimpleNamespace(
        auth=SimpleNamespace(get_user=get_user)))
    with ThreadPoolExecutor(max_workers=2) as pool:
        futures = [pool.submit(auth.get_current_user, credentials(t)) for t in ("a", "b")]
        assert {f.result().id for f in futures} == {"a", "b"}
    assert not auth._AUTH_TOKEN_LOCKS


def test_same_token_is_validated_once_and_lock_registry_is_released(monkeypatch):
    auth._AUTH_CACHE.clear()
    calls = []
    barrier = Barrier(8)
    def get_user(token):
        calls.append(token)
        return SimpleNamespace(user=SimpleNamespace(id="user", user_metadata={}))
    monkeypatch.setattr(auth, "get_supabase_client", lambda: SimpleNamespace(
        auth=SimpleNamespace(get_user=get_user)))
    def request():
        barrier.wait(timeout=2)
        return auth.get_current_user(credentials("shared"))
    with ThreadPoolExecutor(max_workers=8) as pool:
        assert all(f.result().id == "user" for f in [pool.submit(request) for _ in range(8)])
    assert calls == ["shared"]
    assert not auth._AUTH_TOKEN_LOCKS


def test_failed_validation_releases_token_lock(monkeypatch):
    auth._AUTH_CACHE.clear()
    def broken(token):
        raise RuntimeError("auth unavailable")
    monkeypatch.setattr(auth, "get_supabase_client", lambda: SimpleNamespace(
        auth=SimpleNamespace(get_user=broken)))
    with pytest.raises(HTTPException):
        auth.get_current_user(credentials("broken"))
    assert not auth._AUTH_TOKEN_LOCKS
