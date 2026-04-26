import json
from pathlib import Path

from sqlalchemy.orm import Session

from app.services.stock_service import upsert_seed_row


def load_seed_json(db: Session, seed_path: str) -> int:
    path = Path(seed_path)
    if not path.exists():
        return 0

    rows = json.loads(path.read_text(encoding="utf-8"))
    imported = 0
    for row in rows:
        if not isinstance(row, dict):
            continue
        if "isin" not in row or "name" not in row:
            continue
        upsert_seed_row(db, row)
        imported += 1
    db.commit()
    return imported
