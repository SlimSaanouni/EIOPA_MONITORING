import sqlite3

import pytest

from eiopa_rfr import db


class TestSchema:
    def test_init_schema_creates_expected_tables(self, test_db_path):
        conn = db.get_connection(test_db_path)
        tables = {
            row["name"]
            for row in conn.execute("SELECT name FROM sqlite_master WHERE type='table'").fetchall()
        }
        conn.close()
        assert {"curves", "curve_metadata", "ingestion_runs"} <= tables

    def test_init_schema_is_idempotent(self, test_db_path):
        # Ré-appliquer le schéma sur une base déjà initialisée ne doit pas lever d'erreur
        from eiopa_rfr.config import DB_SCHEMA_FILE
        db.init_schema(db_path=test_db_path, schema_file=DB_SCHEMA_FILE)

    def test_curves_rejects_invalid_va_type(self, conn):
        with pytest.raises(sqlite3.IntegrityError):
            conn.execute(
                "INSERT INTO curves VALUES ('2026-07-31', 'FR', 'BOGUS', 'BASE', 1, 0.02)"
            )

    def test_curves_rejects_maturity_out_of_range(self, conn):
        with pytest.raises(sqlite3.IntegrityError):
            conn.execute(
                "INSERT INTO curves VALUES ('2026-07-31', 'FR', 'NO_VA', 'BASE', 151, 0.02)"
            )


class TestUpsertCurveRows:
    def test_insert_then_read_back(self, conn):
        db.upsert_curve_rows(conn, [("2026-07-31", "FR", "NO_VA", "BASE", 10, 0.025)])
        conn.commit()
        assert db.get_rate(conn, "2026-07-31", "FR", "NO_VA", "BASE", 10) == pytest.approx(0.025)

    def test_upsert_on_conflict_updates_rate_not_duplicates(self, conn):
        db.upsert_curve_rows(conn, [("2026-07-31", "FR", "NO_VA", "BASE", 10, 0.025)])
        db.upsert_curve_rows(conn, [("2026-07-31", "FR", "NO_VA", "BASE", 10, 0.030)])
        conn.commit()

        count = conn.execute(
            "SELECT COUNT(*) AS n FROM curves WHERE reference_date='2026-07-31' AND maturity=10"
        ).fetchone()["n"]
        assert count == 1
        assert db.get_rate(conn, "2026-07-31", "FR", "NO_VA", "BASE", 10) == pytest.approx(0.030)

    def test_missing_maturity_returns_none(self, conn):
        db.upsert_curve_rows(conn, [("2026-07-31", "FR", "NO_VA", "BASE", 10, 0.025)])
        conn.commit()
        assert db.get_rate(conn, "2026-07-31", "FR", "NO_VA", "BASE", 99) is None

    def test_get_curve_returns_full_dict(self, conn):
        rows = [("2026-07-31", "FR", "NO_VA", "BASE", m, 0.01 * m) for m in (1, 5, 10)]
        db.upsert_curve_rows(conn, rows)
        conn.commit()
        curve = db.get_curve(conn, "2026-07-31", "FR", "NO_VA", "BASE")
        assert curve == {1: pytest.approx(0.01), 5: pytest.approx(0.05), 10: pytest.approx(0.10)}


class TestUpsertMetadata:
    def test_insert_then_read_back(self, conn):
        meta = {
            "reference_date": "2026-07-31", "country": "FR", "va_type": "WITH_VA",
            "coupon_freq": 1, "llp": 20, "convergence": 40, "ufr": 3.3,
            "alpha": 0.05, "cra": 10.0, "va": 0.0013,
        }
        db.upsert_metadata(conn, meta)
        conn.commit()
        result = db.get_metadata(conn, "2026-07-31", "FR", "WITH_VA")
        assert result["va"] == pytest.approx(0.0013)
        assert result["llp"] == 20

    def test_upsert_updates_existing_row(self, conn):
        base_meta = {
            "reference_date": "2026-07-31", "country": "FR", "va_type": "WITH_VA",
            "coupon_freq": 1, "llp": 20, "convergence": 40, "ufr": 3.3,
            "alpha": 0.05, "cra": 10.0, "va": 0.0013,
        }
        db.upsert_metadata(conn, base_meta)
        db.upsert_metadata(conn, {**base_meta, "va": 0.0020})
        conn.commit()

        count = conn.execute("SELECT COUNT(*) AS n FROM curve_metadata").fetchone()["n"]
        assert count == 1
        assert db.get_metadata(conn, "2026-07-31", "FR", "WITH_VA")["va"] == pytest.approx(0.0020)

    def test_missing_metadata_returns_none(self, conn):
        assert db.get_metadata(conn, "2026-07-31", "FR", "WITH_VA") is None


