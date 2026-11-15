from functools import lru_cache
import json
import os
from pathlib import Path
import pandas as pd
from fastapi import FastAPI, HTTPException, Query
from fastapi.responses import FileResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles

ROOT = Path(
    os.getenv(
        "TOURISM_EXPORT_DIR", Path(__file__).resolve().parent.parent / "data/gold"
    )
)
STATIC = Path(__file__).parent / "static"
app = FastAPI(title="TurismoLakehouse", version="1.0.0")
app.mount("/static", StaticFiles(directory=STATIC), name="static")


@lru_cache
def table(name):
    if name not in {
        "fact_hotel",
        "fact_markets_annual",
        "fact_region_monthly",
        "fact_housing",
        "dim_province",
        "fact_forecast",
    }:
        raise ValueError("Tabla no autorizada")
    return pd.read_csv(ROOT / (name + ".csv"))


def clean(frame):
    return frame.astype(object).where(pd.notna(frame), None).to_dict(orient="records")


@app.get("/", include_in_schema=False)
def index():
    return FileResponse(STATIC / "index.html")


@app.get("/health")
def health():
    return {
        "status": "ok",
        "hotel_rows": len(table("fact_hotel")),
        "pipeline": json.loads((ROOT / "pipeline-run.json").read_text()),
    }


@app.get("/api/dashboard")
def dashboard(year: int = Query(2025, ge=2020, le=2100), province: str | None = None):
    df = table("fact_hotel").copy()
    provinces = table("dim_province")
    if province and province not in set(provinces.province):
        raise HTTPException(422, "Provincia desconocida")
    current = df[df.year == year]
    if province:
        current = current[current.province == province]
    if current.empty:
        raise HTTPException(404, "No hay observaciones publicadas para esa selección")
    current = current.copy()
    current["month"] = pd.to_datetime(current.period_start).dt.month
    months = set(current.month)
    previous = df[
        (df.year == year - 1) & pd.to_datetime(df.period_start).dt.month.isin(months)
    ]
    if province:
        previous = previous[previous.province == province]
    nights = float(current.nights_total.sum())
    travelers = float(current.travelers_total.sum())
    prior = (
        float(previous.nights_total.sum()) if len(previous) == len(current) else None
    )
    weights = current.hotel_beds * pd.to_datetime(current.period_start).dt.days_in_month
    valid = current.occupancy_pct.notna() & weights.gt(0)
    occupancy = (
        float(
            (current.loc[valid, "occupancy_pct"] * weights[valid]).sum()
            / weights[valid].sum()
        )
        if valid.any()
        else None
    )
    trend = current.groupby("period_start", as_index=False).agg(
        nights=("nights_total", "sum"),
        travelers=("travelers_total", "sum"),
        foreign=("travelers_foreign", lambda s: s.sum(min_count=1)),
    )
    current["occupancy_weight"] = weights.where(valid, 0)
    current["occupied_weight"] = (
        current.occupancy_pct.fillna(0) * current.occupancy_weight
    )
    areas = current.groupby("province", as_index=False).agg(
        nights=("nights_total", "sum"),
        travelers=("travelers_total", "sum"),
        occupied_weight=("occupied_weight", "sum"),
        occupancy_weight=("occupancy_weight", "sum"),
    )
    areas["occupancy"] = areas.occupied_weight / areas.occupancy_weight.replace(
        0, float("nan")
    )
    areas = areas.drop(columns=["occupied_weight", "occupancy_weight"])
    markets = table("fact_markets_annual")
    markets = markets[
        (markets.year == year) & (markets.country != "Total")
    ].sort_values("spend_eur", ascending=False)
    housing = table("fact_housing")
    housing = housing[housing.year <= year]
    if province:
        housing = housing[housing.province == province]
    housing_date = housing.period_start.max() if not housing.empty else None
    homes = (
        housing[housing.period_start == housing_date].homes.sum()
        if housing_date
        else None
    )
    forecast = table("fact_forecast")
    forecast = forecast[forecast.province == province] if province else forecast
    forecast = forecast.groupby("period_start", as_index=False).agg(
        predicted_nights=("predicted_nights", "sum"),
        lower=("lower", "sum"),
        upper=("upper", "sum"),
    )
    return {
        "year": year,
        "province": province,
        "provinces": provinces.province.tolist(),
        "available_years": sorted(int(v) for v in df.year.unique()),
        "months": sorted(months),
        "kpis": {
            "travelers": travelers,
            "nights": nights,
            "nights_yoy_pct": (nights / prior - 1) * 100 if prior else None,
            "occupancy_pct": occupancy,
            "mean_stay": nights / travelers if travelers else None,
            "tourist_homes": int(homes) if homes is not None else None,
            "housing_date": housing_date,
        },
        "trend": clean(trend),
        "provinces_data": clean(areas),
        "markets": clean(markets),
        "forecast": clean(forecast),
        "missing_values": int(current.isna().sum().sum()),
        "scope": {
            "markets": "Gasto anual de Andalucía por país. No existe desglose provincial en esta fuente.",
            "occupancy": "Media ponderada por plazas y días del mes.",
            "forecast": "Previsión desde el último mes observado; intervalos aproximados. Los límites agregados no son intervalos conjuntos calibrados.",
            "weather": "Sin observaciones meteorológicas cargadas. Requiere clave y selección de estaciones AEMET.",
            "yoy": "Mismos meses publicados del año anterior; no se completa con ceros.",
        },
        "pipeline": json.loads((ROOT / "pipeline-run.json").read_text()),
    }


@app.get("/api/export.csv")
def export(year: int = 2025, province: str | None = None):
    dashboard(year, province)
    data = table("fact_hotel")
    data = data[data.year == year]
    if province:
        data = data[data.province == province]
    return StreamingResponse(
        iter([data.to_csv(index=False).encode("utf-8-sig")]),
        media_type="text/csv",
        headers={"Content-Disposition": f'attachment; filename="turismo-{year}.csv"'},
    )


@app.get("/api/pipeline")
def pipeline():
    return {
        "run": json.loads((ROOT / "pipeline-run.json").read_text()),
        "sources": json.loads((ROOT.parent / "source-manifest.json").read_text()),
        "forecast": json.loads((ROOT / "forecast-metrics.json").read_text()),
    }
