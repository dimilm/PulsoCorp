"""Tests for the CSV export/import service and the HTTP endpoints."""
from __future__ import annotations

import io
from datetime import date, timedelta

import pytest
from fastapi.testclient import TestClient

from app.db.session import SessionLocal
from app.main import app
from app.models.job_source import JobSnapshot, JobSource


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _login(client: TestClient, *, username: str = "admin", password: str = "changeme") -> str:
    resp = client.post("/api/v1/auth/login", json={"username": username, "password": password})
    assert resp.status_code == 200, resp.text
    return resp.json()["csrf_token"]


def _make_source(db, *, name: str = "Test Corp", isin: str | None = None) -> JobSource:
    src = JobSource(
        name=name,
        portal_url="https://test.example.com/jobs",
        adapter_type="json_get_path_int",
        adapter_settings={"endpoint": "https://api.example.com/jobs", "value_path": "total"},
        is_active=True,
        isin=isin,
    )
    db.add(src)
    db.commit()
    db.refresh(src)
    return src


def _make_snapshot(db, source_id: int, snap_date: date, count: int) -> JobSnapshot:
    snap = JobSnapshot(
        job_source_id=source_id,
        snapshot_date=snap_date,
        jobs_count=count,
        raw_meta={},
    )
    db.add(snap)
    db.commit()
    return snap


def _csv_bytes(*rows: dict) -> bytes:
    """Build a minimal CSV from a list of dicts (header inferred from first row)."""
    buf = io.StringIO()
    fieldnames = list(rows[0].keys())
    import csv as _csv
    w = _csv.DictWriter(buf, fieldnames=fieldnames, lineterminator="\n")
    w.writeheader()
    for row in rows:
        w.writerow(row)
    return buf.getvalue().encode()


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture(autouse=True)
def _clean_jobs(monkeypatch):
    """Wipe job tables before each test."""
    db = SessionLocal()
    try:
        db.query(JobSnapshot).delete()
        db.query(JobSource).delete()
        db.commit()
    finally:
        db.close()
    yield


# ---------------------------------------------------------------------------
# Service-level tests (bypass HTTP)
# ---------------------------------------------------------------------------

class TestBuildHistoryCsv:
    def test_empty_db_returns_header_only(self):
        from app.services.job_history_io import build_history_csv

        db = SessionLocal()
        try:
            csv_text = build_history_csv(db)
        finally:
            db.close()

        lines = csv_text.strip().splitlines()
        assert len(lines) == 1
        assert "snapshot_date" in lines[0]
        assert "jobs_count" in lines[0]

    def test_rows_appear_sorted_by_name_then_date(self):
        from app.services.job_history_io import build_history_csv

        db = SessionLocal()
        try:
            src_b = _make_source(db, name="Beta Corp")
            src_a = _make_source(db, name="Alpha Corp")
            today = date.today()
            _make_snapshot(db, src_b.id, today, 5)
            _make_snapshot(db, src_a.id, today - timedelta(days=1), 10)
            _make_snapshot(db, src_a.id, today, 20)
            csv_text = build_history_csv(db)
        finally:
            db.close()

        import csv as _csv
        reader = list(_csv.DictReader(io.StringIO(csv_text)))
        names = [r["source_name"] for r in reader]
        assert names == ["Alpha Corp", "Alpha Corp", "Beta Corp"]
        # Alpha Corp: older date first
        alpha_dates = [r["snapshot_date"] for r in reader if r["source_name"] == "Alpha Corp"]
        assert alpha_dates == sorted(alpha_dates)


