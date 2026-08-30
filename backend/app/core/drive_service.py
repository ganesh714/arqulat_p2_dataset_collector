"""
Pluggable Drive Service Interface.

Implement the `upload` method to store files remotely.
GoogleDriveService is used when credentials are configured.
StubDriveService is the fallback for local dev without Drive.
"""

import io
import logging
import os
from abc import ABC, abstractmethod
from typing import Optional, Dict

logger = logging.getLogger(__name__)


class DriveServiceBase(ABC):
    """Interface for any file storage backend."""

    @abstractmethod
    async def upload(self, file_bytes: bytes, remote_path: str) -> str:
        """
        Upload file bytes to the storage backend.

        Args:
            file_bytes: Raw file content.
            remote_path: Desired path/key in the remote storage.
                         e.g. "entries/{entry_id}/render.png"

        Returns:
            A URL or path string where the file can be accessed.
        """
        ...


class StubDriveService(DriveServiceBase):
    """
    Stub implementation that returns a fake local path.
    Used when Google Drive credentials are not configured.
    """

    async def upload(self, file_bytes: bytes, remote_path: str) -> str:
        logger.info(f"[STUB] Would upload {len(file_bytes)} bytes to: {remote_path}")
        return f"stub://drive/{remote_path}"


class GoogleDriveService(DriveServiceBase):
    """
    Real Google Drive implementation using a service account.

    Uploads files to a nested folder structure under the configured
    root folder:
        /{phase}/{subphase}/{category}/{entry_code}/render.png
        /{phase}/{subphase}/{category}/{entry_code}/model.glb

    Creates folders on-the-fly if they don't exist, caching folder IDs
    to avoid redundant API calls within the same process lifetime.
    """

    # MIME types
    FOLDER_MIME = "application/vnd.google-apps.folder"
    MIME_MAP = {
        ".png": "image/png",
        ".jpg": "image/jpeg",
        ".jpeg": "image/jpeg",
        ".glb": "model/gltf-binary",
        ".gltf": "model/gltf+json",
        ".json": "application/json",
        ".py": "text/x-python",
    }

    def __init__(self, client_id: str, client_secret: str, refresh_token: str, folder_id: str):
        from google.oauth2.credentials import Credentials
        from googleapiclient.discovery import build

        self.root_folder_id = folder_id

        # Authenticate with standard OAuth refresh token
        creds = Credentials(
            token=None,
            refresh_token=refresh_token,
            client_id=client_id,
            client_secret=client_secret,
            token_uri="https://oauth2.googleapis.com/token",
            scopes=["https://www.googleapis.com/auth/drive.file"],
        )
        self.service = build("drive", "v3", credentials=creds)

        # Cache: "parent_id/folder_name" -> folder_id
        self._folder_cache: Dict[str, str] = {}

        logger.info(f"GoogleDriveService initialized (root folder: {folder_id})")

    def _get_or_create_folder(self, folder_name: str, parent_id: str) -> str:
        """
        Find a folder by name under parent_id, or create it.
        Results are cached for the lifetime of this service instance.
        """
        cache_key = f"{parent_id}/{folder_name}"
        if cache_key in self._folder_cache:
            return self._folder_cache[cache_key]

        # Search for existing folder
        query = (
            f"name = '{folder_name}' "
            f"and '{parent_id}' in parents "
            f"and mimeType = '{self.FOLDER_MIME}' "
            f"and trashed = false"
        )
        results = (
            self.service.files()
            .list(q=query, spaces="drive", fields="files(id, name)", pageSize=1,
                  supportsAllDrives=True, includeItemsFromAllDrives=True)
            .execute()
        )
        files = results.get("files", [])

        if files:
            folder_id = files[0]["id"]
            logger.debug(f"Found existing folder: {folder_name} ({folder_id})")
        else:
            # Create the folder
            metadata = {
                "name": folder_name,
                "mimeType": self.FOLDER_MIME,
                "parents": [parent_id],
            }
            folder = (
                self.service.files()
                .create(body=metadata, fields="id", supportsAllDrives=True)
                .execute()
            )
            folder_id = folder["id"]
            logger.info(f"Created folder: {folder_name} ({folder_id})")

        self._folder_cache[cache_key] = folder_id
        return folder_id

    def _ensure_folder_path(self, path_segments: list[str]) -> str:
        """
        Walk a list of folder names, creating any that don't exist,
        and return the final folder's ID.

        e.g. ["Modeling", "Furniture", "Chair", "chair0001_v1"]
        """
        current_parent = self.root_folder_id
        for segment in path_segments:
            current_parent = self._get_or_create_folder(segment, current_parent)
        return current_parent

    def _guess_mime(self, filename: str) -> str:
        """Guess MIME type from file extension."""
        import os
        _, ext = os.path.splitext(filename.lower())
        return self.MIME_MAP.get(ext, "application/octet-stream")

    async def upload(self, file_bytes: bytes, remote_path: str) -> str:
        """
        Upload a file to Google Drive.

        remote_path format: "entries/{entry_id}/{filename}"
            (this is the existing contract from the jobs router)

        The file is placed under the root folder. The path segments
        before the filename become nested folders.
        """
        import os
        from googleapiclient.http import MediaIoBaseUpload

        # Split path into folder segments and filename
        parts = remote_path.replace("\\", "/").strip("/").split("/")
        filename = parts[-1]
        folder_segments = parts[:-1]  # e.g. ["entries", "{entry_id}"]

        # Create/find nested folder structure
        if folder_segments:
            parent_id = self._ensure_folder_path(folder_segments)
        else:
            parent_id = self.root_folder_id

        # Check if file already exists (to update rather than duplicate)
        query = (
            f"name = '{filename}' "
            f"and '{parent_id}' in parents "
            f"and trashed = false"
        )
        existing = (
            self.service.files()
            .list(q=query, spaces="drive", fields="files(id)", pageSize=1,
                  supportsAllDrives=True, includeItemsFromAllDrives=True)
            .execute()
        )
        existing_files = existing.get("files", [])

        mime_type = self._guess_mime(filename)
        media = MediaIoBaseUpload(io.BytesIO(file_bytes), mimetype=mime_type, resumable=False)

        if existing_files:
            # Update existing file
            file_id = existing_files[0]["id"]
            self.service.files().update(
                fileId=file_id,
                media_body=media,
                supportsAllDrives=True,
            ).execute()
            logger.info(f"Updated existing file: {filename} ({file_id})")
        else:
            # Create new file
            file_metadata = {
                "name": filename,
                "parents": [parent_id],
            }
            created = (
                self.service.files()
                .create(body=file_metadata, media_body=media, fields="id",
                        supportsAllDrives=True)
                .execute()
            )
            file_id = created["id"]
            logger.info(f"Uploaded new file: {filename} ({file_id})")

        # Make the file publicly readable via link
        try:
            self.service.permissions().create(
                fileId=file_id,
                body={"type": "anyone", "role": "reader"},
                supportsAllDrives=True,
            ).execute()
        except Exception as e:
            logger.warning(f"Failed to set public permission on {file_id}: {e}")

        # Return the direct web content link
        url = f"https://drive.google.com/file/d/{file_id}/view?usp=sharing"
        logger.info(f"File URL: {url}")
        return url


