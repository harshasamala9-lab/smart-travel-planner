"""Neon Object Storage: branch-scoped, S3-compatible storage.

Credentials come from the branch env pulled by ``neon env pull``
(``AWS_ACCESS_KEY_ID``, ``AWS_SECRET_ACCESS_KEY``, ``AWS_ENDPOINT_URL_S3``,
``AWS_REGION``). Every branch has its own bucket namespace, so storage state
branches together with the database. boto3 is imported lazily so the offline
test suite does not require it to be installed.
"""

from __future__ import annotations

import logging
from typing import Any

from app.config import Settings

logger = logging.getLogger(__name__)


class NeonObjectStorageService:
    """Thin S3 client wrapper for the branch's object storage bucket."""

    def __init__(self, settings: Settings) -> None:
        self._settings = settings
        self._client: Any | None = None

    @property
    def is_configured(self) -> bool:
        return bool(
            self._settings.aws_access_key_id
            and self._settings.aws_secret_access_key
            and self._settings.aws_endpoint_url_s3
        )

    @property
    def bucket(self) -> str:
        return self._settings.neon_storage_bucket

    def client(self) -> Any:
        if not self.is_configured:
            raise RuntimeError(
                "Object storage is not configured. Set AWS_ACCESS_KEY_ID, "
                "AWS_SECRET_ACCESS_KEY, and AWS_ENDPOINT_URL_S3 (run "
                "`neon env pull` for the linked branch)."
            )
        if self._client is None:
            import boto3  # imported lazily; optional dependency for this service
            from botocore.config import Config

            self._client = boto3.client(
                "s3",
                endpoint_url=self._settings.aws_endpoint_url_s3,
                aws_access_key_id=self._settings.aws_access_key_id.get_secret_value(),
                aws_secret_access_key=(
                    self._settings.aws_secret_access_key.get_secret_value()
                ),
                region_name=self._settings.aws_region or "auto",
                config=Config(
                    retries={"max_attempts": 3, "mode": "standard"},
                    s3={"addressing_style": "path"},
                ),
            )
        return self._client

    async def check_health(self) -> dict[str, Any]:
        """Verify the bucket is reachable. Raises on any failure."""
        client = self.client()
        try:
            await _call(
                client.head_bucket,
                Bucket=self.bucket,
            )
        except Exception as exc:
            logger.warning("Object storage health check failed: %s", type(exc).__name__)
            raise
        return {"status": "up", "bucket": self.bucket}

    async def put_object(
        self, *, key: str, body: bytes, content_type: str
    ) -> dict[str, Any]:
        client = self.client()
        response = await _call(
            client.put_object,
            Bucket=self.bucket,
            Key=key,
            Body=body,
            ContentType=content_type,
        )
        return {"key": key, "etag": response.get("ETag")}

    async def get_object(self, *, key: str) -> tuple[bytes, str]:
        client = self.client()
        response = await _call(client.get_object, Bucket=self.bucket, Key=key)
        payload = response["Body"].read()
        content_type = response.get("ContentType", "application/octet-stream")
        return payload, content_type


async def _call(function: Any, **kwargs: Any) -> Any:
    """Run a blocking boto3 call off the event loop."""
    import asyncio

    return await asyncio.to_thread(function, **kwargs)