class TestImportHistoryCsv:
    def test_roundtrip_is_idempotent(self):
        """Export → import into same DB produces 0 new rows."""
        from app.services.job_history_io import build_history_csv, import_history_csv

        db = SessionLocal()
        try:
            src = _make_source(db, name="Loop Corp")
            today = date.today()
            _make_snapshot(db, src.id, today - timedelta(days=1), 100)
            _make_snapshot(db, src.id, today, 200)
            csv_bytes = build_history_csv(db).encode()
        finally:
            db.close()

        db = SessionLocal()
        try:
            report = import_history_csv(db, csv_bytes)
        finally:
            db.close()

        assert report.total_rows == 2
        assert report.inserted == 0
        assert report.skipped_existing == 2
        assert report.unmapped_rows == []
        assert report.malformed_rows == []

    def test_import_into_empty_db_inserts_all_rows(self):
        from app.services.job_history_io import build_history_csv, import_history_csv

        db = SessionLocal()
        try:
            src = _make_source(db, name="Fresh Corp")
            today = date.today()
            _make_snapshot(db, src.id, today, 42)
            csv_bytes = build_history_csv(db).encode()
            # remove the snapshot so the target DB is "empty" of snapshot data
            db.query(JobSnapshot).delete()
            db.commit()
        finally:
            db.close()

        db = SessionLocal()
        try:
            report = import_history_csv(db, csv_bytes)
            snap_count = db.query(JobSnapshot).count()
        finally:
            db.close()

        assert report.inserted == 1
        assert report.skipped_existing == 0
        assert snap_count == 1

    def test_skip_existing_does_not_overwrite(self):
        from app.services.job_history_io import import_history_csv

        db = SessionLocal()
        try:
            src = _make_source(db, name="Stable Corp")
            today = date.today()
            _make_snapshot(db, src.id, today, 999)
            content = _csv_bytes(
                {
                    "job_source_id": src.id,
                    "isin": "",
                    "source_name": "Stable Corp",
                    "snapshot_date": today.isoformat(),
                    "jobs_count": "1",  # different value — must NOT overwrite
                }
            )
            report = import_history_csv(db, content)
            snap = db.query(JobSnapshot).filter(JobSnapshot.job_source_id == src.id).first()
        finally:
            db.close()

        assert report.skipped_existing == 1
        assert report.inserted == 0
        assert snap.jobs_count == 999  # original value preserved

    def test_match_by_id(self):
        from app.services.job_history_io import import_history_csv

        db = SessionLocal()
        try:
            src = _make_source(db, name="ID Corp")
            today = date.today()
            content = _csv_bytes(
                {
                    "job_source_id": src.id,
                    "isin": "",
                    "source_name": "",
                    "snapshot_date": today.isoformat(),
                    "jobs_count": "7",
                }
            )
            report = import_history_csv(db, content)
        finally:
            db.close()

        assert report.inserted == 1
        assert report.unmapped_rows == []

    def test_match_by_name_fallback(self):
        from app.services.job_history_io import import_history_csv

        db = SessionLocal()
        try:
            src = _make_source(db, name="Name Corp")
            today = date.today()
            content = _csv_bytes(
                {
                    "job_source_id": "",
                    "isin": "",
                    "source_name": "Name Corp",  # case-insensitive
                    "snapshot_date": today.isoformat(),
                    "jobs_count": "3",
                }
            )
            report = import_history_csv(db, content)
        finally:
            db.close()

        assert report.inserted == 1

    def test_match_by_name_case_insensitive(self):
        from app.services.job_history_io import import_history_csv

        db = SessionLocal()
        try:
            src = _make_source(db, name="Mixed Case Corp")
            today = date.today()
            content = _csv_bytes(
                {
                    "job_source_id": "",
                    "isin": "",
                    "source_name": "MIXED CASE CORP",
                    "snapshot_date": today.isoformat(),
                    "jobs_count": "5",
                }
            )
            report = import_history_csv(db, content)
        finally:
            db.close()

        assert report.inserted == 1

    def test_match_by_isin_fallback(self):
        from app.services.job_history_io import import_history_csv

        db = SessionLocal()
        try:
            src = _make_source(db, name="ISIN Corp", isin="DE0099999999")
            today = date.today()
            content = _csv_bytes(
                {
                    "job_source_id": "",
                    "isin": "DE0099999999",
                    "source_name": "",
                    "snapshot_date": today.isoformat(),
                    "jobs_count": "99",
                }
            )
            report = import_history_csv(db, content)
        finally:
            db.close()

        assert report.inserted == 1

    def test_isin_ambiguous_reports_unmapped(self):
        """Two sources with the same ISIN → isin_ambiguous reason."""
        from app.services.job_history_io import import_history_csv

        db = SessionLocal()
        try:
            _make_source(db, name="VW Portal A", isin="DE0007664039")
            _make_source(db, name="VW Portal B", isin="DE0007664039")
            today = date.today()
            content = _csv_bytes(
                {
                    "job_source_id": "",
                    "isin": "DE0007664039",
                    "source_name": "",
                    "snapshot_date": today.isoformat(),
                    "jobs_count": "50",
                }
            )
            report = import_history_csv(db, content)
        finally:
            db.close()

        assert report.inserted == 0
        assert len(report.unmapped_rows) == 1
        assert "isin_ambiguous" in report.unmapped_rows[0].reason

    def test_no_matching_source_reports_unmapped(self):
        from app.services.job_history_io import import_history_csv

        db = SessionLocal()
        try:
            today = date.today()
            content = _csv_bytes(
                {
                    "job_source_id": "99999",
                    "isin": "",
                    "source_name": "",
                    "snapshot_date": today.isoformat(),
                    "jobs_count": "1",
                }
            )
            report = import_history_csv(db, content)
        finally:
            db.close()

        assert report.inserted == 0
        assert len(report.unmapped_rows) == 1

    def test_malformed_date_reported(self):
        from app.services.job_history_io import import_history_csv

        db = SessionLocal()
        try:
            src = _make_source(db, name="Bad Date Corp")
            content = _csv_bytes(
                {
                    "job_source_id": src.id,
                    "isin": "",
                    "source_name": "Bad Date Corp",
                    "snapshot_date": "not-a-date",
                    "jobs_count": "5",
                }
            )
            report = import_history_csv(db, content)
        finally:
            db.close()

        assert report.inserted == 0
        assert len(report.malformed_rows) == 1
        assert "snapshot_date" in report.malformed_rows[0].error

    def test_negative_count_reported(self):
        from app.services.job_history_io import import_history_csv

        db = SessionLocal()
        try:
            src = _make_source(db, name="Negative Corp")
            today = date.today()
            content = _csv_bytes(
                {
                    "job_source_id": src.id,
                    "isin": "",
                    "source_name": "Negative Corp",
                    "snapshot_date": today.isoformat(),
                    "jobs_count": "-1",
                }
            )
            report = import_history_csv(db, content)
        finally:
            db.close()

        assert report.inserted == 0
        assert len(report.malformed_rows) == 1

    def test_missing_count_reported(self):
        from app.services.job_history_io import import_history_csv

        db = SessionLocal()
        try:
            src = _make_source(db, name="Missing Count Corp")
            today = date.today()
            content = _csv_bytes(
                {
                    "job_source_id": src.id,
                    "isin": "",
                    "source_name": "Missing Count Corp",
                    "snapshot_date": today.isoformat(),
                    "jobs_count": "",
                }
            )
            report = import_history_csv(db, content)
        finally:
            db.close()

        assert report.inserted == 0
        assert len(report.malformed_rows) == 1

    def test_same_date_in_csv_twice_not_double_inserted(self):
        """Two rows for the same (source, date) in one CSV → only one inserted."""
        from app.services.job_history_io import import_history_csv

        db = SessionLocal()
        try:
            src = _make_source(db, name="Dedup Corp")
            today = date.today()
            csv_content = (
                "job_source_id,isin,source_name,snapshot_date,jobs_count\n"
                f"{src.id},,Dedup Corp,{today.isoformat()},10\n"
                f"{src.id},,Dedup Corp,{today.isoformat()},20\n"
            ).encode()
            report = import_history_csv(db, csv_content)
            count = db.query(JobSnapshot).filter(JobSnapshot.job_source_id == src.id).count()
        finally:
            db.close()

        assert count == 1
        assert report.inserted == 1
        assert report.skipped_existing == 1