# ─── Singleton ──────────────────────────────────────────────────────

_drive_service_instance: Optional[DriveServiceBase] = None


def get_drive_service() -> DriveServiceBase:
    """
    Factory function. Returns a singleton drive service instance.
    Uses GoogleDriveService when credentials are configured,
    falls back to StubDriveService otherwise.
    """
    global _drive_service_instance
    if _drive_service_instance is not None:
        return _drive_service_instance

    from app.core.config import settings

    has_oauth = (
        settings.GOOGLE_CLIENT_ID and 
        settings.GOOGLE_CLIENT_SECRET and 
        settings.GOOGLE_REFRESH_TOKEN and 
        settings.GOOGLE_DRIVE_FOLDER_ID
    )

    if has_oauth:
        try:
            _drive_service_instance = GoogleDriveService(
                settings.GOOGLE_CLIENT_ID,
                settings.GOOGLE_CLIENT_SECRET,
                settings.GOOGLE_REFRESH_TOKEN,
                settings.GOOGLE_DRIVE_FOLDER_ID,
            )
            logger.info("Using GoogleDriveService (OAuth credentials found)")
        except Exception as e:
            logger.error(f"Failed to initialize GoogleDriveService: {e}")
            logger.warning("Falling back to StubDriveService")
            _drive_service_instance = StubDriveService()
    else:
        logger.info("No full Drive OAuth credentials configured — using StubDriveService")
        _drive_service_instance = StubDriveService()

    return _drive_service_instance
