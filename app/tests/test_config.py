"""Verificación de residencia UE (REQ-23) y guarda de secretos por defecto (B1)."""

from __future__ import annotations

import pytest

from app.core.config import (
    DEV_GEO_KEY,
    DEV_JWT_SECRET,
    InsecureDefaultSecretError,
    RegionNotEUError,
    Settings,
    assert_eu_region,
    assert_secure_secrets,
    is_eu_region,
)


@pytest.mark.parametrize(
    "region",
    ["eu-west-1", "eu-central-1", "europe-west1", "Frankfurt", "EU_WEST_3"],
)
def test_eu_regions_accepted(region):
    assert is_eu_region(region)


@pytest.mark.parametrize(
    "region",
    ["us-east-1", "ap-south-1", "sa-east-1", "", None, "europa-imaginaria"],
)
def test_non_eu_regions_rejected(region):
    assert not is_eu_region(region)


def test_assert_eu_region_passes_for_eu():
    s = Settings(deploy_region="eu-west-1", supabase_region="eu-central-1")
    assert_eu_region(s)  # no lanza


def test_assert_eu_region_fails_for_non_eu():
    s = Settings(deploy_region="us-east-1", supabase_region="eu-central-1")
    with pytest.raises(RegionNotEUError):
        assert_eu_region(s)


def test_secure_secrets_local_allows_defaults():
    # En local los defaults de desarrollo son aceptables: la app arranca como hasta ahora.
    # Se fijan explícitamente para no depender de un .env real presente en el entorno.
    s = Settings(app_env="local", jwt_secret=DEV_JWT_SECRET, geo_encryption_key=DEV_GEO_KEY)
    assert_secure_secrets(s)  # no lanza


def test_secure_secrets_production_rejects_default():
    # Valores por defecto explícitos: el test no debe depender del .env del entorno.
    s = Settings(app_env="production", jwt_secret=DEV_JWT_SECRET, geo_encryption_key=DEV_GEO_KEY)
    with pytest.raises(InsecureDefaultSecretError) as exc:
        assert_secure_secrets(s)
    # El mensaje nombra ambas variables que deben configurarse.
    assert "JWT_SECRET" in str(exc.value)
    assert "GEO_ENCRYPTION_KEY" in str(exc.value)


def test_secure_secrets_production_with_real_secrets_passes():
    s = Settings(
        app_env="production",
        jwt_secret="x" * 40,
        geo_encryption_key="y" * 40,
    )
    assert_secure_secrets(s)  # no lanza
