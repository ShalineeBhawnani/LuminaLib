"""
Local disk storage provider.
Conforms to BaseStorageService — swappable with S3 via config.
"""

import aiofiles
import aiofiles.os
from pathlib import Path

from app.core.config import settings
from app.services.storage.base import BaseStorageService


class LocalStorageService(BaseStorageService):
    def __init__(self) -> None:
        self._root = Path(settings.LOCAL_STORAGE_PATH)
        self._root.mkdir(parents=True, exist_ok=True)

    def _resolve(self, key: str) -> Path:
        path = (self._root / key).resolve()
        # Safety: prevent directory traversal
        if not str(path).startswith(str(self._root)):
            raise ValueError("Invalid storage key.")
        return path

    async def upload(self, key: str, data: bytes, content_type: str = "application/octet-stream") -> str:
        path = self._resolve(key)
        path.parent.mkdir(parents=True, exist_ok=True)
        async with aiofiles.open(path, "wb") as f:
            await f.write(data)
        return key

    async def download(self, key: str) -> bytes:
        path = self._resolve(key)
        if not path.exists():
            raise FileNotFoundError(f"Storage key not found: {key}")
        async with aiofiles.open(path, "rb") as f:
            return await f.read()

    async def delete(self, key: str) -> None:
        path = self._resolve(key)
        if path.exists():
            await aiofiles.os.remove(path)

    async def exists(self, key: str) -> bool:
        return self._resolve(key).exists()
