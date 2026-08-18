-- Schéma de la base de courbes EIOPA (historical.db)
--
-- curves          : une ligne par (date, pays, va_type, curve_type, maturité).
--                    Remplace à la fois l'extraction 5-maturités historique
--                    (processor.py) et l'extraction 0-150 (rfr_exporter.py) :
--                    un seul chemin d'extraction pour tous les usages.
-- curve_metadata  : paramètres scalaires de construction de la courbe,
--                    rattachés à (date, pays, va_type) — alpha et va varient
--                    selon va_type, les autres non, mais on les stocke ainsi
--                    pour rester homogène et ne rien supposer.
-- ingestion_runs  : trace d'audit de chaque ingestion (succès/partiel/échec),
--                    remplace les warnings silencieux de l'ancien pipeline.

PRAGMA journal_mode = WAL;
PRAGMA foreign_keys = ON;

CREATE TABLE IF NOT EXISTS curves (
    reference_date TEXT    NOT NULL,               -- 'YYYY-MM-DD'
    country        TEXT    NOT NULL,
    va_type        TEXT    NOT NULL CHECK (va_type IN ('NO_VA', 'WITH_VA')),
    curve_type     TEXT    NOT NULL CHECK (curve_type IN ('BASE', 'UP', 'DOWN')),
    maturity       INTEGER NOT NULL CHECK (maturity BETWEEN 0 AND 150),
    rate           REAL    NOT NULL,
    PRIMARY KEY (reference_date, country, va_type, curve_type, maturity)
);

-- Requêtes "série temporelle d'une maturité" (dashboard, M/M, YTD)
CREATE INDEX IF NOT EXISTS idx_curves_series
    ON curves (country, va_type, curve_type, maturity, reference_date);

CREATE TABLE IF NOT EXISTS curve_metadata (
    reference_date TEXT    NOT NULL,
    country        TEXT    NOT NULL,
    va_type        TEXT    NOT NULL CHECK (va_type IN ('NO_VA', 'WITH_VA')),
    coupon_freq    INTEGER,
    llp            INTEGER,
    convergence    INTEGER,
    ufr            REAL,      -- en %, ex. 3.3
    alpha          REAL,      -- paramètre Smith-Wilson, diffère selon va_type
    cra            REAL,      -- Credit Risk Adjustment, en bps
    va             REAL,      -- Volatility Adjustment, en décimal (converti depuis bps à l'ingestion), NULL si NO_VA
    PRIMARY KEY (reference_date, country, va_type)
);

CREATE TABLE IF NOT EXISTS ingestion_runs (
    id                 INTEGER PRIMARY KEY AUTOINCREMENT,
    reference_date     TEXT    NOT NULL,
    country            TEXT    NOT NULL,
    source_file        TEXT    NOT NULL,
    ingested_at        TEXT    NOT NULL,           -- timestamp ISO
    status             TEXT    NOT NULL CHECK (status IN ('SUCCESS', 'PARTIAL', 'FAILED')),
    missing_maturities TEXT,                        -- JSON liste, si extraction partielle
    notes              TEXT
);

CREATE INDEX IF NOT EXISTS idx_ingestion_runs_date
    ON ingestion_runs (reference_date, country);
