import pytest

from app.services.fatsecret import FatSecretService


pytestmark = pytest.mark.anyio


async def test_oauth1_signature_params_include_required_fields(monkeypatch):
    monkeypatch.setattr("app.services.fatsecret.settings.FATSECRET_CONSUMER_KEY", "demo-key")
    monkeypatch.setattr("app.services.fatsecret.settings.FATSECRET_CONSUMER_SECRET", "demo-secret")
    monkeypatch.setattr("app.services.fatsecret.settings.FATSECRET_API_BASE_URL", "https://platform.fatsecret.com/rest/server.api")

    signed = FatSecretService._oauth1_signed_params(
        {"method": "foods.search.v3", "search_expression": "chicken breast", "format": "json"},
        timestamp=1234567890,
        nonce="abc123",
    )

    assert signed["oauth_consumer_key"] == "demo-key"
    assert signed["oauth_signature_method"] == "HMAC-SHA1"
    assert signed["oauth_timestamp"] == "1234567890"
    assert signed["oauth_nonce"] == "abc123"
    assert signed["oauth_version"] == "1.0"
    assert isinstance(signed["oauth_signature"], str)
    assert len(signed["oauth_signature"]) > 10


async def test_preferred_auth_mode_prefers_oauth1_when_available(monkeypatch):
    monkeypatch.setattr("app.services.fatsecret.settings.FATSECRET_AUTH_MODE", "auto")
    monkeypatch.setattr("app.services.fatsecret.settings.FATSECRET_CONSUMER_KEY", "demo-key")
    monkeypatch.setattr("app.services.fatsecret.settings.FATSECRET_CONSUMER_SECRET", "demo-secret")
    monkeypatch.setattr("app.services.fatsecret.settings.FATSECRET_CLIENT_ID", "client-id")
    monkeypatch.setattr("app.services.fatsecret.settings.FATSECRET_CLIENT_SECRET", "client-secret")

    assert FatSecretService.preferred_auth_mode() == "oauth1"


async def test_preferred_auth_mode_honors_explicit_oauth2(monkeypatch):
    monkeypatch.setattr("app.services.fatsecret.settings.FATSECRET_AUTH_MODE", "oauth2")
    monkeypatch.setattr("app.services.fatsecret.settings.FATSECRET_CONSUMER_KEY", "demo-key")
    monkeypatch.setattr("app.services.fatsecret.settings.FATSECRET_CONSUMER_SECRET", "demo-secret")
    monkeypatch.setattr("app.services.fatsecret.settings.FATSECRET_CLIENT_ID", "client-id")
    monkeypatch.setattr("app.services.fatsecret.settings.FATSECRET_CLIENT_SECRET", "client-secret")

    assert FatSecretService.preferred_auth_mode() == "oauth2"


async def test_first_food_candidate_supports_legacy_v1_shape():
    payload = {
        "foods": {
            "food": {
                "food_id": "1641",
                "food_name": "Chicken Breast",
            }
        }
    }

    candidate = FatSecretService.first_food_candidate(payload)

    assert candidate is not None
    assert candidate["food_id"] == "1641"
