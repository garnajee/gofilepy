#!/usr/bin/env python3

import httpx
import logging
import os
from typing import Optional, List, Dict, Callable, BinaryIO, Union
from .utils import ProgressFileReader

logger = logging.getLogger(__name__)

class GofileFile:
    """Represents an uploaded file on Gofile"""
    def __init__(self, data: Dict):
        self._data = data
        self.name = data.get("fileName", "")
        self.page_link = data.get("downloadPage", "")
        self.file_id = data.get("fileId", "")
        self.parent_folder = data.get("parentFolder", "")
        
    def __repr__(self):
        return f"GofileFile(name='{self.name}', page_link='{self.page_link}')"

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
        logger.debug(f"Response Status: {response.status_code}")

        try:
            data = response.json()
            logger.debug(f"Response Body: {data}")
        except Exception:
            error_text = response.text.strip()
            logger.debug(f"Failed to parse JSON: {error_text}")
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

    def upload(self, 
               file: Union[str, BinaryIO], 
               folder_id: Optional[str] = None, 
               callback: Optional[Callable[[int], None]] = None) -> GofileFile:
        """
        Upload a file to Gofile.
        
        Args:
            file: Either a file path (str) or a file object opened in binary mode
            folder_id: Optional folder ID to upload to
            callback: Optional progress callback function
            
        Returns:
            GofileFile object with name and page_link attributes
        """
        server_url = f"{self.get_server()}/uploadfile"
        
        # Prepare parameters
        data = {}
        if self.token:
            data["token"] = self.token
        if folder_id:
            data["folderId"] = folder_id

        progress_callback = callback if callback else lambda x: None
        
        # Handle file path (string)
        if isinstance(file, str):
            file_name = os.path.basename(file)
            logger.info(f"Starting upload: {file_name} -> {server_url}")
            
            with ProgressFileReader(file, progress_callback) as f:
                files = {'file': (file_name, f)}
                res = self.client.post(
                    server_url, 
                    data=data, 
                    files=files, 
                    timeout=None 
                )
        # Handle file object
        else:
            file_name = getattr(file, 'name', 'uploaded_file')
            if hasattr(file_name, '__fspath__'):  # Path object
                file_name = os.path.basename(file_name)
            elif '/' in str(file_name) or '\\' in str(file_name):
                file_name = os.path.basename(str(file_name))
            
            logger.info(f"Starting upload: {file_name} -> {server_url}")
            files = {'file': (file_name, file)}
            res = self.client.post(
                server_url, 
                data=data, 
                files=files, 
                timeout=None 
            )

        response_data = self._handle_response(res)
        return GofileFile(response_data)

    def upload_file(self, 
                    file_path: str, 
                    folder_id: Optional[str] = None, 
                    callback: Optional[Callable[[int], None]] = None) -> Dict:
        """
        Legacy method for uploading files (returns raw dict).
        Use upload() method for a cleaner API.
        """
        result = self.upload(file_path, folder_id, callback)
        return result._data
