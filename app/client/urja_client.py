import asyncio
import hashlib
import hmac
import logging
import time
from typing import Any, Dict, List, Optional
import httpx

from app.config import settings

logger = logging.getLogger("urja.client")

class UrjaClientError(Exception):
    """Base exception for Urja portal communication errors."""
    pass

class UrjaAuthError(UrjaClientError):
    """Authentication or credential failure."""
    pass

class UrjaNotFoundError(UrjaClientError):
    """Resource not found on Urja portal."""
    pass

class UrjaClient:
    """
    Robust reverse-engineered client for the Urja Meter Ops portal.
    Handles session lifecycle, CSRF headers, SvelteKit cookies, HMAC export signing,
    and automatic transparent re-authentication.
    """

    def __init__(
        self,
        base_url: str = settings.urja_portal_url,
        username: str = settings.urja_username,
        password: str = settings.urja_password,
        timeout: float = 15.0
    ):
        self.base_url = base_url.rstrip("/")
        self.username = username
        self.password = password
        self.timeout = timeout

        self._session_token: Optional[str] = None
        self._token_expires_at: float = 0
        self._signing_secret: Optional[str] = None
        self._lock = asyncio.Lock()
        self._client: Optional[httpx.AsyncClient] = None

    async def _get_client(self) -> httpx.AsyncClient:
        if self._client is None or self._client.is_closed:
            self._client = httpx.AsyncClient(
                timeout=self.timeout,
                headers={
                    "User-Agent": "Urja-Gateway-Service/1.0 (+https://flockenergy.tech)",
                    "Origin": self.base_url,
                    "Referer": f"{self.base_url}/meters"
                }
            )
        return self._client

    async def close(self):
        if self._client and not self._client.is_closed:
            await self._client.aclose()

    async def login(self, force: bool = False) -> str:
        """
        Authenticates against the Urja portal and stores the session cookie.
        Thread/async-safe via asyncio.Lock.
        """
        async with self._lock:
            now = time.time()
            # If token is still fresh and not forcing, return it
            if not force and self._session_token and now < (self._token_expires_at - settings.session_refresh_buffer_seconds):
                return self._session_token

            client = await self._get_client()
            login_url = f"{self.base_url}/login"
            payload = {
                "email": self.username,
                "password": self.password
            }

            try:
                # SvelteKit checks Origin header for CSRF protection
                headers = {
                    "Origin": self.base_url,
                    "Referer": login_url,
                    "Content-Type": "application/x-www-form-urlencoded"
                }
                response = await client.post(login_url, data=payload, headers=headers, follow_redirects=False)
            except Exception as e:
                logger.error(f"Failed to connect to Urja portal login: {e}")
                raise UrjaClientError(f"Connection failed: {e}") from e

            if response.status_code not in (200, 302, 303):
                logger.error(f"Login failed with status {response.status_code}: {response.text}")
                raise UrjaAuthError(f"Urja portal login rejected ({response.status_code}): {response.text}")

            token = response.cookies.get("__Secure-better-auth.session_token")
            if not token:
                # Check headers directly if cookie jar hasn't parsed it
                set_cookie = response.headers.get("set-cookie", "")
                if "__Secure-better-auth.session_token=" in set_cookie:
                    parts = set_cookie.split("__Secure-better-auth.session_token=")[1].split(";")
                    token = parts[0].strip()

            if not token:
                raise UrjaAuthError(f"No session cookie returned after login: {response.headers}")

            self._session_token = token
            # Portal session cookie has Max-Age=3600 (1 hour)
            self._token_expires_at = time.time() + 3600
            logger.info("Successfully authenticated with Urja Meter Ops portal.")

            # Invalidate cached signing secret on fresh login
            self._signing_secret = None
            return token

    async def _request(
        self,
        method: str,
        path: str,
        headers: Optional[Dict[str, str]] = None,
        params: Optional[Dict[str, Any]] = None,
        data: Optional[Any] = None,
        retry_on_401: bool = True
    ) -> httpx.Response:
        """
        Executes an HTTP request to the Urja portal with automatic session injection
        and transparent 401 re-authentication retry.
        """
        if not self._session_token or time.time() >= (self._token_expires_at - settings.session_refresh_buffer_seconds):
            await self.login()

        client = await self._get_client()
        req_headers = headers.copy() if headers else {}
        req_headers["Cookie"] = f"__Secure-better-auth.session_token={self._session_token}"
        req_headers["Origin"] = self.base_url

        url = f"{self.base_url}{path}"

        try:
            resp = await client.request(method, url, headers=req_headers, params=params, data=data)
        except Exception as e:
            logger.error(f"Request error calling {path}: {e}")
            raise UrjaClientError(f"Network error calling {path}: {e}") from e

        # Handle session expiration
        if resp.status_code == 401 and retry_on_401:
            logger.warning(f"Received 401 Unauthorized for {path}. Re-authenticating and retrying...")
            await self.login(force=True)
            return await self._request(method, path, headers=headers, params=params, data=data, retry_on_401=False)

        if resp.status_code == 404:
            raise UrjaNotFoundError(f"Resource {path} not found on portal.")

        if resp.status_code >= 400:
            raise UrjaClientError(f"Portal returned error {resp.status_code} for {path}: {resp.text}")

        return resp

    async def search_meters(self, query: str = "", page: int = 1) -> Dict[str, Any]:
        """Queries `/portal/meters/search?q={query}&page={page}`."""
        resp = await self._request("GET", "/portal/meters/search", params={"q": query, "page": page})
        return resp.json()

    async def get_distribution_transformers(self, page: int = 1) -> Dict[str, Any]:
        """Queries `/portal/dts?page={page}`."""
        resp = await self._request("GET", "/portal/dts", params={"page": page})
        return resp.json()

    async def get_all_distribution_transformers(self) -> List[Dict[str, Any]]:
        """Paginates through `/portal/dts` to retrieve all transformers."""
        all_dts = []
        page = 1
        while True:
            res = await self.get_distribution_transformers(page=page)
            dts = res.get("data", [])
            if not dts:
                break
            all_dts.extend(dts)
            total = res.get("total", 0)
            if len(all_dts) >= total:
                break
            page += 1
        return all_dts

    async def get_signing_secret(self) -> str:
        """Fetches the HMAC signing secret from `/portal/keys`."""
        if self._signing_secret:
            return self._signing_secret

        resp = await self._request("GET", "/portal/keys")
        data = resp.json().get("data", {})
        secret = data.get("signingSecret")
        if not secret:
            raise UrjaClientError("Failed to extract signingSecret from /portal/keys response")
        self._signing_secret = secret
        return secret

    async def get_full_export(self) -> List[Dict[str, Any]]:
        """
        Retrieves the complete dataset via HMAC-signed `/portal/export?page=1`.
        Signs: "{method}\n{path}\n{query}\n{timestamp}" with sha256.
        """
        secret = await self.get_signing_secret()
        method = "GET"
        path = "/portal/export"
        query = "page=1"
        timestamp = str(int(time.time()))

        payload = f"{method}\n{path}\n{query}\n{timestamp}"
        signature = hmac.new(
            secret.encode("utf-8"),
            payload.encode("utf-8"),
            hashlib.sha256
        ).hexdigest()

        headers = {
            "x-timestamp": timestamp,
            "x-signature": signature
        }

        resp = await self._request("GET", f"{path}?{query}", headers=headers)
        res_data = resp.json()
        return res_data.get("data", [])

    async def get_meter_geo(self, meter_id: str) -> Optional[Dict[str, Any]]:
        """Fetches geolocation for a specific meter from `/portal/meters/{meter_id}/geo`."""
        try:
            resp = await self._request("GET", f"/portal/meters/{meter_id}/geo")
            return resp.json().get("data")
        except UrjaNotFoundError:
            return None

    async def get_meter_energy(self, meter_id: str) -> List[Dict[str, Any]]:
        """Fetches recent energy consumption readings from `/portal/meters/{meter_id}/energy`."""
        try:
            resp = await self._request("GET", f"/portal/meters/{meter_id}/energy")
            return resp.json().get("data", [])
        except UrjaNotFoundError:
            return []

    async def get_meter_route_data(self, meter_id: str) -> Optional[Dict[str, Any]]:
        """Fetches SvelteKit SSR serialized data from `/meters/{meter_id}/__data.json`."""
        try:
            resp = await self._request("GET", f"/meters/{meter_id}/__data.json")
            return resp.json()
        except UrjaNotFoundError:
            return None

# Global singleton client
urja_client = UrjaClient()
