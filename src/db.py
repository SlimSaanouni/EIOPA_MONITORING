"""
Accès à la base de courbes EIOPA (SQLite).

Remplace historical.csv comme source de vérité : écritures transactionnelles
(une ingestion = un COMMIT ou rien), schéma contraint (CHECK sur va_type /
curve_type / maturity), et backup horodaté avant toute session d'écriture.
"""
import shutil
import sqlite3
from contextlib import contextmanager
from datetime import datetime
from pathlib import Path
from typing import Dict, Iterable, List, Optional, Tuple

from config import DB_BACKUP_DIR, DB_BACKUP_KEEP, DB_SCHEMA_FILE, HISTORICAL_DB
from src.utils import setup_logging

logger = setup_logging()


def get_connection(db_path: Path = HISTORICAL_DB) -> sqlite3.Connection:
    """Ouvre une connexion avec row_factory dict-like et clés étrangères actives."""
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


def init_schema(db_path: Path = HISTORICAL_DB, schema_file: Path = DB_SCHEMA_FILE) -> None:
    """Crée les tables si elles n'existent pas (idempotent)."""
    with open(schema_file, "r", encoding="utf-8") as f:
        schema_sql = f.read()
    conn = get_connection(db_path)
    try:
        conn.executescript(schema_sql)
        conn.commit()
        logger.info(f"Schéma initialisé : {db_path}")
    finally:
        conn.close()


def backup_database(db_path: Path = HISTORICAL_DB, keep: int = DB_BACKUP_KEEP) -> Optional[Path]:
    """
    Copie la base vers DB_BACKUP_DIR avec un horodatage, puis supprime les
    plus anciens backups au-delà de `keep`. Ne fait rien si la base n'existe
    pas encore (première initialisation), ni si un backup du jour existe déjà
    — une session d'écriture copie l'intégralité du fichier (plusieurs Mo),
    inutile de le refaire à chaque ingestion répétée dans la même journée ;
    `keep` couvre alors `keep` jours distincts plutôt que `keep` écritures.
    """
    if not db_path.exists():
        return None

    DB_BACKUP_DIR.mkdir(parents=True, exist_ok=True)
    today = datetime.now().strftime("%Y%m%d")
    todays_backups = list(DB_BACKUP_DIR.glob(f"{db_path.stem}_{today}_*{db_path.suffix}"))
    if todays_backups:
        logger.debug(f"Backup du jour déjà présent, ignoré : {todays_backups[0]}")
        return todays_backups[0]

    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    backup_path = DB_BACKUP_DIR / f"{db_path.stem}_{timestamp}{db_path.suffix}"
    shutil.copy2(db_path, backup_path)
    logger.info(f"Backup créé : {backup_path}")

    backups = sorted(DB_BACKUP_DIR.glob(f"{db_path.stem}_*{db_path.suffix}"))
    for old_backup in backups[:-keep]:
        old_backup.unlink()
        logger.debug(f"Backup obsolète supprimé : {old_backup}")

    return backup_path


@contextmanager
def session(db_path: Path = HISTORICAL_DB):
    """
    Contexte transactionnel : COMMIT si le bloc réussit, ROLLBACK sinon.
    Sauvegarde la base avant d'ouvrir la session d'écriture.

    Usage:
        with db.session() as conn:
            db.upsert_curve_rows(conn, rows)
            db.upsert_metadata(conn, meta)
    """
    backup_database(db_path)
    conn = get_connection(db_path)
    try:
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        logger.error("Session DB annulée (rollback) suite à une erreur.", exc_info=True)
        raise
    finally:
        conn.close()


# ---------------------------------------------------------------------------
# Écriture
# ---------------------------------------------------------------------------

def upsert_curve_rows(conn: sqlite3.Connection, rows: Iterable[Tuple]) -> int:
    """
    Insère/remplace des lignes de courbe.

    rows: itérable de tuples (reference_date, country, va_type, curve_type, maturity, rate)
    """
    rows = list(rows)
    conn.executemany(
        """
        INSERT INTO curves (reference_date, country, va_type, curve_type, maturity, rate)
        VALUES (?, ?, ?, ?, ?, ?)
        ON CONFLICT (reference_date, country, va_type, curve_type, maturity)
        DO UPDATE SET rate = excluded.rate
        """,
        rows,
    )
    return len(rows)