class TestGetDates:
    def test_returns_sorted_distinct_dates(self, conn):
        rows = [
            ("2026-06-30", "FR", "NO_VA", "BASE", 1, 0.02),
            ("2026-07-31", "FR", "NO_VA", "BASE", 1, 0.02),
            ("2026-07-31", "FR", "NO_VA", "UP", 1, 0.04),  # même date, autre curve_type
        ]
        db.upsert_curve_rows(conn, rows)
        conn.commit()
        assert db.get_dates(conn, "FR") == ["2026-06-30", "2026-07-31"]

    def test_filters_by_country(self, conn):
        db.upsert_curve_rows(conn, [("2026-07-31", "DE", "NO_VA", "BASE", 1, 0.02)])
        conn.commit()
        assert db.get_dates(conn, "FR") == []


class TestGetTimeSeries:
    def test_filters_by_date_range(self, conn):
        rows = [(d, "FR", "NO_VA", "BASE", 10, 0.02) for d in ("2026-01-31", "2026-06-30", "2026-07-31")]
        db.upsert_curve_rows(conn, rows)
        conn.commit()
        series = db.get_time_series(conn, "FR", 10, start_date="2026-06-01")
        assert [d for d, _ in series] == ["2026-06-30", "2026-07-31"]

    def test_sorted_ascending_by_date(self, conn):
        rows = [(d, "FR", "NO_VA", "BASE", 10, 0.02) for d in ("2026-07-31", "2026-01-31")]
        db.upsert_curve_rows(conn, rows)
        conn.commit()
        series = db.get_time_series(conn, "FR", 10)
        assert [d for d, _ in series] == ["2026-01-31", "2026-07-31"]


class TestIngestionRuns:
    def test_record_and_retrieve_issue(self, conn):
        db.record_ingestion_run(
            conn, reference_date="2026-07-31", country="FR", source_file="x.zip",
            status="PARTIAL", missing_maturities="NO_VA: maturité 5 manquante",
        )
        conn.commit()
        issues = db.get_ingestion_issues(conn, "FR")
        assert len(issues) == 1
        assert issues[0]["status"] == "PARTIAL"

    def test_success_runs_are_excluded(self, conn):
        db.record_ingestion_run(conn, reference_date="2026-07-31", country="FR", source_file="x.zip", status="SUCCESS")
        conn.commit()
        assert db.get_ingestion_issues(conn, "FR") == []

    def test_most_recent_first(self, conn):
        db.record_ingestion_run(conn, reference_date="2026-01-31", country="FR", source_file="a.zip", status="FAILED", notes="premier")
        conn.commit()
        db.record_ingestion_run(conn, reference_date="2026-07-31", country="FR", source_file="b.zip", status="PARTIAL", notes="second")
        conn.commit()
        issues = db.get_ingestion_issues(conn, "FR")
        assert [i["notes"] for i in issues] == ["second", "premier"]


class TestBackupDatabase:
    def test_no_backup_if_db_missing(self, tmp_path):
        assert db.backup_database(tmp_path / "does_not_exist.db") is None

    def test_creates_one_backup_per_day(self, tmp_path, monkeypatch, test_db_path):
        backup_dir = tmp_path / "backups"
        monkeypatch.setattr(db, "DB_BACKUP_DIR", backup_dir)

        first = db.backup_database(test_db_path, keep=5)
        second = db.backup_database(test_db_path, keep=5)

        assert first == second
        assert len(list(backup_dir.glob("*.db"))) == 1

    def test_retention_keeps_only_the_n_most_recent(self, tmp_path, monkeypatch, test_db_path):
        backup_dir = tmp_path / "backups"
        backup_dir.mkdir()
        monkeypatch.setattr(db, "DB_BACKUP_DIR", backup_dir)

        stem, suffix = test_db_path.stem, test_db_path.suffix
        # 4 anciens backups simulés (dates passées) + celui du jour créé par l'appel ci-dessous = 5 avant purge
        for d in ["20260101", "20260201", "20260301", "20260401"]:
            (backup_dir / f"{stem}_{d}_120000{suffix}").write_bytes(b"x")

        db.backup_database(test_db_path, keep=2)

        remaining = sorted(f.name for f in backup_dir.glob(f"{stem}_*{suffix}"))
        assert len(remaining) == 2
        # Les 2 conservés sont les 2 plus récents par tri du nom de fichier :
        # le backup du jour (créé par l'appel) et le plus récent des anciens (20260401)
        assert remaining[0].startswith(f"{stem}_20260401")
