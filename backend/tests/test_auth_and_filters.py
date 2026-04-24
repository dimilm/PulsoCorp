from fastapi.testclient import TestClient

from app.core.security import hash_password
from app.db.session import SessionLocal
from app.main import app
from app.models.user import User


def _login(client: TestClient, username: str = "admin", password: str = "changeme") -> str:
    resp = client.post("/api/v1/auth/login", json={"username": username, "password": password})
    assert resp.status_code == 200
    return resp.json()["csrf_token"]


def test_refresh_endpoint_works() -> None:
    client = TestClient(app)
    _login(client)
    response = client.post("/api/v1/auth/refresh")
    assert response.status_code == 200
    body = response.json()
    assert body["username"] == "admin"
    assert "csrf_token" in body


def test_stocks_filter_by_score_and_undervaluation() -> None:
    client = TestClient(app)
    csrf = _login(client)
    headers = {"X-CSRF-Token": csrf}
    client.post(
        "/api/v1/stocks",
        headers=headers,
        json={
            "isin": "US0000000001",
            "name": "Filter Test Stock",
            "sector": "Tech",
            "currency": "USD",
            "burggraben": True,
            "tranches": 1,
        },
    )
    client.patch(
        "/api/v1/stocks/US0000000001",
        headers=headers,
        json={
            "fundamental_score": 9,
            "fair_value_dcf": 120,
            "fair_value_nav": 110,
            "recommendation": "buy",
        },
    )
    data = client.get("/api/v1/stocks", params={"score_min": 8, "undervalued_dcf": True}).json()
    assert any(row["isin"] == "US0000000001" for row in data)


def test_create_stock_with_tags_and_filter_by_tag() -> None:
    client = TestClient(app)
    csrf = _login(client)
    headers = {"X-CSRF-Token": csrf}
    create = client.post(
        "/api/v1/stocks",
        headers=headers,
        json={
            "isin": "US0000000003",
            "name": "Tag Test Stock",
            "sector": "Tech",
            "currency": "USD",
            "burggraben": False,
            "tranches": 0,
            "tags": ["Growth", " growth ", "Dividend"],
        },
    )
    assert create.status_code == 200
    body = create.json()
    assert sorted(body["tags"]) == ["dividend", "growth"]

    listing = client.get("/api/v1/tags").json()
    assert any(t["name"] == "growth" for t in listing)

    data = client.get("/api/v1/stocks", params={"tags": "growth"}).json()
    assert any(row["isin"] == "US0000000003" for row in data)

    data = client.get("/api/v1/stocks", params={"tags": "no-such-tag"}).json()
    assert not any(row["isin"] == "US0000000003" for row in data)


def test_delete_requires_admin() -> None:
    client = TestClient(app)
    csrf = _login(client)
    headers = {"X-CSRF-Token": csrf}
    client.post(
        "/api/v1/stocks",
        headers=headers,
        json={
            "isin": "US0000000002",
            "name": "Delete Guard Stock",
            "sector": "Tech",
            "currency": "USD",
            "burggraben": False,
            "tranches": 0,
        },
    )

    db = SessionLocal()
    try:
        if not db.get(User, "viewer"):
            db.add(User(username="viewer", password_hash=hash_password("viewerpw"), role="user"))
            db.commit()
    finally:
        db.close()

    viewer_client = TestClient(app)
    viewer_csrf = _login(viewer_client, username="viewer", password="viewerpw")
    response = viewer_client.delete("/api/v1/stocks/US0000000002", headers={"X-CSRF-Token": viewer_csrf})
    assert response.status_code == 403
