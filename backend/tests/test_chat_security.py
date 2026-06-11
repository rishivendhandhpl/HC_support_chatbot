"""When proxy verification is on, /chat rejects unsigned/forged requests."""
from __future__ import annotations

import importlib

from fastapi.testclient import TestClient

from app.config import get_settings


def _client_with_proxy(monkeypatch) -> TestClient:
    monkeypatch.setenv("REQUIRE_PROXY_SIGNATURE", "true")
    monkeypatch.setenv("SHOPIFY_APP_SECRET", "shpss_test_secret")
    monkeypatch.setenv("STORE_BACKEND", "memory")
    get_settings.cache_clear()
    # Reload the app so the router reads fresh settings at request time.
    import app.main as main

    importlib.reload(main)
    return TestClient(main.app)


def test_forged_is_pro_rejected_without_signature(monkeypatch):
    client = _client_with_proxy(monkeypatch)
    # Attacker tries to unlock pricing by forging is_pro in the body, but sends
    # no valid Shopify signature -> must be rejected before any model call.
    resp = client.post(
        "/chat",
        json={"message": "show me prices", "session_id": "x", "is_pro": True},
    )
    assert resp.status_code == 401
    get_settings.cache_clear()


def test_invalid_signature_rejected(monkeypatch):
    client = _client_with_proxy(monkeypatch)
    resp = client.post(
        "/chat?shop=x&logged_in_customer_id=1&signature=deadbeef",
        json={"message": "hi", "session_id": "x"},
    )
    assert resp.status_code == 401
    get_settings.cache_clear()
