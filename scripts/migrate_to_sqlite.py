"""
Migration ponctuelle : reconstruit historical.db à partir des artefacts déjà
sur disque, sans re-télécharger ni re-traiter les fichiers EIOPA.

Sources :
  - data/processed/RFR_[DATE]_{NO_VA,WITH_VA}.csv  -> table curves (0-150, Base/Up/Down)
  - data/extracts/EIOPA_RFR_[DATE]_Term_Structures.xlsx -> table curve_metadata
  - data/raw/EIOPA_RFR_[DATE].zip (si présent)     -> source_file de ingestion_runs

Ne touche jamais data/historical.csv : un fichier de contrôle
data/historical_from_db.csv est généré à côté pour comparaison manuelle,
en plus du rapport de cohérence affiché en console.

Usage:
    python scripts/migrate_to_sqlite.py
"""
import csv
import re
import sys
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).parent.parent))

from config import (
    DATA_DIR, EXTRACTS_DIR, PROCESSED_DIR, RAW_DIR,
    HISTORICAL_FILE, HISTORICAL_DB, TARGET_COUNTRY, TARGET_MATURITIES,
    BPS_CONVERSION,
)
from src import db
from src.utils import setup_logging, parse_date_from_filename

logger = setup_logging()

CURVE_TYPE_COLUMNS = {
    "Base": "BASE",
    "IR Upward Shock": "UP",
    "IR Downward shock": "DOWN",
}

METADATA_ROWS = ["Coupon_freq", "LLP", "Convergence", "UFR", "alpha", "CRA", "VA"]

COUNTRY_ALIASES = {
    "FR": ["france", "french", "fr"],
    "DE": ["germany", "german", "de"],
    "IT": ["italy", "italian", "it"],
    "ES": ["spain", "spanish", "es"],
    "EUR": ["euro", "eur", "eurozone"],
    "GB": ["united kingdom", "uk", "gb", "gbp"],
    "US": ["united states", "usa", "us", "usd"],
}


def find_country_column(columns, country_code: str):
    targets = COUNTRY_ALIASES.get(country_code.upper(), [country_code.lower()])
    for col in columns:
        if any(alias in str(col).lower() for alias in targets):
            return col
    return None


# ---------------------------------------------------------------------------
# Étape 1 : curves depuis data/processed/
# ---------------------------------------------------------------------------

def migrate_curves(conn) -> int:
    total_rows = 0
    files = sorted(PROCESSED_DIR.glob("RFR_*_NO_VA.csv")) + sorted(PROCESSED_DIR.glob("RFR_*_WITH_VA.csv"))
    logger.info(f"[curves] {len(files)} fichiers à ingérer depuis {PROCESSED_DIR}")

    for path in files:
        match = re.match(r"RFR_(\d{8})_(NO_VA|WITH_VA)\.csv", path.name)
        if not match:
            logger.warning(f"[curves] Nom de fichier inattendu, ignoré : {path.name}")
            continue
        date_str, va_type = match.groups()
        reference_date = f"{date_str[:4]}-{date_str[4:6]}-{date_str[6:]}"

        df = pd.read_csv(path)
        df.columns = [c.strip() for c in df.columns]

        rows = []
        for _, record in df.iterrows():
            maturity = int(record["Maturity"])
            for col_name, curve_type in CURVE_TYPE_COLUMNS.items():
                rows.append((
                    reference_date, TARGET_COUNTRY, va_type, curve_type,
                    maturity, float(record[col_name]),
                ))

        db.upsert_curve_rows(conn, rows)
        total_rows += len(rows)

    logger.info(f"[curves] {total_rows} lignes insérées.")
    return total_rows


# ---------------------------------------------------------------------------
# Étape 2 : curve_metadata depuis data/extracts/
# ---------------------------------------------------------------------------

def _read_metadata_block(excel_path: Path, sheet_name: str, country_code: str):
    """Lit les 7 lignes de métadonnées (Coupon_freq..VA) pour un pays donné."""
    df = pd.read_excel(excel_path, sheet_name=sheet_name, engine="openpyxl", header=1, index_col=1)
    country_col = find_country_column(df.columns, country_code)
    if country_col is None:
        logger.warning(f"[metadata] Colonne pays introuvable dans {excel_path.name} / {sheet_name}")
        return None

    values = {}
    for label in METADATA_ROWS:
        if label in df.index:
            values[label] = df.loc[label, country_col]
        else:
            values[label] = None
    return values


def migrate_metadata(conn) -> int:
    files = sorted(EXTRACTS_DIR.glob("EIOPA_RFR_*_Term_Structures.xlsx"))
    logger.info(f"[metadata] {len(files)} fichiers Excel à relire depuis {EXTRACTS_DIR}")

    total = 0
    for path in files:
        reference_date_dt = parse_date_from_filename(path.name)
        if not reference_date_dt:
            logger.warning(f"[metadata] Date illisible, ignoré : {path.name}")
            continue
        reference_date = reference_date_dt.strftime("%Y-%m-%d")

        for sheet_name, va_type in [("RFR_spot_no_VA", "NO_VA"), ("RFR_spot_with_VA", "WITH_VA")]:
            block = _read_metadata_block(path, sheet_name, TARGET_COUNTRY)
            if block is None:
                continue

            va_raw = block["VA"]
            va_decimal = (float(va_raw) / BPS_CONVERSION) if pd.notna(va_raw) else None

            meta = {
                "reference_date": reference_date,
                "country": TARGET_COUNTRY,
                "va_type": va_type,
                "coupon_freq": int(block["Coupon_freq"]) if pd.notna(block["Coupon_freq"]) else None,
                "llp": int(block["LLP"]) if pd.notna(block["LLP"]) else None,
                "convergence": int(block["Convergence"]) if pd.notna(block["Convergence"]) else None,
                "ufr": float(block["UFR"]) if pd.notna(block["UFR"]) else None,
                "alpha": float(block["alpha"]) if pd.notna(block["alpha"]) else None,
                "cra": float(block["CRA"]) if pd.notna(block["CRA"]) else None,
                "va": va_decimal,
            }
            db.upsert_metadata(conn, meta)
            total += 1

    logger.info(f"[metadata] {total} lignes insérées.")
    return total


