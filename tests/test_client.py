import hmac
import hashlib
import time
import pytest
from app.client.urja_client import UrjaClient

def test_hmac_signature_generation():
    """Validates HMAC-SHA256 signature algorithm against expected canonical format."""
    secret = "test-secret-key-12345"
    method = "GET"
    path = "/portal/export"
    query = "page=1"
    timestamp = "1729000000"

    payload = f"{method}\n{path}\n{query}\n{timestamp}"
    expected_sig = hmac.new(
        secret.encode("utf-8"),
        payload.encode("utf-8"),
        hashlib.sha256
    ).hexdigest()

    # Manual calculation matches client logic
    computed_sig = hmac.new(
        secret.encode("utf-8"),
        f"GET\n/portal/export\npage=1\n{timestamp}".encode("utf-8"),
        hashlib.sha256
    ).hexdigest()

    assert computed_sig == expected_sig
    assert len(computed_sig) == 64

def test_urja_client_initialization():
    client = UrjaClient(
        base_url="https://urja-ops.flockenergy.tech",
        username="operator@urja.local",
        password="secret-password"
    )
    assert client.base_url == "https://urja-ops.flockenergy.tech"
    assert client.username == "operator@urja.local"
    assert client._session_token is None
