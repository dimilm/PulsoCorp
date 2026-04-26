from __future__ import annotations

import csv
import io
import re

from sqlalchemy import func, or_
from sqlalchemy.orm import Session

from app.models.stock import MarketData, Metrics, Position, Stock, Tag, stock_tags
from app.schemas.stock import StockCreate, StockUpdate

ISIN_RE = re.compile(r"^[A-Z]{2}[A-Z0-9]{10}$")

CSV_COL_PRIMARY_ISIN = 2
CSV_COL_PRIMARY_CURRENCY = 4
CSV_COL_NAME = 14
CSV_COL_SECONDARY_ISIN = 15
CSV_COL_REASONING = 22
CSV_COL_TRANCHE_BURGGRABEN = 24
CSV_COL_TRANCHE_INVEST = 25
CSV_COL_TRANCHE_SUM = 26
CSV_COL_YAHOO_LINK = 8
CSV_COL_FINANZEN_LINK = 9
CSV_COL_ONVISTA_CHART_LINK = 55
CSV_COL_ONVISTA_FUNDAMENTAL_LINK = 57
CSV_COL_SECTOR = 62


def _normalize_tag(name: str | None) -> str | None:
    if name is None:
        return None
    cleaned = name.strip().lower()
    if not cleaned:
        return None
    return cleaned[:32]


def _get_or_create_tags(db: Session, names: list[str] | None) -> list[Tag]:
    if not names:
        return []
    seen: list[str] = []
    for raw in names:
        norm = _normalize_tag(raw)
        if norm and norm not in seen:
            seen.append(norm)
    if not seen:
        return []
    existing = {t.name: t for t in db.query(Tag).filter(Tag.name.in_(seen)).all()}
    result: list[Tag] = []
    for name in seen:
        tag = existing.get(name)
        if tag is None:
            tag = Tag(name=name)
            db.add(tag)
            db.flush()
            existing[name] = tag
        result.append(tag)
    return result


def list_stocks(
    db: Session,
    query: str | None = None,
    sector: str | None = None,
    burggraben: bool | None = None,
    tags: list[str] | None = None,
    tags_mode: str = "any",
) -> list[dict]:
    q = db.query(Stock)
    if query:
        like = f"%{query}%"
        q = q.filter(or_(Stock.name.ilike(like), Stock.isin.ilike(like)))
    if sector:
        q = q.filter(Stock.sector == sector)
    if burggraben is not None:
        q = q.filter(Stock.burggraben == burggraben)

    normalized_tags: list[str] = []
    if tags:
        for t in tags:
            n = _normalize_tag(t)
            if n and n not in normalized_tags:
                normalized_tags.append(n)
    if normalized_tags:
        q = (
            q.join(stock_tags, stock_tags.c.isin == Stock.isin)
            .join(Tag, Tag.id == stock_tags.c.tag_id)
            .filter(Tag.name.in_(normalized_tags))
        )
        if tags_mode == "all":
            q = q.group_by(Stock.isin).having(
                func.count(func.distinct(Tag.id)) == len(normalized_tags)
            )
        else:
            q = q.distinct()

    return [to_stock_out(db, stock) for stock in q.order_by(Stock.name.asc()).all()]


def _missing_metrics(metrics: Metrics | None) -> list[str]:
    if not metrics:
        return [
            "pe_forward",
            "pe_min_5y",
            "pe_max_5y",
            "pe_avg_5y",
            "dividend_yield_current",
            "dividend_yield_avg_5y",
            "analyst_target_1y",
            "market_cap",
            "equity_ratio",
            "debt_ratio",
            "revenue_growth",
        ]
    checks = {
        "pe_forward": metrics.pe_forward,
        "pe_min_5y": metrics.pe_min_5y,
        "pe_max_5y": metrics.pe_max_5y,
        "pe_avg_5y": metrics.pe_avg_5y,
        "dividend_yield_current": metrics.dividend_yield_current,
        "dividend_yield_avg_5y": metrics.dividend_yield_avg_5y,
        "analyst_target_1y": metrics.analyst_target_1y,
        "market_cap": metrics.market_cap,
        "equity_ratio": metrics.equity_ratio,
        "debt_ratio": metrics.debt_ratio,
        "revenue_growth": metrics.revenue_growth,
    }
    return [key for key, value in checks.items() if value is None]


