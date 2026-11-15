"""Application settings loaded from environment variables.

Secrets are wrapped in :class:`pydantic.SecretStr` so they are not rendered in
logs or tracebacks. The only supported production database is Neon (Lakebase
PostgreSQL); SQLite is allowed for isolated local development and tests.
Authentication is Neon Auth (Managed Better Auth): access tokens are EdDSA JWTs
verified locally against the branch JWKS.
"""

from __future__ import annotations

import json
from functools import lru_cache
from pathlib import Path
from typing import Any, Literal
from urllib.parse import urlparse

from pydantic import Field, SecretStr, field_validator, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

BASE_DIR = Path(__file__).resolve().parent.parent
DEFAULT_DATABASE_URL = f"sqlite:///{(BASE_DIR / 'smart_travel_dev.db').as_posix()}"


class Settings(BaseSettings):
    """Runtime configuration.

    All values can be supplied through environment variables or ``backend/.env``.
    See ``.env.example`` for the complete documented list.
    """

    model_config = SettingsConfigDict(
        env_file=(BASE_DIR / ".env"),
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    # ------------------------------------------------------------------ app
    app_name: str = "Smart Travel Planner API"
    app_version: str = "1.0.0"
    app_env: Literal["development", "test", "production"] = "development"
    debug: bool = False
    log_level: str = "INFO"
    api_v1_prefix: str = "/api/v1"

    cors_origins: str = "http://localhost:5173,http://localhost:3000"
    allowed_hosts: str = "localhost,127.0.0.1,testserver"
    frontend_url: str = "http://localhost:5173"
    google_oauth_redirect_url: str = "http://localhost:5173/auth/callback"
    # Built SPA copied into the container (single-service deployments).
    frontend_dist_path: str = str(BASE_DIR.parent / "frontend" / "dist")

    request_timeout_seconds: float = Field(default=90.0, gt=0, le=300)
    max_request_body_bytes: int = Field(default=1_048_576, ge=1024)
    auth_rate_limit_requests: int = Field(default=20, ge=1)
    auth_rate_limit_window_seconds: int = Field(default=60, ge=1)

    # --------------------------------------------------------------- database
    database_url: SecretStr = Field(default=SecretStr(DEFAULT_DATABASE_URL))
    auto_create_schema: bool = True
    db_pool_min_size: int = Field(default=1, ge=1)
    db_pool_max_size: int = Field(default=10, ge=1)
    db_pool_timeout_seconds: float = Field(default=10.0, gt=0)

    # -------------------------------------------------------------- Neon Auth
    # Managed Better Auth on the branch. Tokens are EdDSA JWTs (Ed25519,
    # 15-minute expiry) verified locally against NEON_AUTH_JWKS_URL.
    neon_auth_base_url: str | None = None
    neon_auth_jwks_url: str | None = None
    # Optional override for the expected JWT iss/aud (derived from the base
    # URL's host origin when unset).
    neon_auth_issuer: str | None = None
    # Origin sent to Neon Auth on server-to-server calls. Neon Auth rejects
    # requests without a trusted Origin header. Localhost ports are
    # pre-approved; production origins must be added with
    # `neon neon-auth domain add <origin>`.
    neon_auth_origin: str | None = None
    neon_auth_timeout_seconds: float = Field(default=10.0, gt=0, le=60)
    neon_auth_jwks_cache_seconds: int = Field(default=3600, ge=60)
    jwt_leeway_seconds: int = Field(default=30, ge=0)
    # Symmetric verification is available ONLY for offline tests and local
    # development. Production rejects any configured HS256 secret and verifies
    # asymmetric EdDSA tokens through the branch JWKS.
    auth_hs256_secret: SecretStr | None = None

    # -------------------------------------------------------- Neon AI Gateway
    # Optional. When both values are present, Gemini calls are routed through
    # the branch AI Gateway instead of a direct Google API key.
    neon_ai_gateway_base_url: str | None = None
    neon_ai_gateway_token: SecretStr | None = None

    # --------------------------------------------------- Neon Object Storage
    # S3-compatible storage that branches with the database.
    neon_storage_bucket: str = "assets"
    aws_access_key_id: SecretStr | None = None
    aws_secret_access_key: SecretStr | None = None
    aws_endpoint_url_s3: str | None = None
    aws_region: str | None = None

    # ------------------------------------------------- Neon Realtime/Functions
    # Declared branch services without a Python-native SDK yet. They are wired
    # through configuration so the app can report their readiness and adopt
    # them without another settings migration.
    neon_realtime_url: str | None = None
    neon_realtime_secret: SecretStr | None = None
    neon_function_host_suffix: str | None = None

    # ----------------------------------------------------------------- Gemini
    gemini_api_key: SecretStr | None = None
    gemini_model: str = "gemini-2.5-flash"
    gemini_timeout_seconds: float = Field(default=60.0, gt=0, le=180)
    gemini_temperature: float = Field(default=0.35, ge=0, le=1)

    # ------------------------------------------------------------ Google Maps
    google_maps_api_key: SecretStr | None = None
    google_maps_timeout_seconds: float = Field(default=10.0, gt=0, le=60)
    google_maps_language: str = "en"
    # "No limit" entry caching: 0 means unbounded entries, expired entries are
    # still purged. TTLs are intentionally long for places that rarely change.
    maps_cache_ttl_seconds: int = Field(default=86_400, ge=0)
    maps_photo_cache_ttl_seconds: int = Field(default=21_600, ge=0)
    maps_route_cache_ttl_seconds: int = Field(default=3_600, ge=0)

    # ------------------------------------------------------------------ Grok
    # xAI's OpenAI-compatible API. Grok is used as an additional itinerary
    # provider; Gemini remains available and provider order is configurable.
    grok_api_key: SecretStr | None = None
    grok_model: str = "grok-4-fast-non-reasoning"
    grok_base_url: str = "https://api.x.ai/v1"
    grok_timeout_seconds: float = Field(default=60.0, gt=0, le=180)
    grok_temperature: float = Field(default=0.35, ge=0, le=1)
    ai_provider_order: str = "gemini,grok"

    # -------------------------------------------------------------- OpenWeather
    openweather_api_key: SecretStr | None = None
    openweather_timeout_seconds: float = Field(default=10.0, gt=0, le=60)
    weather_cache_ttl_seconds: int = Field(default=600, ge=0)
    weather_geocode_cache_ttl_seconds: int = Field(default=86_400, ge=0)

    # ------------------------------------------------------------- itinerary
    max_trip_days: int = Field(default=30, ge=1, le=60)
    max_travellers: int = Field(default=20, ge=1, le=50)
    max_activities_per_day: int = Field(default=8, ge=1, le=12)
    max_route_legs: int = Field(default=16, ge=0, le=50)
    budget_rates_json: str | None = None

    # --------------------------------------------------------------- helpers
    @field_validator(
        "neon_auth_base_url",
        "neon_auth_jwks_url",
        "neon_auth_issuer",
        "neon_auth_origin",
        "neon_ai_gateway_base_url",
        "aws_endpoint_url_s3",
        "neon_realtime_url",
        "frontend_url",
        "google_oauth_redirect_url",
        "grok_base_url",
        mode="before",
    )
    @classmethod
    def _strip_url(cls, value: Any) -> Any:
        if isinstance(value, str) and value.strip():
            return value.strip().rstrip("/")
        return None if value == "" else value

    @field_validator(
        "auth_hs256_secret",
        "neon_ai_gateway_token",
        "aws_access_key_id",
        "aws_secret_access_key",
        "neon_realtime_secret",
        "gemini_api_key",
        "grok_api_key",
        "google_maps_api_key",
        "openweather_api_key",
        mode="after",
    )
    @classmethod
    def _blank_secret_is_none(cls, value: SecretStr | None) -> SecretStr | None:
        if value is None:
            return None
        if not value.get_secret_value().strip():
            return None
        return value

    @staticmethod
    def _valid_url(value: str | None) -> str | None:
        if value is None:
            return None
        parsed = urlparse(value)
        if parsed.scheme not in {"http", "https", "wss"} or not parsed.netloc:
            raise ValueError("URL settings must be valid http(s)/wss URLs")
        return value

    @field_validator(
        "neon_auth_base_url",
        "neon_auth_jwks_url",
        "neon_auth_issuer",
        "neon_auth_origin",
        "neon_ai_gateway_base_url",
        "aws_endpoint_url_s3",
        "neon_realtime_url",
        "grok_base_url",
        mode="after",
    )
    @classmethod
    def _validate_urls(cls, value: str | None) -> str | None:
        return cls._valid_url(value)

    @field_validator("cors_origins", "allowed_hosts")
    @classmethod
    def _strip_csv(cls, value: str) -> str:
        return ",".join(part.strip() for part in value.split(",") if part.strip())

    @model_validator(mode="after")
    def _validate_environment(self) -> "Settings":
        if self.db_pool_max_size < self.db_pool_min_size:
            raise ValueError("DB_POOL_MAX_SIZE must be >= DB_POOL_MIN_SIZE")

        if self.app_env == "production":
            if not self.cors_origin_list:
                raise ValueError("CORS_ORIGINS must contain at least one exact origin")
            if "*" in self.cors_origin_list:
                raise ValueError("Wildcard CORS origins are not allowed in production")
            if not self.allowed_host_list:
                raise ValueError("ALLOWED_HOSTS must contain at least one host")
            if "*" in self.allowed_host_list:
                raise ValueError("Wildcard ALLOWED_HOSTS values are not allowed in production")
            for origin in self.cors_origin_list:
                parsed_origin = urlparse(origin)
                if parsed_origin.scheme not in {"http", "https"} or not parsed_origin.netloc:
                    raise ValueError(
                        "Every CORS_ORIGINS entry must be an exact http(s) origin"
                    )
            if self.auto_create_schema:
                raise ValueError(
                    "AUTO_CREATE_SCHEMA must be false in production; apply "
                    "backend/neon/schema.sql explicitly."
                )
            if not self.database_dsn.startswith("postgresql://"):
                raise ValueError(
                    "Production DATABASE_URL must be a Neon (Lakebase PostgreSQL) "
                    "connection string (postgresql://...). SQLite and other "
                    "databases are not supported."
                )
            if not self.neon_auth_base_url or not self.neon_auth_jwks_url:
                raise ValueError(
                    "NEON_AUTH_BASE_URL and NEON_AUTH_JWKS_URL are required in "
                    "production; run `neon env pull` for the linked branch."
                )
            if self.auth_hs256_secret is not None:
                raise ValueError(
                    "AUTH_HS256_SECRET is only for offline tests and local "
                    "development; production must verify EdDSA tokens via JWKS."
                )
            if self.debug:
                raise ValueError("DEBUG must be false in production")
        return self

    @property
    def integration_warnings(self) -> list[str]:
        """Optional integrations that are not configured.

        Maps, weather and the AI generator are valuable but not required for
        the API to boot: endpoints return an explicit 503 (or the deterministic
        planner fallback) instead of preventing deployment.
        """
        missing: list[str] = []
        if not self.ai_configured:
            missing.append("GEMINI_API_KEY, GROK_API_KEY, or Neon AI Gateway")
        if not self.google_maps_api_key:
            missing.append("GOOGLE_MAPS_API_KEY")
        if not self.openweather_api_key:
            missing.append("OPENWEATHER_API_KEY")
        return missing

    @property
    def cors_origin_list(self) -> list[str]:
        # Exact origins never include a trailing slash; normalise here so the
        # same value behaves consistently in CORS matching and OAuth checks.
        return [
            origin.rstrip("/")
            for origin in self.cors_origins.split(",")
            if origin.rstrip("/")
        ]

    @property
    def allowed_host_list(self) -> list[str]:
        return [host for host in self.allowed_hosts.split(",") if host]

    @property
    def database_dsn(self) -> str:
        return self.database_url.get_secret_value()

    @property
    def sqlite_database(self) -> bool:
        return self.database_dsn.startswith("sqlite")

    # --------------------------------------------------------- Neon Auth props
    @property
    def auth_issuer(self) -> str | None:
        """Better Auth JWTs carry ``iss``/``aud`` equal to the Auth host origin.

        Verified live: the token issuer is the Neon Auth host without the
        tenant path (``https://<host>.neonauth.<region>.aws.neon.tech``), even
        though the API base URL ends in ``/neondb/auth``. Set
        ``NEON_AUTH_ISSUER`` to override if a deployment ever differs.
        """
        if self.neon_auth_issuer:
            return self.neon_auth_issuer
        base = self.neon_auth_base_url
        if not base:
            return None
        parsed = urlparse(base)
        return f"{parsed.scheme}://{parsed.netloc}"

    @property
    def auth_origin(self) -> str:
        """Origin header sent on server-to-server calls to Neon Auth."""
        return self.neon_auth_origin or self.frontend_url

    @property
    def auth_hs256_key(self) -> str | None:
        return (
            self.auth_hs256_secret.get_secret_value()
            if self.auth_hs256_secret
            else None
        )

    # ------------------------------------------------------- integration props
    @property
    def gemini_key(self) -> str | None:
        return self.gemini_api_key.get_secret_value() if self.gemini_api_key else None

    @property
    def grok_key(self) -> str | None:
        return self.grok_api_key.get_secret_value() if self.grok_api_key else None

    @property
    def gemini_configured(self) -> bool:
        return bool(self.gemini_key or self.ai_gateway_url)

    @property
    def ai_configured(self) -> bool:
        return bool(self.grok_key or self.gemini_configured)

    @property
    def ai_provider_list(self) -> list[str]:
        """Configured providers in the requested order, without duplicates."""
        requested = [
            part.strip().lower()
            for part in self.ai_provider_order.split(",")
            if part.strip()
        ]
        available = {
            "grok": bool(self.grok_key),
            "gemini": self.gemini_configured,
        }
        ordered = [name for name in requested if available.get(name)]
        # Any configured provider omitted from the order still participates.
        ordered.extend(name for name in ("gemini", "grok") if available[name] and name not in ordered)
        return ordered

    @property
    def ai_gateway_key(self) -> str | None:
        return (
            self.neon_ai_gateway_token.get_secret_value()
            if self.neon_ai_gateway_token
            else None
        )

    @property
    def ai_gateway_url(self) -> str | None:
        """Native Gemini dialect base URL for the google-genai SDK."""
        if self.neon_ai_gateway_base_url and self.ai_gateway_key:
            return f"{self.neon_ai_gateway_base_url}/gemini"
        return None

    @property
    def maps_key(self) -> str | None:
        return (
            self.google_maps_api_key.get_secret_value()
            if self.google_maps_api_key
            else None
        )

    @property
    def weather_key(self) -> str | None:
        return (
            self.openweather_api_key.get_secret_value()
            if self.openweather_api_key
            else None
        )

    @property
    def oauth_allowed_redirects(self) -> set[str]:
        return {
            url.rstrip("/")
            for url in (
                self.frontend_url,
                self.google_oauth_redirect_url,
                *self.cors_origin_list,
            )
            if url
        }

    def budget_rates(self) -> dict[str, Any]:
        """Return configured budget estimation profiles.

        Currency-specific profiles are planning estimates, not live prices.
        """
        if not self.budget_rates_json:
            return {}
        try:
            parsed = json.loads(self.budget_rates_json)
        except json.JSONDecodeError as exc:
            raise ValueError("BUDGET_RATES_JSON must be valid JSON") from exc
        if not isinstance(parsed, dict):
            raise ValueError("BUDGET_RATES_JSON must be a JSON object")
        return parsed

    def integration_status(self) -> dict[str, bool]:
        return {
            "neon_auth": bool(self.neon_auth_base_url and self.neon_auth_jwks_url),
            "gemini": bool(self.gemini_key or self.ai_gateway_url),
            "grok": bool(self.grok_key),
            "google_maps": bool(self.google_maps_api_key),
            "openweather": bool(self.openweather_api_key),
            "ai_gateway": bool(self.ai_gateway_url),
            "object_storage": bool(
                self.aws_access_key_id
                and self.aws_secret_access_key
                and self.aws_endpoint_url_s3
            ),
            "realtime": bool(self.neon_realtime_url),
        }


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    return Settings()
