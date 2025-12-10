#!/usr/bin/env python3

import httpx
import logging
import os
from typing import Optional, List, Dict, Callable
from .utils import ProgressFileReader

logger = logging.getLogger(__name__)

class GofileClient:
    API_ROOT = "https://api.gofile.io"
    UPLOAD_SERVER_URL = "https://upload.gofile.io"

    def __init__(self, token: Optional[str] = None):
        self.token = token
        # Increase timeout for large API operations, though uploads handle their own timeout
        self.client = httpx.Client(timeout=30.0) 
        
        if self.token:
            logger.debug(f"Initialized with token: {self.token[:4]}***")
            self.client.headers.update({"Authorization": f"Bearer {self.token}"})

    def _handle_response(self, response: httpx.Response) -> Dict:
        try:
            data = response.json()
        except Exception:
            logger.error(f"Failed to parse JSON: {response.text}")
            response.raise_for_status()
            return {}

        if data.get("status") != "ok":
            logger.error(f"API Error: {data}")
            raise Exception(f"Gofile API Error: {data.get('status')} - {data.get('data')}")
        
        return data.get("data", {})

    def get_server(self) -> str:
        """
        Gofile suggests using specific servers (availables in their doc), 
        but 'upload.gofile.io' uses DNS geo-routing automatically.
        We stick to the best practice default.
        """
        return self.UPLOAD_SERVER_URL

    def create_folder(self, parent_folder_id: str, folder_name: str) -> Dict:
        logger.debug(f"Creating folder '{folder_name}' in '{parent_folder_id}'")
        url = f"{self.API_ROOT}/contents/createFolder"
        payload = {
            "parentFolderId": parent_folder_id,
            "folderName": folder_name
        }
        res = self.client.post(url, json=payload)
        return self._handle_response(res)

    def delete_content(self, content_ids: List[str]) -> Dict:
        logger.debug(f"Deleting content IDs: {content_ids}")
        url = f"{self.API_ROOT}/contents"
        # HTTPX needs 'content' or 'json' for DELETE requests explicitly if body is required
        res = self.client.request("DELETE", url, json={"contentsId": ",".join(content_ids)})
        return self._handle_response(res)

    def upload_file(self, 
                    file_path: str, 
                    folder_id: Optional[str] = None, 
                    callback: Optional[Callable[[int], None]] = None) -> Dict:
        
        server_url = f"{self.get_server()}/uploadfile"
        file_name = os.path.basename(file_path)
        
        # Prepare parameters
        data = {}
        if self.token:
            data["token"] = self.token
        if folder_id:
            data["folderId"] = folder_id

        # Use our custom ProgressFileReader
        # If no callback is provided, we use a dummy lambda to avoid errors
        progress_callback = callback if callback else lambda x: None
        
        logger.info(f"Starting upload: {file_name} -> {server_url}")
        
        # Open file using our wrapper
        with ProgressFileReader(file_path, progress_callback) as f:
            files = {'file': (file_name, f)}
            
            # Use a longer timeout for the upload specifically (None = infinite)
            # This is crucial for 2000GB files
            res = self.client.post(
                server_url, 
                data=data, 
                files=files, 
                timeout=None 
            )

        return self._handle_response(res)
