import base64
import hashlib
import hmac
import secrets
import time
from typing import Any, Dict, Optional
from urllib.parse import quote

import httpx

from app.core.config import settings


def _oauth_percent_encode(value: Any) -> str:
    return quote(str(value), safe="~")


class FatSecretService:
    _token_cache: Dict[str, Any] = {"access_token": None, "expires_at": 0.0}

    @staticmethod
    def enabled() -> bool:
        return FatSecretService.oauth1_enabled() or FatSecretService.oauth2_enabled()

    @staticmethod
    def oauth1_enabled() -> bool:
        return bool(settings.FATSECRET_CONSUMER_KEY and settings.FATSECRET_CONSUMER_SECRET)

    @staticmethod
    def oauth2_enabled() -> bool:
        return bool(settings.FATSECRET_CLIENT_ID and settings.FATSECRET_CLIENT_SECRET)

    @staticmethod
    def auth_mode() -> str:
        mode = (settings.FATSECRET_AUTH_MODE or "auto").strip().lower()
        if mode in {"oauth1", "oauth2", "auto"}:
            return mode
        return "auto"

    @classmethod
    def preferred_auth_mode(cls) -> str:
        mode = cls.auth_mode()
        if mode == "oauth1" and cls.oauth1_enabled():
            return "oauth1"
        if mode == "oauth2" and cls.oauth2_enabled():
            return "oauth2"
        if cls.oauth1_enabled():
            return "oauth1"
        if cls.oauth2_enabled():
            return "oauth2"
        raise RuntimeError("FatSecret credentials are not configured")

    @classmethod
    async def get_access_token(cls) -> str:
        cached_token = cls._token_cache.get("access_token")
        expires_at = float(cls._token_cache.get("expires_at") or 0.0)
        now = time.time()
        if cached_token and expires_at - now > 30:
            return str(cached_token)

        if not cls.oauth2_enabled():
            raise RuntimeError("FatSecret OAuth 2.0 credentials are not configured")

        async with httpx.AsyncClient(timeout=15.0) as client:
            response = await client.post(
                settings.FATSECRET_TOKEN_URL,
                data={"grant_type": "client_credentials", "scope": "basic"},
                auth=(settings.FATSECRET_CLIENT_ID, settings.FATSECRET_CLIENT_SECRET),
                headers={"Content-Type": "application/x-www-form-urlencoded"},
            )
            response.raise_for_status()
            payload = response.json()

        access_token = payload.get("access_token")
        expires_in = int(payload.get("expires_in") or 3600)
        if not access_token:
            raise RuntimeError("FatSecret token response did not contain access_token")

        cls._token_cache = {
            "access_token": access_token,
            "expires_at": now + expires_in,
        }
        return str(access_token)

    @classmethod
    def _oauth1_signed_params(
        cls,
        params: Dict[str, Any],
        *,
        timestamp: Optional[int] = None,
        nonce: Optional[str] = None,
    ) -> Dict[str, Any]:
        if not cls.oauth1_enabled():
            raise RuntimeError("FatSecret OAuth 1.0 credentials are not configured")

        oauth_params: Dict[str, Any] = {
            "oauth_consumer_key": settings.FATSECRET_CONSUMER_KEY,
            "oauth_signature_method": "HMAC-SHA1",
            "oauth_timestamp": str(timestamp or int(time.time())),
            "oauth_nonce": nonce or secrets.token_hex(8),
            "oauth_version": "1.0",
        }
        signing_params = {**params, **oauth_params}
        normalized = "&".join(
            f"{_oauth_percent_encode(key)}={_oauth_percent_encode(signing_params[key])}"
            for key in sorted(signing_params)
        )
        base_string = "&".join(
            [
                "GET",
                _oauth_percent_encode(settings.FATSECRET_API_BASE_URL),
                _oauth_percent_encode(normalized),
            ]
        )
        signing_key = f"{_oauth_percent_encode(settings.FATSECRET_CONSUMER_SECRET)}&"
        signature = base64.b64encode(
            hmac.new(signing_key.encode("utf-8"), base_string.encode("utf-8"), hashlib.sha1).digest()
        ).decode("utf-8")
        return {**signing_params, "oauth_signature": signature}

    @classmethod
    async def _request(cls, params: Dict[str, Any]) -> Dict[str, Any]:
        mode = cls.preferred_auth_mode()
        if mode == "oauth1":
            signed_params = cls._oauth1_signed_params(params)
            async with httpx.AsyncClient(timeout=20.0) as client:
                response = await client.get(settings.FATSECRET_API_BASE_URL, params=signed_params)
                response.raise_for_status()
                return response.json()

        token = await cls.get_access_token()
        async with httpx.AsyncClient(timeout=20.0) as client:
            response = await client.get(
                settings.FATSECRET_API_BASE_URL,
                params=params,
                headers={"Authorization": f"Bearer {token}"},
            )
            response.raise_for_status()
            return response.json()

    @classmethod
    async def foods_search(
        cls,
        query: str,
        *,
        page_number: int = 0,
        max_results: int = 10,
        region: str = "US",
        language: str = "en",
    ) -> Dict[str, Any]:
        params = {
            "method": "foods.search",
            "search_expression": query,
            "page_number": page_number,
            "max_results": max_results,
            "format": "json",
        }
        if region:
            params["region"] = region
        if language:
            params["language"] = language
        return await cls._request(params)

    @classmethod
    async def food_get(cls, food_id: str, *, language: str = "en") -> Dict[str, Any]:
        params = {
            "method": "food.get",
            "food_id": food_id,
            "format": "json",
        }
        if language:
            params["language"] = language
        return await cls._request(params)

    @staticmethod
    def first_food_candidate(search_payload: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        legacy_foods = search_payload.get("foods", {}).get("food", [])
        if isinstance(legacy_foods, dict):
            return legacy_foods
        if isinstance(legacy_foods, list) and legacy_foods:
            return legacy_foods[0]

        foods = search_payload.get("foods_search", {}).get("results", {}).get("food", [])
        if isinstance(foods, dict):
            return foods
        if isinstance(foods, list) and foods:
            return foods[0]
        return None