def upsert_metadata(conn: sqlite3.Connection, meta: Dict) -> None:
    """
    Insère/remplace une ligne de métadonnées.

    meta: dict avec les clés reference_date, country, va_type, coupon_freq,
          llp, convergence, ufr, alpha, cra, va
    """
    conn.execute(
        """
        INSERT INTO curve_metadata
            (reference_date, country, va_type, coupon_freq, llp, convergence, ufr, alpha, cra, va)
        VALUES
            (:reference_date, :country, :va_type, :coupon_freq, :llp, :convergence, :ufr, :alpha, :cra, :va)
        ON CONFLICT (reference_date, country, va_type)
        DO UPDATE SET
            coupon_freq = excluded.coupon_freq,
            llp         = excluded.llp,
            convergence = excluded.convergence,
            ufr         = excluded.ufr,
            alpha       = excluded.alpha,
            cra         = excluded.cra,
            va          = excluded.va
        """,
        meta,
    )


def record_ingestion_run(
    conn: sqlite3.Connection,
    reference_date: str,
    country: str,
    source_file: str,
    status: str,
    missing_maturities: Optional[str] = None,
    notes: Optional[str] = None,
) -> None:
    conn.execute(
        """
        INSERT INTO ingestion_runs
            (reference_date, country, source_file, ingested_at, status, missing_maturities, notes)
        VALUES (?, ?, ?, ?, ?, ?, ?)
        """,
        (
            reference_date, country, source_file,
            datetime.now().isoformat(timespec="seconds"),
            status, missing_maturities, notes,
        ),
    )


# ---------------------------------------------------------------------------
# Lecture
# ---------------------------------------------------------------------------

def get_rate(
    conn: sqlite3.Connection,
    reference_date: str,
    country: str,
    va_type: str,
    curve_type: str,
    maturity: int,
) -> Optional[float]:
    row = conn.execute(
        """
        SELECT rate FROM curves
        WHERE reference_date = ? AND country = ? AND va_type = ? AND curve_type = ? AND maturity = ?
        """,
        (reference_date, country, va_type, curve_type, maturity),
    ).fetchone()
    return row["rate"] if row else None


def get_curve(
    conn: sqlite3.Connection,
    reference_date: str,
    country: str,
    va_type: str,
    curve_type: str = "BASE",
) -> Dict[int, float]:
    """Retourne la courbe complète {maturité: taux} pour une date/pays/va_type/curve_type."""
    rows = conn.execute(
        """
        SELECT maturity, rate FROM curves
        WHERE reference_date = ? AND country = ? AND va_type = ? AND curve_type = ?
        ORDER BY maturity
        """,
        (reference_date, country, va_type, curve_type),
    ).fetchall()
    return {row["maturity"]: row["rate"] for row in rows}


def get_metadata(
    conn: sqlite3.Connection, reference_date: str, country: str, va_type: str
) -> Optional[Dict]:
    row = conn.execute(
        """
        SELECT * FROM curve_metadata
        WHERE reference_date = ? AND country = ? AND va_type = ?
        """,
        (reference_date, country, va_type),
    ).fetchone()
    return dict(row) if row else None


def get_dates(conn: sqlite3.Connection, country: str) -> List[str]:
    """Liste triée des dates de référence disponibles pour un pays."""
    rows = conn.execute(
        "SELECT DISTINCT reference_date FROM curves WHERE country = ? ORDER BY reference_date",
        (country,),
    ).fetchall()
    return [row["reference_date"] for row in rows]


def get_ingestion_issues(conn: sqlite3.Connection, country: str, limit: int = 20) -> List[Dict]:
    """Runs d'ingestion non-SUCCESS (PARTIAL/FAILED), les plus récents d'abord."""
    rows = conn.execute(
        """
        SELECT reference_date, source_file, ingested_at, status, missing_maturities, notes
        FROM ingestion_runs
        WHERE country = ? AND status != 'SUCCESS'
        ORDER BY ingested_at DESC, id DESC
        LIMIT ?
        """,
        (country, limit),
    ).fetchall()
    return [dict(row) for row in rows]


def get_time_series(
    conn: sqlite3.Connection,
    country: str,
    maturity: int,
    va_type: str = "NO_VA",
    curve_type: str = "BASE",
    start_date: Optional[str] = None,
    end_date: Optional[str] = None,
) -> List[Tuple[str, float]]:
    """Série temporelle [(reference_date, rate), ...] triée par date pour une maturité donnée."""
    query = """
        SELECT reference_date, rate FROM curves
        WHERE country = ? AND va_type = ? AND curve_type = ? AND maturity = ?
    """
    params: list = [country, va_type, curve_type, maturity]
    if start_date:
        query += " AND reference_date >= ?"
        params.append(start_date)
    if end_date:
        query += " AND reference_date <= ?"
        params.append(end_date)
    query += " ORDER BY reference_date"

    rows = conn.execute(query, params).fetchall()
    return [(row["reference_date"], row["rate"]) for row in rows]
