from __future__ import annotations

import csv
import io
import re
from datetime import datetime

from sqlalchemy import func, or_
from sqlalchemy.orm import Session

from app.models.stock import MarketData, Metrics, Position, Stock, Tag, Valuation, stock_tags
from app.schemas.stock import StockCreate, StockUpdate
from app.services.valuation_service import calc_discount_pct, calc_target_distance_pct

ISIN_RE = re.compile(r"^[A-Z]{2}[A-Z0-9]{10}$")

CSV_COL_PRIMARY_ISIN = 2
CSV_COL_PRIMARY_CURRENCY = 4
CSV_COL_NAME = 14
CSV_COL_SECONDARY_ISIN = 15
CSV_COL_REASONING = 22
CSV_COL_TRANCHE_BURGGRABEN = 24
CSV_COL_TRANCHE_INVEST = 25
CSV_COL_TRANCHE_SUM = 26
CSV_COL_RECOMMENDATION = 27
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
    recommendation: str | None = None,
    burggraben: bool | None = None,
    score_min: int | None = None,
    score_max: int | None = None,
    undervalued_dcf: bool | None = None,
    undervalued_nav: bool | None = None,
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
    if recommendation:
        q = q.join(Valuation, Valuation.isin == Stock.isin).filter(Valuation.recommendation == recommendation)
    if score_min is not None:
        q = q.join(Valuation, Valuation.isin == Stock.isin).filter(Valuation.fundamental_score >= score_min)
    if score_max is not None:
        q = q.join(Valuation, Valuation.isin == Stock.isin).filter(Valuation.fundamental_score <= score_max)

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

    rows = []
    for stock in q.order_by(Stock.name.asc()).all():
        item = to_stock_out(db, stock)
        if undervalued_dcf is not None:
            is_undervalued_dcf = (item.get("dcf_discount_pct") is not None) and (item["dcf_discount_pct"] < 0)
            if undervalued_dcf != is_undervalued_dcf:
                continue
        if undervalued_nav is not None:
            is_undervalued_nav = (item.get("nav_discount_pct") is not None) and (item["nav_discount_pct"] < 0)
            if undervalued_nav != is_undervalued_nav:
                continue
        rows.append(item)
    return rows


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


def to_stock_out(db: Session, stock: Stock) -> dict:
    market = db.get(MarketData, stock.isin)
    valuation = db.get(Valuation, stock.isin) or Valuation(isin=stock.isin, field_sources={}, field_locks={})
    position = db.get(Position, stock.isin) or Position(isin=stock.isin, tranches=0)

    metrics = db.get(Metrics, stock.isin)
    analyst_target = metrics.analyst_target_1y if metrics else None
    dcf_discount = calc_discount_pct(market.current_price if market else None, valuation.fair_value_dcf)
    nav_discount = calc_discount_pct(market.current_price if market else None, valuation.fair_value_nav)
    target_distance = calc_target_distance_pct(market.current_price if market else None, analyst_target)
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
        "recommendation": valuation.recommendation or "none",
        "fundamental_score": valuation.fundamental_score,
        "moat_score": valuation.moat_score,
        "dcf_discount_pct": dcf_discount,
        "nav_discount_pct": nav_discount,
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
        "field_sources": valuation.field_sources,
        "field_locks": valuation.field_locks,
        "tags": sorted([t.name for t in (stock.tags or [])]),
    }


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
    db.merge(Valuation(isin=stock.isin, field_sources={}, field_locks={}, recommendation="none"))
    db.merge(MarketData(isin=stock.isin, last_status="ok"))
    db.flush()
    persisted = db.get(Stock, stock.isin)
    if persisted is not None:
        persisted.tags = _get_or_create_tags(db, payload.tags)
    db.commit()
    return db.get(Stock, stock.isin)


def update_stock(db: Session, stock: Stock, payload: StockUpdate) -> Stock:
    data = payload.model_dump(exclude_unset=True)
    for field in ["name", "sector", "currency", "burggraben", "reasoning", "ticker_override"]:
        if field in data:
            setattr(stock, field, data[field])

    if "tranches" in data:
        pos = db.get(Position, stock.isin) or Position(isin=stock.isin)
        pos.tranches = data["tranches"] or 0
        db.add(pos)

    valuation = db.get(Valuation, stock.isin) or Valuation(isin=stock.isin, field_sources={}, field_locks={})
    for key in ["recommendation", "recommendation_reason", "fundamental_score", "moat_score", "fair_value_dcf", "fair_value_nav"]:
        if key in data:
            setattr(valuation, key, data[key])
            valuation.field_sources[key] = "manual"
    db.add(valuation)

    if "tags" in data:
        stock.tags = _get_or_create_tags(db, data["tags"] or [])

    db.add(stock)
    db.commit()
    return stock


def parse_csv_and_upsert(db: Session, content: bytes) -> dict:
    seed_rows = extract_seed_rows_from_csv(content)
    imported = 0
    for row in seed_rows:
        _upsert_seed_row(db, row)
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

    recommendation_raw = (_safe_get(row, CSV_COL_RECOMMENDATION) or "").strip().lower()
    recommendation = "none"
    if "risk" in recommendation_raw:
        recommendation = "risk_buy"
    elif "buy" in recommendation_raw:
        recommendation = "buy"

    return {
        "isin": isin,
        "name": name,
        "sector": _safe_get(row, CSV_COL_SECTOR),
        "currency": _safe_get(row, CSV_COL_PRIMARY_CURRENCY),
        "burggraben": bool((burggraben_tranches or 0) > 0),
        "tranches": tranches,
        "recommendation": recommendation,
        "reasoning": _safe_get(row, CSV_COL_REASONING),
        "link_yahoo": _as_url(_safe_get(row, CSV_COL_YAHOO_LINK)),
        "link_finanzen": _as_url(_safe_get(row, CSV_COL_FINANZEN_LINK)),
        "link_onvista_chart": _as_url(_safe_get(row, CSV_COL_ONVISTA_CHART_LINK)),
        "link_onvista_fundamental": _as_url(_safe_get(row, CSV_COL_ONVISTA_FUNDAMENTAL_LINK)),
    }


def _upsert_seed_row(db: Session, row: dict) -> None:
    db.merge(
        Stock(
            isin=row["isin"],
            name=row["name"],
            sector=row["sector"],
            currency=row["currency"],
            burggraben=row["burggraben"],
            reasoning=row["reasoning"],
            link_yahoo=row["link_yahoo"],
            link_finanzen=row["link_finanzen"],
            link_onvista_chart=row["link_onvista_chart"],
            link_onvista_fundamental=row["link_onvista_fundamental"],
        )
    )
    db.merge(Position(isin=row["isin"], tranches=row["tranches"]))
    db.merge(
        Valuation(
            isin=row["isin"],
            recommendation=row["recommendation"],
            field_sources={"recommendation": "manual"},
            field_locks={},
            last_ai_at=datetime.utcnow(),
        )
    )
    db.merge(MarketData(isin=row["isin"], last_status="ok"))


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
