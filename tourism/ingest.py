from datetime import datetime, timezone
from hashlib import sha256
import json
from pathlib import Path
import time
import httpx
from .catalog import SOURCES


def fetch(root: Path, offline: bool = False):
    folder = root / "raw"
    folder.mkdir(parents=True, exist_ok=True)
    records = []
    manifest = []
    with httpx.Client(
        timeout=90,
        follow_redirects=True,
        headers={"User-Agent": "TurismoLakehouse/1.0"},
    ) as client:
        for source in SOURCES:
            table = source["id"]
            target = folder / f"{table}.json"
            url = f"https://servicios.ine.es/wstempus/js/es/DATOS_TABLA/{table}?nult={source['months']}"
            if not offline:
                for attempt in range(4):
                    try:
                        response = client.get(url)
                        response.raise_for_status()
                        payload = response.content
                        json.loads(payload)
                        break
                    except (httpx.HTTPError, ValueError):
                        if attempt == 3:
                            raise
                        time.sleep(2**attempt)
                target.write_bytes(payload)
            if not target.exists():
                raise FileNotFoundError(f"No hay captura de la tabla {table}")
            raw = target.read_bytes()
            data = json.loads(raw)
            if not isinstance(data, list) or not data:
                raise ValueError(f"La tabla {table} está vacía")
            retrieved = datetime.fromtimestamp(
                target.stat().st_mtime, timezone.utc
            ).isoformat()
            manifest.append(
                {
                    **source,
                    "url": url,
                    "sha256": sha256(raw).hexdigest(),
                    "retrieved": retrieved,
                    "series": len(data),
                }
            )
            for series in data:
                for point in series.get("Data", []):
                    key = (
                        f"{table}|{series['COD']}|{point['Anyo']}|{point['FK_Periodo']}"
                    )
                    row = {
                        "source_table": table,
                        "series_code": series["COD"],
                        "series_name": series["Nombre"],
                        "unit_id": series["FK_Unidad"],
                        "scale_id": series["FK_Escala"],
                        "frequency": source["frequency"],
                        "point_json": json.dumps(point, separators=(",", ":")),
                        "retrieved": retrieved,
                    }
                    row["record_key"] = key
                    row["content_hash"] = sha256(
                        json.dumps(row, sort_keys=True).encode()
                    ).hexdigest()
                    records.append(row)
    (root / "source-manifest.json").write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2)
    )
    return records
