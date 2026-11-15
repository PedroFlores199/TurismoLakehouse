import csv
import io

from fastapi.testclient import TestClient
from tourism.web import app, table

client = TestClient(app)


def test_partial_year_compares_only_matching_months():
    result = client.get("/api/dashboard", params={"year": 2026, "province": "Almería"})
    assert result.status_code == 200
    data = result.json()
    frame = table("fact_hotel")
    prior = frame[
        (frame.year == 2025)
        & (frame.province == "Almería")
        & frame.period_start.str[5:7].astype(int).isin(data["months"])
    ]
    expected = (data["kpis"]["nights"] / prior.nights_total.sum() - 1) * 100
    assert abs(data["kpis"]["nights_yoy_pct"] - expected) < 1e-9
    assert len(data["months"]) < 12


def test_occupancy_comparison_uses_same_weighted_definition():
    data = client.get(
        "/api/dashboard", params={"year": 2025, "province": "Almería"}
    ).json()
    assert (
        abs(data["provinces_data"][0]["occupancy"] - data["kpis"]["occupancy_pct"])
        < 1e-9
    )


def test_export_and_province_validation():
    response = client.get("/api/export.csv", params={"year": 2025, "province": "Cádiz"})
    rows = list(csv.DictReader(io.StringIO(response.content.decode("utf-8-sig"))))
    assert len(rows) == 12
    assert {r["province"] for r in rows} == {"Cádiz"}
    assert (
        client.get("/api/dashboard", params={"province": "../private"}).status_code
        == 422
    )
    assert client.get("/api/export.csv", params={"year": 2099}).status_code == 404


def test_regional_markets_do_not_change_with_province_filter():
    cadiz = client.get(
        "/api/dashboard", params={"year": 2024, "province": "Cádiz"}
    ).json()
    malaga = client.get(
        "/api/dashboard", params={"year": 2024, "province": "Málaga"}
    ).json()
    assert cadiz["markets"] == malaga["markets"]
    assert "No existe desglose provincial" in cadiz["scope"]["markets"]
