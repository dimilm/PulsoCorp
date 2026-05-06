"""HTTP endpoints for the career-portal job-source feature."""
from __future__ import annotations

from fastapi import APIRouter, Depends, File, HTTPException, Query, UploadFile
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session

from app.api.deps import csrf_guard, get_current_user, require_admin
from app.db.session import get_db
from app.models.job_source import JobSource
from app.schemas.job_source import (
    JobsAggregateTrendsOut,
    JobSnapshotOut,
    JobSourceCreate,
    JobSourceOut,
    JobSourceTestResult,
    JobSourceTrendOut,
    JobSourceUpdate,
)
from app.services import job_history_io, jobs_service, jobs_trend_service
from app.services.job_history_io import ImportReport

router = APIRouter(prefix="/job-sources", tags=["job-sources"])


def _to_out(db: Session, source: JobSource) -> dict:
    """Project a `JobSource` ORM row onto the API shape with derived fields."""
    summary = jobs_trend_service.summary_for_source(db, source.id)
    return {
        "id": source.id,
        "isin": source.isin,
        "name": source.name,
        "portal_url": source.portal_url,
        "adapter_type": source.adapter_type,
        "adapter_settings": source.adapter_settings or {},
        "is_active": source.is_active,
        "created_at": source.created_at,
        "updated_at": source.updated_at,
        **summary,
    }


@router.get("", response_model=list[JobSourceOut])
def list_job_sources(
    isin: str | None = Query(default=None),
    is_active: bool | None = Query(default=None),
    _: dict = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> list[dict]:
    query = db.query(JobSource)
    if isin:
        query = query.filter(JobSource.isin == isin.upper())
    if is_active is not None:
        query = query.filter(JobSource.is_active.is_(is_active))
    sources = query.order_by(JobSource.name.asc()).all()
    return [_to_out(db, s) for s in sources]


@router.get("/trends", response_model=JobsAggregateTrendsOut)
def aggregate_trends(
    days: int = Query(default=90, ge=1, le=3650),
    _: dict = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> dict:
    """Per-ISIN, per-day summed `jobs_count` over the last ``days``.

    Powers the watchlist sparkline column: returns one timeseries per ISIN
    that has at least one snapshot in the window, summed across that
    ISIN's active sources. Mounted **before** the `/{source_id}` routes so
    FastAPI does not try to parse the literal string ``trends`` as an int.
    """
    aggregated = jobs_trend_service.aggregated_trends_by_isin(db, days=days)
    items = [
        {
            "isin": isin,
            "points": [
                {"snapshot_date": snap_date, "jobs_count": count}
                for snap_date, count in points
            ],
        }
        for isin, points in aggregated.items()
    ]
    return {"days": days, "items": items}


@router.get("/history/export-csv")
def export_history_csv(
    _: dict = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> StreamingResponse:
    """Download all JobSnapshot rows for every source as a single CSV file.

    Mounted before ``/{source_id}`` so FastAPI does not try to parse the
    literal string ``history`` as an int.
    """
    csv_text = job_history_io.build_history_csv(db)
    return StreamingResponse(
        iter([csv_text]),
        media_type="text/csv",
        headers={"Content-Disposition": 'attachment; filename="job-history.csv"'},
    )


@router.post(
    "/history/import-csv",
    response_model=ImportReport,
    dependencies=[Depends(csrf_guard)],
)
async def import_history_csv(
    file: UploadFile = File(...),
    _: dict = Depends(require_admin),
    db: Session = Depends(get_db),
) -> ImportReport:
    """Upload a CSV and insert missing JobSnapshot rows (skip existing).

    Accepts the same format that ``/history/export-csv`` produces so a
    round-trip export→edit→import is the primary workflow.  Rows that
    cannot be matched to an existing JobSource are listed in
    ``unmapped_rows``; validation errors are listed in ``malformed_rows``.
    """
    content = await file.read()
    return job_history_io.import_history_csv(db, content)


@router.post("", response_model=JobSourceOut, dependencies=[Depends(csrf_guard)])
def create_job_source(
    payload: JobSourceCreate,
    _: dict = Depends(require_admin),
    db: Session = Depends(get_db),
) -> dict:
    source = JobSource(
        isin=payload.isin,
        name=payload.name,
        portal_url=payload.portal_url,
        adapter_type=payload.adapter_type,
        adapter_settings=payload.adapter_settings,
        is_active=payload.is_active,
    )
    db.add(source)
    db.commit()
    db.refresh(source)
    return _to_out(db, source)


@router.get("/{source_id}", response_model=JobSourceOut)
def get_job_source(
    source_id: int,
    _: dict = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> dict:
    source = db.get(JobSource, source_id)
    if not source:
        raise HTTPException(status_code=404, detail="Job source not found")
    return _to_out(db, source)


@router.patch(
    "/{source_id}",
    response_model=JobSourceOut,
    dependencies=[Depends(csrf_guard)],
)
def update_job_source(
    source_id: int,
    payload: JobSourceUpdate,
    _: dict = Depends(require_admin),
    db: Session = Depends(get_db),
) -> dict:
    source = db.get(JobSource, source_id)
    if not source:
        raise HTTPException(status_code=404, detail="Job source not found")
    data = payload.model_dump(exclude_unset=True)
    for field, value in data.items():
        setattr(source, field, value)
    db.add(source)
    db.commit()
    db.refresh(source)
    return _to_out(db, source)


@router.delete("/{source_id}", dependencies=[Depends(csrf_guard)])
def delete_job_source(
    source_id: int,
    _: dict = Depends(require_admin),
    db: Session = Depends(get_db),
) -> dict:
    source = db.get(JobSource, source_id)
    if not source:
        raise HTTPException(status_code=404, detail="Job source not found")
    db.delete(source)
    db.commit()
    return {"ok": True}


@router.post(
    "/{source_id}/test",
    response_model=JobSourceTestResult,
    dependencies=[Depends(csrf_guard)],
)
async def test_job_source(
    source_id: int,
    _: dict = Depends(require_admin),
    db: Session = Depends(get_db),
) -> dict:
    """Adapter dry-run; does not touch ``job_snapshots`` or ``run_logs``.

    Used by the source-edit form to preview what a scrape would yield with
    the current configuration. The result mirrors the shape that the cron
    pipeline would record so the UI renders the same status pills.
    """
    source = db.get(JobSource, source_id)
    if not source:
        raise HTTPException(status_code=404, detail="Job source not found")
    return await jobs_service.test_source_scrape(source)


@router.get("/{source_id}/trend", response_model=JobSourceTrendOut)
def trend(
    source_id: int,
    days: int = Query(default=30, ge=1, le=3650),
    _: dict = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> dict:
    if not db.get(JobSource, source_id):
        raise HTTPException(status_code=404, detail="Job source not found")
    points = jobs_trend_service.trend_for_source(db, source_id, days=days)
    return {
        "source_id": source_id,
        "days": days,
        "points": [JobSnapshotOut.model_validate(p) for p in points],
    }


@router.post(
    "/{source_id}/refresh",
    dependencies=[Depends(csrf_guard)],
)
def refresh_single_source(
    source_id: int,
    _: dict = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> dict:
    """Kick off a one-off scrape for a single source on the worker thread."""
    if not db.get(JobSource, source_id):
        raise HTTPException(status_code=404, detail="Job source not found")
    return jobs_service.start_single_jobs_refresh_background(source_id)
