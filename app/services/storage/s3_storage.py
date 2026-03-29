"""
S3 / MinIO storage provider.
Conforms to BaseStorageService — swappable with LocalStorage via config.
Set STORAGE_BACKEND=s3 in .env to activate.
"""

import aioboto3
from botocore.exceptions import ClientError

from app.core.config import settings
from app.services.storage.base import BaseStorageService


class S3StorageService(BaseStorageService):
    def __init__(self) -> None:
        self._bucket = settings.S3_BUCKET_NAME
        self._session = aioboto3.Session(
            aws_access_key_id=settings.S3_ACCESS_KEY,
            aws_secret_access_key=settings.S3_SECRET_KEY,
        )
        self._endpoint = settings.S3_ENDPOINT_URL

    def _client(self):
        return self._session.client("s3", endpoint_url=self._endpoint)

    async def upload(self, key: str, data: bytes, content_type: str = "application/octet-stream") -> str:
        async with self._client() as s3:
            await s3.put_object(
                Bucket=self._bucket,
                Key=key,
                Body=data,
                ContentType=content_type,
            )
        return key

    async def download(self, key: str) -> bytes:
        async with self._client() as s3:
            response = await s3.get_object(Bucket=self._bucket, Key=key)
            return await response["Body"].read()

    async def delete(self, key: str) -> None:
        async with self._client() as s3:
            await s3.delete_object(Bucket=self._bucket, Key=key)

    async def exists(self, key: str) -> bool:
        async with self._client() as s3:
            try:
                await s3.head_object(Bucket=self._bucket, Key=key)
                return True
            except ClientError:
                return False
