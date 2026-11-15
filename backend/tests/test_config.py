"""Configuration guards and secret handling tests."""

from __future__ import annotations

import pytest
from pydantic import SecretStr, ValidationError

from app.config import Settings


def _production_settings(**overrides) -> Settings:
    values = {
        "app_env": "production",
        "debug": False,
        "auto_create_schema": False,
        "database_url": SecretStr(
            "postgresql://owner:password@ep-test-pooler.region.aws.neon.tech/neondb"
        ),
        "neon_auth_base_url": "https://auth-host.neonauth.region.aws.neon.tech",
        "neon_auth_jwks_url": (
            "https://auth-host.neonauth.region.aws.neon.tech/.well-known/jwks.json"
        ),
        "gemini_api_key": SecretStr("gemini-key"),
        "google_maps_api_key": SecretStr("maps-key"),
        "openweather_api_key": SecretStr("weather-key"),
        "cors_origins": "https://app.example.com",
        "allowed_hosts": "api.example.com",
    }
    values.update(overrides)
    return Settings(_env_file=None, **values)


def test_blank_secrets_are_treated_as_missing():
    settings = Settings(
        _env_file=None,
        app_env="test",
        auth_hs256_secret=SecretStr("   "),
        neon_ai_gateway_token=SecretStr(""),
        gemini_api_key=SecretStr(""),
        google_maps_api_key=SecretStr("\t"),
        openweather_api_key=SecretStr(" "),
    )

    assert settings.auth_hs256_secret is None
    assert settings.neon_ai_gateway_token is None
    assert settings.gemini_api_key is None
    assert settings.google_maps_api_key is None
    assert settings.openweather_api_key is None
    assert settings.integration_status() == {
        "neon_auth": False,
        "gemini": False,
        "grok": False,
        "google_maps": False,
        "openweather": False,
        "ai_gateway": False,
        "object_storage": False,
        "realtime": False,
    }


def test_production_requires_neon_auth_but_allows_optional_integrations():
    # Maps, weather and AI are optional at boot: their endpoints return an
    # explicit 503 (or the deterministic planner fallback) instead of taking
    # the whole deployment down.
    settings = _production_settings(
        gemini_api_key=None,
        google_maps_api_key=None,
        openweather_api_key=None,
    )
    assert settings.app_env == "production"
    assert len(settings.integration_warnings) == 3
    assert any("GOOGLE_MAPS_API_KEY" in warning for warning in settings.integration_warnings)

    with pytest.raises(ValidationError, match="NEON_AUTH_BASE_URL"):
        _production_settings(
            neon_auth_base_url=None,
            neon_auth_jwks_url=(
                "https://auth-host.neonauth.region.aws.neon.tech/.well-known/jwks.json"
            ),
        )
    with pytest.raises(ValidationError, match="NEON_AUTH_JWKS_URL"):
        _production_settings(
            neon_auth_base_url="https://auth-host.neonauth.region.aws.neon.tech",
            neon_auth_jwks_url=None,
        )


def test_production_rejects_hs256_secret():
    with pytest.raises(ValidationError, match="AUTH_HS256_SECRET"):
        _production_settings(auth_hs256_secret=SecretStr("some-secret"))


def test_production_rejects_non_postgresql_database(tmp_path):
    with pytest.raises(ValidationError, match="PostgreSQL"):
        _production_settings(database_url=SecretStr(f"sqlite:///{tmp_path}/x.db"))
    with pytest.raises(ValidationError, match="PostgreSQL"):
        _production_settings(
            database_url=SecretStr("mysql://user:pass@localhost:3306/travel")
        )


def test_production_rejects_unsafe_http_settings():
    with pytest.raises(ValidationError, match="CORS"):
        _production_settings(cors_origins="*")
    with pytest.raises(ValidationError, match="CORS"):
        _production_settings(cors_origins="")
    with pytest.raises(ValidationError, match="CORS"):
        _production_settings(cors_origins="not-an-origin")
    with pytest.raises(ValidationError, match="ALLOWED_HOSTS"):
        _production_settings(allowed_hosts="")
    with pytest.raises(ValidationError, match="ALLOWED_HOSTS"):
        _production_settings(allowed_hosts="*")
    with pytest.raises(ValidationError, match="DEBUG"):
        _production_settings(debug=True)
    with pytest.raises(ValidationError, match="AUTO_CREATE_SCHEMA"):
        _production_settings(auto_create_schema=True)


