"""
Abstract base class for file storage backends.
All providers (Local, S3/MinIO) must implement this interface.
Switch backends by changing STORAGE_BACKEND in .env.
"""

from abc import ABC, abstractmethod


class BaseStorageService(ABC):

    @abstractmethod
    async def upload(self, key: str, data: bytes, content_type: str = "application/octet-stream") -> str:
        """Upload file bytes and return the storage key."""
        pass

    @abstractmethod
    async def download(self, key: str) -> bytes:
        """Download and return raw file bytes by storage key."""
        pass

    @abstractmethod
    async def delete(self, key: str) -> None:
        """Delete a file by its storage key."""
        pass

    @abstractmethod
    async def exists(self, key: str) -> bool:
        """Return True if the key exists in the backend."""
        pass