def _calc_target_distance_pct(price: float | None, target: float | None) -> float | None:
    if price is None or target is None or price == 0:
        return None
    return round(((target - price) / price) * 100.0, 2)


def to_stock_out(db: Session, stock: Stock) -> dict:
    # Relies on the eager-loaded 1:1 relationships on Stock (lazy="joined").
    # `db` stays in the signature so callers don't change, but we no longer
    # issue per-row SELECTs from here.
    market = stock.market_data
    position = stock.position or Position(isin=stock.isin, tranches=0)
    metrics = stock.metrics
    analyst_target = metrics.analyst_target_1y if metrics else None
    target_distance = _calc_target_distance_pct(
        market.current_price if market else None, analyst_target
    )
    return {
        "isin": stock.isin,
        "name": stock.name,
        "sector": stock.sector,
        "currency": stock.currency,
        "burggraben": stock.burggraben,
        "reasoning": stock.reasoning,
        "ticker_override": stock.ticker_override,
        "link_yahoo": stock.link_yahoo,
        "link_finanzen": stock.link_finanzen,
        "link_onvista_chart": stock.link_onvista_chart,
        "link_onvista_fundamental": stock.link_onvista_fundamental,
        "tranches": position.tranches,
        "current_price": market.current_price if market else None,
        "day_change_pct": market.day_change_pct if market else None,
        "last_updated": market.last_updated if market else None,
        "last_status": market.last_status if market else None,
        "analyst_target_distance_pct": target_distance,
        "invested_capital_eur": float(position.tranches * 1000),
        "pe_forward": metrics.pe_forward if metrics else None,
        "pe_min_5y": metrics.pe_min_5y if metrics else None,
        "pe_max_5y": metrics.pe_max_5y if metrics else None,
        "pe_avg_5y": metrics.pe_avg_5y if metrics else None,
        "dividend_yield_current": metrics.dividend_yield_current if metrics else None,
        "dividend_yield_avg_5y": metrics.dividend_yield_avg_5y if metrics else None,
        "analyst_target_1y": metrics.analyst_target_1y if metrics else None,
        "market_cap": metrics.market_cap if metrics else None,
        "equity_ratio": metrics.equity_ratio if metrics else None,
        "debt_ratio": metrics.debt_ratio if metrics else None,
        "revenue_growth": metrics.revenue_growth if metrics else None,
        "missing_metrics": _missing_metrics(metrics),
        "tags": sorted([t.name for t in (stock.tags or [])]),
    }


def find_similar_stocks(db: Session, stock: Stock, limit: int = 5) -> list[dict]:
    """Heuristic peer suggestions: same sector, sorted by market-cap proximity.

    We look exclusively in the local DB (no external lookup) so this stays
    fast and free. Stocks without a known market cap fall to the end of the
    list. If the input stock has no sector at all we return an empty list —
    the UI then shows a friendly "kein Sektor" hint instead of guessing.
    """
    if not stock.sector:
        return []

    own_cap = stock.metrics.market_cap if stock.metrics else None

    candidates = (
        db.query(Stock)
        .filter(Stock.sector == stock.sector, Stock.isin != stock.isin)
        .all()
    )
    if not candidates:
        return []

    def sort_key(other: Stock):
        cap = other.metrics.market_cap if other.metrics else None
        if own_cap is not None and cap is not None:
            return (0, abs(cap - own_cap))
        if cap is not None:
            return (1, -cap)
        return (2, other.name.lower())

    candidates.sort(key=sort_key)
    return [to_stock_out(db, c) for c in candidates[:limit]]