def test_production_accepts_safe_postgresql_configuration():
    settings = _production_settings(
        neon_ai_gateway_base_url="https://api.ai.region.aws.neon.tech",
        neon_ai_gateway_token=SecretStr("nt_live_test"),
        aws_access_key_id=SecretStr("key"),
        aws_secret_access_key=SecretStr("secret"),
        aws_endpoint_url_s3="https://storage.region.aws.neon.tech",
        neon_realtime_url="https://realtime.region.aws.neon.tech",
    )
    assert settings.integration_status() == {
        "neon_auth": True,
        "gemini": True,
        "grok": False,
        "google_maps": True,
        "openweather": True,
        "ai_gateway": True,
        "object_storage": True,
        "realtime": True,
    }
    assert settings.cors_origin_list == ["https://app.example.com"]
    assert settings.allowed_host_list == ["api.example.com"]
    assert settings.sqlite_database is False
    assert settings.ai_gateway_url == "https://api.ai.region.aws.neon.tech/gemini"


def test_pool_and_url_validation():
    with pytest.raises(ValidationError, match="DB_POOL_MAX_SIZE"):
        Settings(_env_file=None, app_env="test", db_pool_min_size=5, db_pool_max_size=2)
    with pytest.raises(ValidationError, match="URL settings"):
        Settings(_env_file=None, app_env="test", neon_auth_base_url="not a url")

    settings = Settings(
        _env_file=None,
        app_env="test",
        neon_auth_base_url=" https://auth-host.neonauth.region.aws.neon.tech/ ",
        neon_auth_jwks_url=(
            " https://auth-host.neonauth.region.aws.neon.tech/.well-known/jwks.json/ "
        ),
        frontend_url=" https://app.example.com/ ",
    )
    assert settings.neon_auth_base_url == "https://auth-host.neonauth.region.aws.neon.tech"
    assert settings.neon_auth_jwks_url == (
        "https://auth-host.neonauth.region.aws.neon.tech/.well-known/jwks.json"
    )
    assert settings.frontend_url == "https://app.example.com"
    assert settings.auth_issuer == settings.neon_auth_base_url
    assert settings.auth_origin == "https://app.example.com"


def test_auth_origin_falls_back_to_frontend_url():
    settings = Settings(_env_file=None, app_env="test", frontend_url="https://app.example.com")
    assert settings.auth_origin == "https://app.example.com"


def test_budget_rates_and_oauth_redirects():
    settings = Settings(
        _env_file=None,
        app_env="test",
        budget_rates_json='{"USD": {"food_per_person_per_day": 55}}',
        frontend_url="https://app.example.com/",
        google_oauth_redirect_url="https://app.example.com/auth/callback/",
        cors_origins="https://app.example.com/,https://admin.example.com",
    )
    assert settings.budget_rates()["USD"]["food_per_person_per_day"] == 55
    assert settings.cors_origin_list == [
        "https://app.example.com",
        "https://admin.example.com",
    ]
    assert settings.oauth_allowed_redirects == {
        "https://app.example.com",
        "https://app.example.com/auth/callback",
        "https://admin.example.com",
    }

    with pytest.raises(ValueError, match="valid JSON"):
        Settings(
            _env_file=None, app_env="test", budget_rates_json="{not json"
        ).budget_rates()
    with pytest.raises(ValueError, match="JSON object"):
        Settings(
            _env_file=None, app_env="test", budget_rates_json="[]"
        ).budget_rates()


def test_budget_rate_overrides_are_validated_at_startup():
    from app.services.budget_service import BudgetService

    invalid_profiles = (
        ('{"USD": {"food_per_person_per_day": -1}}', "non-negative"),
        ('{"USD": {"local_transport_per_person_per_day": NaN}}', "non-negative"),
        ('{"USD": {"lodging": 25}}', "lodging"),
        ('{"US": {"food_per_person_per_day": 10}}', "currency code"),
    )
    for payload, message in invalid_profiles:
        settings = Settings(
            _env_file=None, app_env="test", budget_rates_json=payload
        )
        with pytest.raises(ValueError, match=message):
            BudgetService(settings)
