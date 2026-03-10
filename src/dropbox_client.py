"""Dropbox client: authenticate and retrieve financial CSV files."""

import io
import os
from pathlib import Path
from typing import Generator

import dropbox
from dropbox.exceptions import ApiError, AuthError
from dropbox.files import FileMetadata


class DropboxClientError(Exception):
    """Raised for Dropbox-related errors."""


class DropboxClient:
    """Thin wrapper around the Dropbox SDK for reading financial files."""

    def __init__(self, access_token: str) -> None:
        if not access_token:
            raise DropboxClientError("DROPBOX_ACCESS_TOKEN is not set.")
        try:
            self._dbx = dropbox.Dropbox(access_token)
            self._dbx.users_get_current_account()
        except AuthError as exc:
            raise DropboxClientError(
                "Invalid Dropbox access token. "
                "Generate a new one at https://www.dropbox.com/developers/apps."
            ) from exc

    def list_csv_files(self, folder_path: str = "/") -> list[str]:
        """Return the Dropbox paths of all CSV files inside *folder_path*."""
        try:
            result = self._dbx.files_list_folder(folder_path, recursive=True)
            csv_paths: list[str] = []
            while True:
                for entry in result.entries:
                    if isinstance(entry, FileMetadata) and entry.name.lower().endswith(".csv"):
                        csv_paths.append(entry.path_lower)
                if not result.has_more:
                    break
                result = self._dbx.files_list_folder_continue(result.cursor)
            return csv_paths
        except ApiError as exc:
            raise DropboxClientError(f"Error listing folder '{folder_path}': {exc}") from exc

    def download_file(self, dropbox_path: str) -> bytes:
        """Download a file from Dropbox and return its raw bytes."""
        try:
            _, response = self._dbx.files_download(dropbox_path)
            return response.content
        except ApiError as exc:
            raise DropboxClientError(f"Error downloading '{dropbox_path}': {exc}") from exc

    def iter_csv_contents(
        self, folder_path: str = "/"
    ) -> Generator[tuple[str, bytes], None, None]:
        """Yield (dropbox_path, raw_bytes) for every CSV file in *folder_path*."""
        for path in self.list_csv_files(folder_path):
            yield path, self.download_file(path)


def build_client_from_env() -> DropboxClient:
    """Instantiate a :class:`DropboxClient` using environment variables."""
    token = os.environ.get("DROPBOX_ACCESS_TOKEN", "")
    return DropboxClient(token)