# ---------------------------------------------------------------------------
# Étape 3 : ingestion_runs
# ---------------------------------------------------------------------------

def migrate_ingestion_runs(conn) -> int:
    files = sorted(EXTRACTS_DIR.glob("EIOPA_RFR_*_Term_Structures.xlsx"))
    total = 0
    for path in files:
        reference_date_dt = parse_date_from_filename(path.name)
        if not reference_date_dt:
            continue
        reference_date = reference_date_dt.strftime("%Y-%m-%d")
        date_str = reference_date_dt.strftime("%Y%m%d")

        raw_zip = RAW_DIR / f"EIOPA_RFR_{date_str}.zip"
        source_file = raw_zip.name if raw_zip.exists() else path.name

        db.record_ingestion_run(
            conn,
            reference_date=reference_date,
            country=TARGET_COUNTRY,
            source_file=source_file,
            status="SUCCESS",
            notes="Migré depuis l'ancien pipeline CSV (scripts/migrate_to_sqlite.py)",
        )
        total += 1
    logger.info(f"[ingestion_runs] {total} lignes insérées.")
    return total


# ---------------------------------------------------------------------------
# Étape 4 : contrôle de cohérence vs historical.csv
# ---------------------------------------------------------------------------

def consistency_check(conn) -> bool:
    if not HISTORICAL_FILE.exists():
        logger.warning("[check] data/historical.csv introuvable, contrôle sauté.")
        return True

    legacy = pd.read_csv(HISTORICAL_FILE, parse_dates=["reference_date"])
    legacy = legacy[legacy["country"] == TARGET_COUNTRY]

    mismatches = []
    checked = 0
    for _, row in legacy.iterrows():
        reference_date = row["reference_date"].strftime("%Y-%m-%d")
        for maturity in TARGET_MATURITIES:
            legacy_rate = row.get(f"rate_{maturity}y")
            if pd.isna(legacy_rate):
                continue
            db_rate = db.get_rate(conn, reference_date, TARGET_COUNTRY, "NO_VA", "BASE", maturity)
            checked += 1
            if db_rate is None:
                mismatches.append((reference_date, maturity, legacy_rate, None))
            elif abs(db_rate - legacy_rate) > 1e-5:
                mismatches.append((reference_date, maturity, legacy_rate, db_rate))

    print(f"\n{'=' * 70}\nCONTRÔLE DE COHÉRENCE — historical.csv vs curves (BASE, NO_VA)\n{'=' * 70}")
    print(f"Points comparés : {checked}")
    if mismatches:
        print(f"❌ {len(mismatches)} écart(s) détecté(s) :")
        for date, maturity, legacy_rate, db_rate in mismatches[:20]:
            print(f"   {date} — {maturity}Y : historical.csv={legacy_rate!r}  db={db_rate!r}")
        if len(mismatches) > 20:
            print(f"   ... et {len(mismatches) - 20} de plus.")
    else:
        print("✅ Aucun écart — migration validée à 1e-5 près.")
    print(f"{'=' * 70}\n")

    return not mismatches


# ---------------------------------------------------------------------------
# Étape 5 : export de contrôle (ne remplace pas historical.csv)
# ---------------------------------------------------------------------------

def export_control_csv(conn) -> Path:
    output_path = DATA_DIR / "historical_from_db.csv"
    dates = db.get_dates(conn, TARGET_COUNTRY)

    fieldnames = ["reference_date", "country"] + [f"rate_{m}y" for m in TARGET_MATURITIES] + ["va"]
    with open(output_path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        for reference_date in dates:
            row = {"reference_date": reference_date, "country": TARGET_COUNTRY}
            for maturity in TARGET_MATURITIES:
                row[f"rate_{maturity}y"] = db.get_rate(conn, reference_date, TARGET_COUNTRY, "NO_VA", "BASE", maturity)
            meta = db.get_metadata(conn, reference_date, TARGET_COUNTRY, "WITH_VA")
            row["va"] = meta["va"] if meta else None
            writer.writerow(row)

    logger.info(f"[export] Fichier de contrôle écrit : {output_path}")
    return output_path


def main():
    if HISTORICAL_DB.exists():
        print(f"⚠️  {HISTORICAL_DB} existe déjà.")
        answer = input("Réinitialiser et re-migrer depuis zéro ? [y/N] ").strip().lower()
        if answer != "y":
            print("Abandon.")
            return
        db.backup_database(HISTORICAL_DB)
        HISTORICAL_DB.unlink()

    db.init_schema()

    with db.session() as conn:
        migrate_curves(conn)
        migrate_metadata(conn)
        migrate_ingestion_runs(conn)

    conn = db.get_connection()
    try:
        ok = consistency_check(conn)
        export_control_csv(conn)
    finally:
        conn.close()

    if not ok:
        print("❌ Migration terminée avec des écarts — vérifier le rapport ci-dessus avant de continuer.")
        sys.exit(1)
    print("✅ Migration terminée et validée.")


if __name__ == "__main__":
    main()