def create_stock(db: Session, payload: StockCreate) -> Stock:
    stock = Stock(
        isin=payload.isin.upper().strip(),
        name=payload.name.strip(),
        sector=payload.sector,
        currency=payload.currency,
        burggraben=payload.burggraben,
        reasoning=payload.reasoning,
        ticker_override=payload.ticker_override,
        link_yahoo=payload.link_yahoo,
        link_finanzen=payload.link_finanzen,
        link_onvista_chart=payload.link_onvista_chart,
        link_onvista_fundamental=payload.link_onvista_fundamental,
    )
    db.merge(stock)
    db.merge(Position(isin=stock.isin, tranches=payload.tranches))
    db.merge(MarketData(isin=stock.isin, last_status="ok"))
    db.flush()
    persisted = db.get(Stock, stock.isin)
    if persisted is not None:
        persisted.tags = _get_or_create_tags(db, payload.tags)
    db.commit()
    return db.get(Stock, stock.isin)


STOCK_PATCH_FIELDS = (
    "name",
    "sector",
    "currency",
    "burggraben",
    "reasoning",
    "ticker_override",
    "link_yahoo",
    "link_finanzen",
    "link_onvista_chart",
    "link_onvista_fundamental",
)


def update_stock(db: Session, stock: Stock, payload: StockUpdate) -> Stock:
    data = payload.model_dump(exclude_unset=True)
    for field in STOCK_PATCH_FIELDS:
        if field in data:
            setattr(stock, field, data[field])

    if "tranches" in data:
        pos = db.get(Position, stock.isin) or Position(isin=stock.isin)
        pos.tranches = data["tranches"] or 0
        db.add(pos)

    if "tags" in data:
        stock.tags = _get_or_create_tags(db, data["tags"] or [])

    db.add(stock)
    db.commit()
    return stock


def parse_csv_and_upsert(db: Session, content: bytes) -> dict:
    seed_rows = extract_seed_rows_from_csv(content)
    imported = 0
    for row in seed_rows:
        upsert_seed_row(db, row)
        imported += 1
    db.commit()
    return {"imported": imported, "skipped": 0, "errors": []}


def extract_seed_rows_from_csv(content: bytes) -> list[dict]:
    text = content.decode("utf-8-sig", errors="ignore")
    reader = csv.reader(io.StringIO(text), delimiter=";")
    results: list[dict] = []
    for row in reader:
        row_data = _extract_row_data(row)
        if row_data:
            results.append(row_data)
    return results


def _extract_row_data(row: list[str]) -> dict | None:
    if len(row) <= CSV_COL_PRIMARY_ISIN:
        return None

    isin = (_safe_get(row, CSV_COL_SECONDARY_ISIN) or _safe_get(row, CSV_COL_PRIMARY_ISIN) or "").upper()
    if not ISIN_RE.match(isin):
        isins = [cell.strip().upper() for cell in row if ISIN_RE.match(cell.strip().upper())]
        if not isins:
            return None
        isin = isins[0]

    name = _safe_get(row, CSV_COL_NAME) or _pick_name(row) or isin
    burggraben_tranches = _as_float(_safe_get(row, CSV_COL_TRANCHE_BURGGRABEN))
    invest_tranches = _as_float(_safe_get(row, CSV_COL_TRANCHE_INVEST))
    sum_tranches = _as_float(_safe_get(row, CSV_COL_TRANCHE_SUM))
    tranches = int(round((burggraben_tranches or 0) + (invest_tranches or 0)))
    if tranches == 0 and sum_tranches:
        tranches = int(round(sum_tranches))

    return {
        "isin": isin,
        "name": name,
        "sector": _safe_get(row, CSV_COL_SECTOR),
        "currency": _safe_get(row, CSV_COL_PRIMARY_CURRENCY),
        "burggraben": bool((burggraben_tranches or 0) > 0),
        "tranches": tranches,
        "reasoning": _safe_get(row, CSV_COL_REASONING),
        "link_yahoo": _as_url(_safe_get(row, CSV_COL_YAHOO_LINK)),
        "link_finanzen": _as_url(_safe_get(row, CSV_COL_FINANZEN_LINK)),
        "link_onvista_chart": _as_url(_safe_get(row, CSV_COL_ONVISTA_CHART_LINK)),
        "link_onvista_fundamental": _as_url(_safe_get(row, CSV_COL_ONVISTA_FUNDAMENTAL_LINK)),
    }


