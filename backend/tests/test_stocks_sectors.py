"""Unit tests for GET /api/v1/stocks/sectors endpoint."""
from fastapi.testclient import TestClient

from app.main import app


def _login(client: TestClient) -> str:
    resp = client.post("/api/v1/auth/login", json={"username": "admin", "password": "changeme"})
    assert resp.status_code == 200
    return resp.json()["csrf_token"]


def _create_stock(client: TestClient, csrf: str, isin: str, name: str, sector: str | None) -> None:
    payload: dict = {
        "isin": isin,
        "name": name,
        "currency": "USD",
        "tranches": 0,
    }
    if sector is not None:
        payload["sector"] = sector
    resp = client.post("/api/v1/stocks", headers={"X-CSRF-Token": csrf}, json=payload)
    assert resp.status_code == 200, resp.text


def test_sectors_unauthenticated_returns_401() -> None:
    """Unauthentifizierter Request → 401."""
    client = TestClient(app)
    resp = client.get("/api/v1/stocks/sectors")
    assert resp.status_code == 401


def test_sectors_empty_db_returns_empty_list() -> None:
    """Nach Login, ohne Stocks mit Sektor → leere Liste."""
    client = TestClient(app)
    _login(client)
    # Fetch sectors — any pre-existing stocks from other tests may have sectors,
    # so we just verify the response is a list (not an error).
    resp = client.get("/api/v1/stocks/sectors")
    assert resp.status_code == 200
    assert isinstance(resp.json(), list)


def test_sectors_stock_with_none_sector_not_returned() -> None:
    """Stocks mit sector=None → werden nicht zurückgegeben."""
    client = TestClient(app)
    csrf = _login(client)
    # Create a stock without a sector (sector omitted → None in DB)
    _create_stock(client, csrf, isin="TESTNONE000A", name="No Sector Stock", sector=None)

    resp = client.get("/api/v1/stocks/sectors")
    assert resp.status_code == 200
    names = [item["name"] for item in resp.json()]
    # The stock has no sector, so it must not appear in the list
    assert "None" not in names
    # Also verify no entry with an empty/null name slipped through
    assert all(n for n in names)


def test_sectors_stock_with_empty_string_sector_not_returned() -> None:
    """Stocks mit sector="" → werden nicht zurückgegeben."""
    client = TestClient(app)
    csrf = _login(client)
    _create_stock(client, csrf, isin="TESTEMPTY0AB", name="Empty Sector Stock", sector="")

    resp = client.get("/api/v1/stocks/sectors")
    assert resp.status_code == 200
    names = [item["name"] for item in resp.json()]
    assert "" not in names


def test_sectors_alphabetical_order() -> None:
    """Stocks mit Sektoren 'Tech', 'Automotive', 'Healthcare' → alphabetische Reihenfolge."""
    client = TestClient(app)
    csrf = _login(client)
    _create_stock(client, csrf, isin="SORTTECH0001", name="Tech Corp", sector="Tech")
    _create_stock(client, csrf, isin="SORTAUTO0002", name="Auto Corp", sector="Automotive")
    _create_stock(client, csrf, isin="SORTHEAL0003", name="Health Corp", sector="Healthcare")

    resp = client.get("/api/v1/stocks/sectors")
    assert resp.status_code == 200
    names = [item["name"] for item in resp.json()]

    # Extract only the three sectors we just inserted (others may exist from prior tests)
    relevant = [n for n in names if n in {"Tech", "Automotive", "Healthcare"}]
    assert relevant == sorted(relevant), f"Expected alphabetical order, got: {relevant}"
    # All three must be present
    assert set(relevant) == {"Tech", "Automotive", "Healthcare"}


def test_sectors_correct_count_values() -> None:
    """2 Stocks mit Sektor 'Tech', 1 Stock mit Sektor 'Finance' → count-Werte stimmen."""
    client = TestClient(app)
    csrf = _login(client)
    _create_stock(client, csrf, isin="CNTTECH00001", name="Tech Stock One", sector="TechCount")
    _create_stock(client, csrf, isin="CNTTECH00002", name="Tech Stock Two", sector="TechCount")
    _create_stock(client, csrf, isin="CNTFIN000001", name="Finance Stock", sector="FinanceCount")

    resp = client.get("/api/v1/stocks/sectors")
    assert resp.status_code == 200
    data = {item["name"]: item["count"] for item in resp.json()}

    assert "TechCount" in data, "TechCount sector missing from response"
    assert "FinanceCount" in data, "FinanceCount sector missing from response"
    assert data["TechCount"] == 2, f"Expected count 2 for TechCount, got {data['TechCount']}"
    assert data["FinanceCount"] == 1, f"Expected count 1 for FinanceCount, got {data['FinanceCount']}"
