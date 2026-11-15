from datetime import date, timedelta
import json
from pathlib import Path
import httpx


def number(value):
    if value in [None, "", "Ip"]:
        return None
    return float(str(value).replace(",", "."))


def fetch_daily(station, start, end, api_key, folder):
    if not api_key:
        raise ValueError(
            "Se necesita la clave AEMET en el entorno; no se incluye en el repositorio"
        )
    start, end = date.fromisoformat(start), date.fromisoformat(end)
    if end < start:
        raise ValueError("El rango de fechas está invertido")
    rows = []
    folder = Path(folder)
    folder.mkdir(parents=True, exist_ok=True)
    with httpx.Client(timeout=60) as client:
        cursor = start
        while cursor <= end:
            last = min(end, cursor + timedelta(days=14))
            path = f"https://opendata.aemet.es/opendata/api/valores/climatologicos/diarios/datos/fechaini/{cursor}T00:00:00UTC/fechafin/{last}T23:59:59UTC/estacion/{station}"
            response = client.get(path, headers={"api_key": api_key})
            response.raise_for_status()
            meta = response.json()
            if meta.get("estado") != 200:
                raise ValueError("AEMET no devolvió datos para el periodo")
            source = meta.get("datos", "")
            if not source.startswith("https://opendata.aemet.es/"):
                raise ValueError("Destino de descarga no reconocido")
            result = client.get(source)
            result.raise_for_status()
            data = result.json()
            (folder / f"{station}-{cursor}.json").write_text(
                json.dumps(data, ensure_ascii=False)
            )
            rows.extend(
                {
                    "date": r["fecha"],
                    "station": r["indicativo"],
                    "province": r.get("provincia"),
                    "temperature_c": number(r.get("tmed")),
                    "precipitation_mm": number(r.get("prec")),
                }
                for r in data
            )
            cursor = last + timedelta(days=1)
    return rows
