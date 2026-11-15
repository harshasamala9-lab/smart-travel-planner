"""Offline tests for the Neon Object Storage service wrapper.

boto3 is stubbed at the ``_client`` attribute, so no network access or optional
dependency is needed: only the wrapper's own logic (configuration checks,
bucket naming, error propagation, off-loop execution) is exercised.
"""

from __future__ import annotations

import pytest
from pydantic import SecretStr

from app.config import Settings
from app.services.neon_object_storage_service import NeonObjectStorageService


def _settings(**overrides) -> Settings:
    values = {
        "app_env": "test",
        "database_url": SecretStr("sqlite:///:memory:"),
        "neon_storage_bucket": "assets",
        "aws_access_key_id": SecretStr("test-key"),
        "aws_secret_access_key": SecretStr("test-secret"),
        "aws_endpoint_url_s3": "https://storage.example.neon.tech",
        "aws_region": "ap-southeast-1",
    }
    values.update(overrides)
    return Settings(_env_file=None, **values)


class _FakeS3Client:
    """Records boto3-style calls and replays canned responses."""

    def __init__(self, fail_on: str | None = None) -> None:
        self.calls: list[tuple[str, dict]] = []
        self.fail_on = fail_on

    async def _record(self, name: str, kwargs: dict):
        self.calls.append((name, kwargs))
        if self.fail_on == name:
            raise RuntimeError(f"{name} failed")
        if name == "head_bucket":
            return {}
        if name == "put_object":
            return {"ETag": '"etag-1"'}
        if name == "get_object":
            body = kwargs.get("_body", b"payload")
            return {"Body": self, "ContentType": "application/json"}

        return {}

    def head_bucket(self, **kwargs):
        return self._sync("head_bucket", kwargs)

    def put_object(self, **kwargs):
        return self._sync("put_object", kwargs)

    def get_object(self, **kwargs):
        return self._sync("get_object", kwargs)

    def _sync(self, name: str, kwargs: dict):
        self.calls.append((name, kwargs))
        if self.fail_on == name:
            raise RuntimeError(f"{name} failed")
        if name == "head_bucket":
            return {}
        if name == "put_object":
            return {"ETag": '"etag-1"'}
        if name == "get_object":
            return {"Body": _FakeBody(b"payload"), "ContentType": "application/json"}
        return {}


class _FakeBody:
    def __init__(self, payload: bytes) -> None:
        self._payload = payload

    def read(self) -> bytes:
        return self._payload


@pytest.mark.asyncio
async def test_check_health_reports_bucket_when_up():
    service = NeonObjectStorageService(_settings())
    fake = _FakeS3Client()
    service._client = fake
    result = await service.check_health()
    assert result == {"status": "up", "bucket": "assets"}
    assert fake.calls[0][0] == "head_bucket"


@pytest.mark.asyncio
async def test_check_health_reraises_on_failure():
    service = NeonObjectStorageService(_settings())
    service._client = _FakeS3Client(fail_on="head_bucket")
    with pytest.raises(RuntimeError, match="head_bucket failed"):
        await service.check_health()


@pytest.mark.asyncio
async def test_put_and_get_object_round_trip():
    service = NeonObjectStorageService(_settings())
    fake = _FakeS3Client()
    service._client = fake

    put = await service.put_object(
        key="itineraries/x/y.pdf", body=b"payload", content_type="application/pdf"
    )
    assert put == {"key": "itineraries/x/y.pdf", "etag": '"etag-1"'}

    body, content_type = await service.get_object(key="itineraries/x/y.pdf")
    assert body == b"payload"
    assert content_type == "application/json"

    put_call = next(c for c in fake.calls if c[0] == "put_object")
    assert put_call[1]["Bucket"] == "assets"
    assert put_call[1]["Key"] == "itineraries/x/y.pdf"
    assert put_call[1]["ContentType"] == "application/pdf"

    get_call = next(c for c in fake.calls if c[0] == "get_object")
    assert get_call[1]["Bucket"] == "assets"


def test_is_configured_and_bucket_name():
    assert NeonObjectStorageService(_settings()).is_configured is True
    assert NeonObjectStorageService(_settings()).bucket == "assets"

    unconfigured = NeonObjectStorageService(
        _settings(aws_access_key_id=None, aws_secret_access_key=None)
    )
    assert unconfigured.is_configured is False
    with pytest.raises(RuntimeError, match="Object storage is not configured"):
        unconfigured.client()


def test_client_is_cached():
    service = NeonObjectStorageService(_settings())
    first = service.client()
    assert first is not None
    assert service.client() is first
