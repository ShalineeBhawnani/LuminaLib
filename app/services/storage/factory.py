"""
Storage service factory.
Returns the correct provider based on STORAGE_BACKEND config.
Switch Local ↔ S3/MinIO by changing a single env var.
"""

from app.services.storage.base import BaseStorageService


def get_storage_service(backend: str) -> BaseStorageService:
    if backend == "s3":
        from app.services.storage.s3_storage import S3StorageService
        return S3StorageService()

    # Default: local disk
    from app.services.storage.local_storage import LocalStorageService
    return LocalStorageService()
