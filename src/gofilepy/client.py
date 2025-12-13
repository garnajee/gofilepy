"""HTTP client for interacting with the Gofile API."""

from __future__ import annotations

import logging
import os
from dataclasses import dataclass
from typing import Any, BinaryIO, Callable, Dict, List, Optional, Union

import httpx

from .utils import ProgressFileReader

logger = logging.getLogger(__name__)


class GofileError(RuntimeError):
    """Base exception for all Gofile client errors."""

    def __init__(self, message: str, *, context: Optional[Dict[str, Any]] = None):
        super().__init__(message)
        self.context = context or {}


class GofileAPIError(GofileError):
    """Raised when the Gofile API reports an error."""


class GofileNetworkError(GofileError):
    """Raised when the HTTP request fails before reaching the API."""


class GofileUploadError(GofileError):
    """Raised when the upload flow cannot complete."""


@dataclass(slots=True)
class GofileFile:
    """Represents a file returned by the Gofile API."""

    name: str
    page_link: str
    file_id: str
    parent_folder: str
    raw: Dict[str, object]

    @classmethod
    def from_data(cls, data: Dict[str, object]) -> "GofileFile":
        """Create an instance from the API response payload."""

        return cls(
            name=str(data.get("fileName", "")),
            page_link=str(data.get("downloadPage", "")),
            file_id=str(data.get("fileId", "")),
            parent_folder=str(data.get("parentFolder", "")),
            raw=data,
        )

    def to_dict(self) -> Dict[str, object]:
        """Return the original API payload as a new dict."""

        return dict(self.raw)


