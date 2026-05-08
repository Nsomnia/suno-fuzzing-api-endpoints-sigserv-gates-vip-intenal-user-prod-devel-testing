import requests
import time
import jwt  # pip install pyjwt
import re
from urllib.parse import urljoin
from threading import Lock

class SunoAuth:
    def __init__(self, base_url="https://suno.com", bearer=None, cookies=None, refresh_token=None):
        self.base_url = base_url
        self.bearer = bearer
        self.cookies = cookies or {}
        self.refresh_token = refresh_token  # User will provide
        self.session = requests.Session()
        self.lock = Lock()
        self.last_refresh = 0
        self.refresh_interval = 50  # seconds, conservative before expiry

        if self.cookies:
            self.session.cookies.update(self.cookies)

    def get_headers(self):
        with self.lock:
            if self._needs_refresh():
                self._refresh_jwt()
            headers = {
                "Authorization": f"Bearer {self.bearer}",
                "Content-Type": "application/json",
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
            }
            return headers

    def _needs_refresh(self):
        if not self.bearer:
            return True
        try:
            decoded = jwt.decode(self.bearer, options={"verify_signature": False})
            exp = decoded.get('exp', 0)
            return time.time() > exp - 60  # refresh 1min early
        except:
            return True

    def _refresh_jwt(self):
        print("[Auth] Refreshing JWT...")
        # Clerk often uses /v1/client/sessions or similar; user can inspect dev tools for exact
        # Common patterns from Clerk + Suno reverse engineering
        refresh_endpoints = [
            "/api/session/",  # from your C++ code
            "/v1/client/sessions/{session_id}/tokens",
            "/api/auth/refresh",
        ]

        for ep in refresh_endpoints:
            try:
                url = urljoin(self.base_url, ep)
                resp = self.session.post(url, json={"refresh_token": self.refresh_token} if self.refresh_token else {},
                                       headers=self.get_headers())  # bootstrap if needed
                if resp.status_code in (200, 201):
                    data = resp.json()
                    # Adapt based on actual response structure from dev console
                    if "token" in data:
                        self.bearer = data["token"]
                    elif "access_token" in data:
                        self.bearer = data["access_token"]
                    self.last_refresh = time.time()
                    print("[Auth] Refresh successful")
                    return
            except:
                continue
        print("[Auth] Refresh failed - check refresh_token / endpoints")

    def request(self, method, url, **kwargs):
        headers = self.get_headers()
        if 'headers' in kwargs:
            headers.update(kwargs.pop('headers'))
        return self.session.request(method, url, headers=headers, **kwargs)