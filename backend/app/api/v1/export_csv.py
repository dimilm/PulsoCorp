import csv
import io
import json

from fastapi import APIRouter, Depends
from fastapi.responses import Response, StreamingResponse
from sqlalchemy.orm import Session

from app.api.deps import get_current_user
from app.db.session import get_db
from app.services.stock_service import build_seed_rows, list_stocks

router = APIRouter(prefix="/export", tags=["export"])


@router.get("/csv")
def export_csv(_: dict = Depends(get_current_user), db: Session = Depends(get_db)) -> StreamingResponse:
    stocks = list_stocks(db)
    output = io.StringIO()
    writer = csv.DictWriter(
        output,
        fieldnames=[
            "isin",
            "name",
            "sector",
            "currency",
            "burggraben",
            "tranches",
            "current_price",
            "day_change_pct",
            "invested_capital_eur",
        ],
    )
    writer.writeheader()
    for row in stocks:
        writer.writerow({k: row.get(k) for k in writer.fieldnames})
    output.seek(0)
    return StreamingResponse(iter([output.getvalue()]), media_type="text/csv")


@router.get("/seed-json")
def export_seed_json(_: dict = Depends(get_current_user), db: Session = Depends(get_db)) -> Response:
    rows = build_seed_rows(db)
    payload = json.dumps(rows, ensure_ascii=False, indent=2)
    return Response(
        content=payload,
        media_type="application/json",
        headers={"Content-Disposition": 'attachment; filename="stocks.seed.json"'},
    )
