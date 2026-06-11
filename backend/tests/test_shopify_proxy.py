"""Shopify App Proxy signature verification + Pro derivation."""
from __future__ import annotations

import hashlib
import hmac

from app.security.shopify_proxy import (
    _canonical_message,
    extract_customer_id,
    verify_app_proxy_signature,
)

_SECRET = "shpss_test_secret"


def _sign(params: dict[str, str]) -> str:
    msg = _canonical_message(params)
    return hmac.new(_SECRET.encode(), msg.encode(), hashlib.sha256).hexdigest()


def test_valid_signature_accepted():
    params = {
        "shop": "haircompounds.myshopify.com",
        "logged_in_customer_id": "123",
        "path_prefix": "/apps/hc-chat",
        "timestamp": "1700000000",
    }
    params["signature"] = _sign(params)
    assert verify_app_proxy_signature(params, _SECRET) is True


def test_tampered_param_rejected():
    params = {"shop": "haircompounds.myshopify.com", "logged_in_customer_id": "123"}
    params["signature"] = _sign(params)
    params["logged_in_customer_id"] = "999"  # forge a different customer
    assert verify_app_proxy_signature(params, _SECRET) is False


def test_missing_signature_rejected():
    assert verify_app_proxy_signature({"shop": "x"}, _SECRET) is False


def test_empty_secret_rejected():
    params = {"shop": "x"}
    params["signature"] = _sign(params)
    assert verify_app_proxy_signature(params, "") is False


def test_logged_in_customer_means_pro():
    assert extract_customer_id({"logged_in_customer_id": "123"}) == "123"


def test_anonymous_has_no_customer_id():
    assert extract_customer_id({"logged_in_customer_id": ""}) is None
    assert extract_customer_id({}) is None