def build_seed_rows(db: Session) -> list[dict]:
    """Return current DB state as a list of dicts matching the seed JSON schema.

    Field order, types and defaults are kept identical to
    `backend/app/seed/stocks.seed.json` so the output can directly replace it.
    Tags are an additive optional field and only emitted when present.
    """
    stocks = db.query(Stock).order_by(func.upper(Stock.name).asc()).all()
    rows: list[dict] = []
    for stock in stocks:
        position = db.get(Position, stock.isin)
        row: dict = {
            "isin": stock.isin,
            "name": stock.name,
            "sector": stock.sector,
            "currency": stock.currency,
            "burggraben": bool(stock.burggraben),
            "tranches": int(position.tranches) if position and position.tranches is not None else 0,
            "reasoning": stock.reasoning,
            "link_yahoo": stock.link_yahoo,
            "link_finanzen": stock.link_finanzen,
            "link_onvista_chart": stock.link_onvista_chart,
            "link_onvista_fundamental": stock.link_onvista_fundamental,
            "tags": sorted(t.name for t in (stock.tags or [])),
        }
        rows.append(row)
    return rows


def upsert_seed_row(db: Session, row: dict) -> None:
    """Insert or update a single seed-shaped row.

    Used by both the JSON loader on first boot (`seed_service`) and the CSV
    importer (`parse_csv_and_upsert`). The shape matches
    `backend/app/seed/stocks.seed.json` so callers can pipe one straight
    through the other without translation. The function flushes the inserts
    but does *not* commit — the caller decides batching.
    """
    db.merge(
        Stock(
            isin=row["isin"],
            name=row["name"],
            sector=row.get("sector"),
            currency=row.get("currency"),
            burggraben=row.get("burggraben", False),
            reasoning=row.get("reasoning"),
            link_yahoo=row.get("link_yahoo"),
            link_finanzen=row.get("link_finanzen"),
            link_onvista_chart=row.get("link_onvista_chart"),
            link_onvista_fundamental=row.get("link_onvista_fundamental"),
        )
    )
    db.merge(Position(isin=row["isin"], tranches=row.get("tranches", 0)))
    db.merge(MarketData(isin=row["isin"], last_status="ok"))
    db.flush()
    tag_names = row.get("tags") or []
    if tag_names:
        stock = db.get(Stock, row["isin"])
        if stock is not None:
            stock.tags = _get_or_create_tags(db, tag_names)


def _safe_get(row: list[str], index: int) -> str | None:
    if index < len(row):
        value = row[index].strip()
        return value or None
    return None


def _as_float(value: str | None) -> float | None:
    if not value:
        return None
    clean = value.replace("%", "").replace(".", "").replace(",", ".")
    try:
        return float(clean)
    except ValueError:
        return None


def _as_url(value: str | None) -> str | None:
    if not value:
        return None
    if value.lower().startswith("http"):
        return value
    return None


def _pick_name(row: list[str]) -> str | None:
    for cell in row:
        value = cell.strip()
        if not value or value.startswith("http"):
            continue
        upper = value.upper()
        if ISIN_RE.match(upper):
            continue
        if len(value) > 2 and any(ch.isalpha() for ch in value):
            if not any(token in upper for token in ["USD", "EUR", "LINK"]):
                return value
    return None
