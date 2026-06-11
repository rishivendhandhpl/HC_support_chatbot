"""Shopify App Proxy request verification.

When a storefront calls a proxied path (e.g. https://www.haircompounds.com/apps/
hc-chat/chat), Shopify forwards it to this backend and appends signed query
params, including:
  - signature: HMAC-SHA256 (hex) of all other params, keyed by the app secret
  - logged_in_customer_id: the customer id if logged in, empty otherwise

Verifying the signature proves the request genuinely came from Shopify, and the
verified logged_in_customer_id is the trustworthy source of Pro status — never
the client-supplied body.

Docs: https://shopify.dev/docs/apps/build/online-store/display-dynamic-data
"""
from __future__ import annotations

import hashlib
import hmac
import logging

logger = logging.getLogger(__name__)


def _canonical_message(params: dict[str, str | list[str]]) -> str:
    """Build the string Shopify signs: sorted `key=value` pairs, no separators.

    Array values are joined with commas. The `signature` key is excluded.
    """
    parts: list[str] = []
    for key in sorted(k for k in params if k != "signature"):
        value = params[key]
        if isinstance(value, list):
            value = ",".join(value)
        parts.append(f"{key}={value}")
    return "".join(parts)


def verify_app_proxy_signature(
    params: dict[str, str | list[str]], secret: str
) -> bool:
    """Return True if the App Proxy ``signature`` param is valid for ``secret``."""
    if not secret:
        logger.warning("App Proxy verification requested but no secret configured.")
        return False
    signature = params.get("signature")
    if not signature or isinstance(signature, list):
        return False
    message = _canonical_message(params)
    digest = hmac.new(secret.encode("utf-8"), message.encode("utf-8"), hashlib.sha256).hexdigest()
    return hmac.compare_digest(digest, signature)


def extract_customer_id(params: dict[str, str | list[str]]) -> str | None:
    """Return the verified logged-in customer id, or None if not logged in."""
    cid = params.get("logged_in_customer_id")
    if isinstance(cid, list):
        cid = cid[0] if cid else None
    return cid or None
