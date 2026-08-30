"""
Pluggable Drive Service Interface.

Implement the `upload` method to store files remotely.
Currently stubbed — returns a local path placeholder.
Swap in a real Google Drive implementation later by replacing
the `StubDriveService` with `GoogleDriveService` in `get_drive_service()`.
"""

from abc import ABC, abstractmethod
from typing import Optional


class DriveServiceBase(ABC):
    """Interface for any file storage backend."""

    @abstractmethod
    async def upload(self, file_bytes: bytes, remote_path: str) -> str:
        """
        Upload file bytes to the storage backend.

        Args:
            file_bytes: Raw file content.
            remote_path: Desired path/key in the remote storage.

        Returns:
            A URL or path string where the file can be accessed.
        """
        ...


class StubDriveService(DriveServiceBase):
    """
    Stub implementation that returns a fake local path.
    Replace with GoogleDriveService once credentials are available.
    """

    async def upload(self, file_bytes: bytes, remote_path: str) -> str:
        # In stub mode we just return a placeholder URL
        return f"stub://drive/{remote_path}"


class GoogleDriveService(DriveServiceBase):
    """
    Real Google Drive implementation — placeholder for future.
    Will use a service account JSON and target folder ID from settings.
    """

    def __init__(self, credentials_path: str, folder_id: str):
        self.credentials_path = credentials_path
        self.folder_id = folder_id
        # TODO: Initialize google drive client here

    async def upload(self, file_bytes: bytes, remote_path: str) -> str:
        # TODO: Implement real upload
        raise NotImplementedError("Google Drive upload not yet implemented")


def get_drive_service() -> DriveServiceBase:
    """
    Factory function. Returns the active drive service.
    Currently returns the stub; swap to GoogleDriveService when ready.
    """
    from app.core.config import settings

    if settings.GOOGLE_DRIVE_CREDENTIALS_PATH and settings.GOOGLE_DRIVE_FOLDER_ID:
        # When credentials are provided, use real service
        # return GoogleDriveService(settings.GOOGLE_DRIVE_CREDENTIALS_PATH, settings.GOOGLE_DRIVE_FOLDER_ID)
        pass  # Uncomment the above when GoogleDriveService is implemented

    return StubDriveService()
