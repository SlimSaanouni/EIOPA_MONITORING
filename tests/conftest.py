from pathlib import Path

import pytest

# eiopa_rfr doit être installé (pip install -e ".[dev]") pour être importable
# ici — pas de bidouille sys.path, cohérent avec le layout src/ du paquet.
from eiopa_rfr.config import DB_SCHEMA_FILE
from eiopa_rfr import db as db_module


@pytest.fixture
def test_db_path(tmp_path) -> Path:
    """Chemin vers une base SQLite neuve et initialisée, isolée dans tmp_path."""
    path = tmp_path / "test_historical.db"
    db_module.init_schema(db_path=path, schema_file=DB_SCHEMA_FILE)
    return path


@pytest.fixture
def conn(test_db_path):
    """Connexion ouverte sur la base de test — commit manuel dans les tests, fermée après."""
    connection = db_module.get_connection(test_db_path)
    yield connection
    connection.close()


def seed_curve(conn, reference_date, country="FR", va_type="NO_VA", curve_type="BASE", rates=None):
    """Insère une courbe minimale (par défaut seulement les maturités passées dans `rates`)."""
    rates = rates or {}
    rows = [
        (reference_date, country, va_type, curve_type, maturity, rate)
        for maturity, rate in rates.items()
    ]
    db_module.upsert_curve_rows(conn, rows)
    conn.commit()


def seed_full_curve(conn, reference_date, country="FR", va_type="NO_VA", base=0.02, up=0.04, down=0.01):
    """Insère une courbe complète 0-150 à taux plat, pour les 3 curve_type."""
    rows = []
    for maturity in range(151):
        rows.append((reference_date, country, va_type, "BASE", maturity, base))
        rows.append((reference_date, country, va_type, "UP", maturity, up))
        rows.append((reference_date, country, va_type, "DOWN", maturity, down))
    db_module.upsert_curve_rows(conn, rows)
    conn.commit()


def seed_metadata(conn, reference_date, country="FR", va_type="WITH_VA", va=0.0014, **overrides):
    meta = {
        "reference_date": reference_date,
        "country": country,
        "va_type": va_type,
        "coupon_freq": 1,
        "llp": 20,
        "convergence": 40,
        "ufr": 3.3,
        "alpha": 0.05,
        "cra": 10.0,
        "va": va,
    }
    meta.update(overrides)
    db_module.upsert_metadata(conn, meta)
    conn.commit()
