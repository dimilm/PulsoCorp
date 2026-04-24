from fastapi import APIRouter, Depends
from sqlalchemy import func
from sqlalchemy.orm import Session

from app.api.deps import get_current_user
from app.db.session import get_db
from app.models.stock import Tag, stock_tags
from app.schemas.tag import TagOut

router = APIRouter(prefix="/tags", tags=["tags"])


@router.get("", response_model=list[TagOut])
def list_tags(_: dict = Depends(get_current_user), db: Session = Depends(get_db)) -> list[dict]:
    rows = (
        db.query(Tag.id, Tag.name, func.count(stock_tags.c.isin).label("count"))
        .outerjoin(stock_tags, stock_tags.c.tag_id == Tag.id)
        .group_by(Tag.id, Tag.name)
        .order_by(Tag.name.asc())
        .all()
    )
    return [{"id": r.id, "name": r.name, "count": int(r.count or 0)} for r in rows]