# ---------------------------------------------------------------------------
# HTTP endpoint tests
# ---------------------------------------------------------------------------

class TestExportEndpoint:
    def test_returns_csv_attachment(self):
        client = TestClient(app)
        _login(client)

        db = SessionLocal()
        try:
            src = _make_source(db, name="HTTP Export Corp")
            _make_snapshot(db, src.id, date.today(), 55)
        finally:
            db.close()

        resp = client.get("/api/v1/job-sources/history/export-csv")
        assert resp.status_code == 200
        assert "text/csv" in resp.headers["content-type"]
        assert "job-history.csv" in resp.headers.get("content-disposition", "")
        assert "HTTP Export Corp" in resp.text
        assert "55" in resp.text

    def test_requires_auth(self):
        client = TestClient(app)
        # No login → no auth cookie
        resp = client.get("/api/v1/job-sources/history/export-csv")
        assert resp.status_code == 401


class TestImportEndpoint:
    def test_import_inserts_new_rows(self):
        client = TestClient(app)
        csrf = _login(client)

        db = SessionLocal()
        try:
            src = _make_source(db, name="HTTP Import Corp")
        finally:
            db.close()

        today = date.today()
        csv_bytes = _csv_bytes(
            {
                "job_source_id": src.id,
                "isin": "",
                "source_name": "HTTP Import Corp",
                "snapshot_date": today.isoformat(),
                "jobs_count": "77",
            }
        )
        resp = client.post(
            "/api/v1/job-sources/history/import-csv",
            headers={"X-CSRF-Token": csrf},
            files={"file": ("job-history.csv", csv_bytes, "text/csv")},
        )
        assert resp.status_code == 200
        body = resp.json()
        assert body["inserted"] == 1
        assert body["skipped_existing"] == 0

    def test_requires_admin_and_csrf(self):
        client = TestClient(app)
        # No login at all → 401
        resp = client.post(
            "/api/v1/job-sources/history/import-csv",
            files={"file": ("job-history.csv", b"a,b\n", "text/csv")},
        )
        assert resp.status_code in (401, 403)

    def test_csrf_required(self):
        client = TestClient(app)
        _login(client)
        # Auth cookie present but no CSRF header
        resp = client.post(
            "/api/v1/job-sources/history/import-csv",
            files={"file": ("job-history.csv", b"a,b\n", "text/csv")},
        )
        assert resp.status_code == 403