class GofileClient:
    """Thin wrapper around Gofile's REST endpoints."""

    API_ROOT = "https://api.gofile.io"
    UPLOAD_SERVER_URL = "https://upload.gofile.io"

    def __init__(self, token: Optional[str] = None):
        """Instantiate the client with an optional authentication token."""

        self.token = token
        self.client = httpx.Client(timeout=30.0)

        if self.token:
            logger.debug("Initialized with token: %s***", self.token[:4])
            self.client.headers.update({"Authorization": f"Bearer {self.token}"})

    def _handle_response(self, response: httpx.Response) -> Dict[str, object]:
        """Validate HTTP responses and normalize API errors."""

        logger.debug("Response status: %s", response.status_code)

        try:
            data = response.json()
            logger.debug("Response body: %s", data)
        except ValueError as exc:  # httpx raises ValueError for invalid JSON
            error_text = response.text.strip()
            logger.debug("Failed to parse JSON: %s", error_text)
            response.raise_for_status()
            raise GofileAPIError("Invalid JSON returned by Gofile API") from exc

        if data.get("status") != "ok":
            logger.error("API error payload: %s", data)
            raise GofileAPIError(
                f"Gofile API Error: {data.get('status')} - {data.get('data')}"
            )

        payload = data.get("data")
        if not isinstance(payload, dict):
            raise GofileAPIError("Gofile API returned unexpected payload structure")
        return payload

    def _request(
        self, method: str, url: str, *, context: Optional[Dict[str, Any]] = None, **kwargs: Any
    ) -> Dict[str, object]:
        """Execute an HTTP request and normalize errors."""

        safe_context = context or {}
        try:
            logger.debug("HTTP %s %s | payload=%s", method, url, safe_context)
            response = self.client.request(method, url, **kwargs)
        except httpx.HTTPError as exc:
            logger.error("HTTP %s %s failed: %s", method, url, exc)
            raise GofileNetworkError(
                f"Failed HTTP request to {url}", context={"method": method, **safe_context}
            ) from exc

        return self._handle_response(response)

    @staticmethod
    def _sanitize_metadata(metadata: Dict[str, str]) -> Dict[str, str]:
        """Return a copy of request metadata with sensitive values redacted."""

        redacted = dict(metadata)
        if "token" in redacted:
            redacted["token"] = "***REDACTED***"
        return redacted

    def get_server(self) -> str:
        """Return the upload server, which leverages geo-aware routing."""

        return self.UPLOAD_SERVER_URL

    def create_folder(self, parent_folder_id: str, folder_name: str) -> Dict[str, object]:
        """Create a folder under the provided parent folder."""

        logger.debug("Creating folder '%s' in '%s'", folder_name, parent_folder_id)
        url = f"{self.API_ROOT}/contents/createFolder"
        payload = {
            "parentFolderId": parent_folder_id,
            "folderName": folder_name,
        }
        return self._request("POST", url, json=payload, context=payload)

    def delete_content(self, content_ids: List[str]) -> Dict[str, object]:
        """Delete one or more items by their content IDs."""

        logger.debug("Deleting content IDs: %s", content_ids)
        url = f"{self.API_ROOT}/contents"
        payload = {"contentsId": ",".join(content_ids)}
        return self._request("DELETE", url, json=payload, context=payload)

    def upload(
        self,
        file: Union[str, BinaryIO],
        folder_id: Optional[str] = None,
        callback: Optional[Callable[[int], None]] = None,
    ) -> GofileFile:
        """Upload a file object or file path to Gofile."""

        server_url = f"{self.get_server()}/uploadfile"
        data: Dict[str, str] = {}
        if self.token:
            data["token"] = self.token
        if folder_id:
            data["folderId"] = folder_id

        logger.debug("Upload metadata: %s", self._sanitize_metadata(data))

        progress_callback = callback or (lambda _chunk: None)

        if isinstance(file, str):
            file_name = os.path.basename(file)
            logger.info("Starting upload: %s -> %s", file_name, server_url)
            with open(file, "rb") as file_handle:
                wrapped_file = ProgressFileReader(file_handle, progress_callback)
                response = self._post_upload(
                    server_url,
                    data=data,
                    files={"file": (file_name, wrapped_file)},
                )
        else:
            file_name = getattr(file, "name", "uploaded_file")
            if hasattr(file_name, "__fspath__"):
                file_name = os.path.basename(file_name)  # type: ignore[arg-type]
            elif "/" in str(file_name) or "\\" in str(file_name):
                file_name = os.path.basename(str(file_name))

            logger.info("Starting upload: %s -> %s", file_name, server_url)
            files = {"file": (file_name, file)}
            response = self._post_upload(
                server_url,
                data=data,
                files=files,
            )

        response_data = self._handle_response(response)
        logger.info("Upload finished: %s", file_name)
        return GofileFile.from_data(response_data)

    def _post_upload(
        self,
        url: str,
        *,
        data: Dict[str, str],
        files: Dict[str, Any],
    ) -> httpx.Response:
        """Issue the actual upload request with improved error context."""

        try:
            return self.client.post(url, data=data, files=files, timeout=None)
        except httpx.TimeoutException as exc:
            logger.error("Upload timed out at %s", url)
            raise GofileUploadError("Upload timed out", context={"url": url}) from exc
        except httpx.HTTPError as exc:
            logger.error("HTTP error while uploading to %s: %s", url, exc)
            raise GofileUploadError("Upload failed", context={"url": url}) from exc

    def upload_file(
        self,
        file_path: str,
        folder_id: Optional[str] = None,
        callback: Optional[Callable[[int], None]] = None,
    ) -> Dict[str, object]:
        """Compatibility helper that mirrors the legacy API."""

        result = self.upload(file_path, folder_id, callback)
        return result.to_dict()

    def create_guest_account(self) -> Dict[str, Any]:
        """Create a guest account and return the token."""

        logger.debug("Creating guest account")
        url = f"{self.API_ROOT}/accounts"
        response = self._request("POST", url, context={"action": "create_guest"})

        if "token" in response:
            self.token = str(response["token"])
            self.client.headers.update({"Authorization": f"Bearer {self.token}"})
            logger.debug("Guest account created with token: %s***", self.token[:4])

        return response

    def get_contents(self, content_id: str) -> Dict[str, Any]:
        """Fetch information about a content ID (folder or file)."""

        # If we don't have a token, create a guest account first
        if not self.token:
            logger.debug("No token available, creating guest account")
            self.create_guest_account()

        logger.debug("Fetching contents for: %s", content_id)
        # Add query parameters and website token header as shown in the API
        url = f"{self.API_ROOT}/contents/{content_id}"
        params = {
            "contentFilter": "",
            "page": "1",
            "pageSize": "1000",
            "sortField": "name",
            "sortDirection": "1"
        }
        headers = {
            # to avoid error-notPremium
            "x-website-token": "4fd6sg89d7s6"
        }
        return self._request(
            "GET", url, params=params, headers=headers, context={"content_id": content_id}
        )

    def download_file(
        self,
        download_url: str,
        output_path: str,
        callback: Optional[Callable[[int], None]] = None,
    ) -> None:
        """Download a file from the provided direct link."""

        logger.info("Starting download: %s -> %s", download_url, output_path)

        cookies = {}
        if self.token:
            cookies["accountToken"] = self.token
            logger.debug("Using accountToken cookie for download")

        try:
            with self.client.stream("GET", download_url, cookies=cookies, timeout=None) as response:
                response.raise_for_status()

                total_size = int(response.headers.get("content-length", 0))
                logger.debug("File size: %s bytes", total_size)

                os.makedirs(os.path.dirname(output_path) or ".", exist_ok=True)

                with open(output_path, "wb") as f:
                    for chunk in response.iter_bytes(chunk_size=8192):
                        if chunk:
                            f.write(chunk)
                            if callback:
                                callback(len(chunk))

                logger.info("Download complete: %s", output_path)
        except httpx.HTTPError as exc:
            logger.error("Download failed for %s: %s", download_url, exc)
            raise GofileNetworkError(
                f"Failed to download from {download_url}",
                context={"url": download_url, "output": output_path}
            ) from exc
        except OSError as exc:
            logger.error("Failed to write file %s: %s", output_path, exc)
            raise GofileError(
                f"Failed to write file to {output_path}",
                context={"output": output_path}
            ) from exc
