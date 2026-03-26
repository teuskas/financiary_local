"""Dropbox API helpers for the Android/mobile app."""

from __future__ import annotations

import json
from dataclasses import dataclass

import requests

TOKEN_URL = "https://api.dropboxapi.com/oauth2/token"
DOWNLOAD_URL = "https://content.dropboxapi.com/2/files/download"


@dataclass
class DropboxCreds:
    app_key: str
    app_secret: str
    refresh_token: str


class DropboxApiError(RuntimeError):
    """Raised when Dropbox auth or download fails."""


class DropboxApiClient:
    def __init__(self, creds: DropboxCreds, timeout_seconds: int = 30):
        self.creds = creds
        self.timeout_seconds = timeout_seconds

    def _access_token(self) -> str:
        response = requests.post(
            TOKEN_URL,
            data={
                "grant_type": "refresh_token",
                "refresh_token": self.creds.refresh_token,
            },
            auth=(self.creds.app_key, self.creds.app_secret),
            timeout=self.timeout_seconds,
        )

        if response.status_code != 200:
            raise DropboxApiError(
                f"Dropbox token error {response.status_code}: {response.text[:300]}"
            )

        payload = response.json()
        token = payload.get("access_token")
        if not token:
            raise DropboxApiError("Dropbox token response senza access_token")
        return token

    def download_file(self, dropbox_path: str) -> bytes:
        token = self._access_token()

        response = requests.post(
            DOWNLOAD_URL,
            headers={
                "Authorization": f"Bearer {token}",
                "Dropbox-API-Arg": json.dumps({"path": dropbox_path}),
            },
            timeout=self.timeout_seconds,
        )

        if response.status_code != 200:
            raise DropboxApiError(
                f"Dropbox download error {response.status_code}: {response.text[:300]}"
            )

        return response.content

