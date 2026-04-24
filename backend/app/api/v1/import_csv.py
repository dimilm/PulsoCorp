from fastapi import APIRouter, Depends, File, UploadFile
from sqlalchemy.orm import Session

from app.api.deps import csrf_guard, require_admin
from app.db.session import get_db
from app.services.stock_service import parse_csv_and_upsert

router = APIRouter(prefix="/import", tags=["import"])


@router.post("/csv", dependencies=[Depends(csrf_guard)])
async def import_csv(
    file: UploadFile = File(...),
    _: dict = Depends(require_admin),
    db: Session = Depends(get_db),
) -> dict:
    content = await file.read()
    return parse_csv_and_upsert(db, content)
