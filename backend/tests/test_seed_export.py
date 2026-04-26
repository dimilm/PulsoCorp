import json

from fastapi.testclient import TestClient

from app.db.session import SessionLocal
from app.main import app
from app.models.stock import Stock
from app.services.stock_service import build_seed_rows, upsert_seed_row


def _login(client: TestClient, username: str = "admin", password: str = "changeme") -> str:
    resp = client.post("/api/v1/auth/login", json={"username": username, "password": password})
    assert resp.status_code == 200
    return resp.json()["csrf_token"]


def test_export_seed_json_round_trip_includes_tags_and_burggraben() -> None:
    client = TestClient(app)
    csrf = _login(client)
    headers = {"X-CSRF-Token": csrf}

    create = client.post(
        "/api/v1/stocks",
        headers=headers,
        json={
            "isin": "US0000000010",
            "name": "Seed Export Stock",
            "sector": "Tech",
            "currency": "USD",
            "burggraben": True,
            "tranches": 3,
            "reasoning": "Strong moat & growth",
            "link_yahoo": "https://finance.yahoo.com/quote/SES/",
            "link_finanzen": None,
            "link_onvista_chart": None,
            "link_onvista_fundamental": None,
            "tags": ["Growth", "Moat"],
        },
    )
    assert create.status_code == 200

    resp = client.get("/api/v1/export/seed-json")
    assert resp.status_code == 200
    assert resp.headers["content-type"].startswith("application/json")
    assert "stocks.seed.json" in resp.headers.get("content-disposition", "")

    rows = json.loads(resp.content)
    row = next(r for r in rows if r["isin"] == "US0000000010")
    assert row["name"] == "Seed Export Stock"
    assert row["sector"] == "Tech"
    assert row["currency"] == "USD"
    assert row["burggraben"] is True
    assert row["tranches"] == 3
    assert row["reasoning"] == "Strong moat & growth"
    assert row["link_yahoo"] == "https://finance.yahoo.com/quote/SES/"
    assert row["link_finanzen"] is None
    assert row["link_onvista_chart"] is None
    assert row["link_onvista_fundamental"] is None
    assert sorted(row["tags"]) == ["growth", "moat"]

    expected_keys = {
        "isin",
        "name",
        "sector",
        "currency",
        "burggraben",
        "tranches",
        "reasoning",
        "link_yahoo",
        "link_finanzen",
        "link_onvista_chart",
        "link_onvista_fundamental",
        "tags",
    }
    assert set(row.keys()) == expected_keys


def test_export_seed_rows_are_sorted_by_name() -> None:
    db = SessionLocal()
    try:
        rows = build_seed_rows(db)
    finally:
        db.close()
    names = [r["name"].upper() for r in rows]
    assert names == sorted(names)


def test_upsert_seed_row_imports_tags_from_seed_dict() -> None:
    db = SessionLocal()
    try:
        upsert_seed_row(
            db,
            {
                "isin": "US0000000011",
                "name": "Reimport Stock",
                "sector": "Tech",
                "currency": "USD",
                "burggraben": False,
                "tranches": 1,
                "reasoning": None,
                "link_yahoo": None,
                "link_finanzen": None,
                "link_onvista_chart": None,
                "link_onvista_fundamental": None,
                "tags": ["alpha", "Beta"],
            },
        )
        db.commit()
        stock = db.get(Stock, "US0000000011")
        assert stock is not None
        assert sorted(t.name for t in stock.tags) == ["alpha", "beta"]
    finally:
        db.close()


def test_upsert_seed_row_without_tags_key_still_works() -> None:
    db = SessionLocal()
    try:
        upsert_seed_row(
            db,
            {
                "isin": "US0000000012",
                "name": "Legacy Seed Stock",
                "sector": "Tech",
                "currency": "USD",
                "burggraben": False,
                "tranches": 0,
                "reasoning": None,
                "link_yahoo": None,
                "link_finanzen": None,
                "link_onvista_chart": None,
                "link_onvista_fundamental": None,
            },
        )
        db.commit()
        stock = db.get(Stock, "US0000000012")
        assert stock is not None
        assert list(stock.tags) == []
    finally:
        db.close()


def test_export_seed_json_requires_auth() -> None:
    client = TestClient(app)
    resp = client.get("/api/v1/export/seed-json")
    assert resp.status_code == 401
