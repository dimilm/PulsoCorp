import csv
import io

from fastapi import APIRouter, Depends
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session

from app.api.deps import get_current_user
from app.db.session import get_db
from app.services.stock_service import list_stocks

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
            "recommendation",
            "invested_capital_eur",
        ],
    )
    writer.writeheader()
    for row in stocks:
        writer.writerow({k: row.get(k) for k in writer.fieldnames})
    output.seek(0)
    return StreamingResponse(iter([output.getvalue()]), media_type="text/csv")
