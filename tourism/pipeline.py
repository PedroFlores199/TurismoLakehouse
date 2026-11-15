import argparse
from datetime import datetime, timezone
import json
from pathlib import Path
import time
from .ingest import fetch
from .medallion import session, transform
from .forecast import forecast


def run(root, offline=False, catalog=None):
    started = time.perf_counter()
    root = Path(root)
    root.mkdir(parents=True, exist_ok=True)
    records = fetch(root, offline)
    spark = session()
    try:
        result = transform(spark, records, root, catalog)
        output = root / "exports"
        output.mkdir(exist_ok=True)
        tables = {}
        for name, frame in result.pop("tables").items():
            df = frame.toPandas().sort_values(list(frame.columns[:2]))
            target = output / (name + ".csv")
            temporary = target.with_suffix(".tmp")
            df.to_csv(temporary, index=False)
            temporary.replace(target)
            tables[name] = len(df)
        import pandas as pd

        predictions, reports = forecast(pd.read_csv(output / "fact_hotel.csv"))
        predictions.to_csv(output / "fact_forecast.csv", index=False)
        (output / "forecast-metrics.json").write_text(json.dumps(reports, indent=2))
        report = {
            **result,
            "tables": tables,
            "forecast_rows": len(predictions),
            "completed_at": datetime.now(timezone.utc).isoformat(),
            "seconds": round(time.perf_counter() - started, 3),
            "engine": "Apache Spark 4.0.1 / Delta Lake 4.0.0",
            "mode": "local" if catalog is None else "Unity Catalog",
        }
        (output / "pipeline-run.json").write_text(json.dumps(report, indent=2))
        print(json.dumps(report, indent=2))
    finally:
        spark.stop()


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--root", default="lake")
    p.add_argument("--offline", action="store_true")
    p.add_argument("--catalog")
    a = p.parse_args()
    run(a.root, a.offline, a.catalog)


if __name__ == "__main__":
    main()
