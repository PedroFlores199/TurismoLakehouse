import numpy as np
import pandas as pd
from statsmodels.tsa.holtwinters import ExponentialSmoothing


def seasonal_naive(values, horizon):
    return np.resize(np.asarray(values[-12:], dtype=float), horizon)


def ets(values, horizon):
    fitted = ExponentialSmoothing(
        values,
        trend="add",
        damped_trend=True,
        seasonal="add",
        seasonal_periods=12,
        initialization_method="estimated",
    ).fit(optimized=True)
    return np.asarray(fitted.forecast(horizon))


def forecast(hotel, horizon=6):
    rows = []
    reports = []
    for province, group in hotel.groupby("province"):
        group = group.sort_values("period_start")
        values = group.nights_total.to_numpy(dtype=float)
        if len(values) < 48 or np.isnan(values).any():
            reports.append({"province": province, "status": "insufficient"})
            continue
        dates = pd.to_datetime(group.period_start)
        if not np.all(np.diff(dates.dt.year * 12 + dates.dt.month) == 1):
            raise ValueError("La previsión requiere meses consecutivos")
        train, calibration, test = values[:-24], values[-24:-12], values[-12:]
        candidates = {"seasonal_naive": seasonal_naive, "exponential_smoothing": ets}
        errors = {
            name: float(np.mean(np.abs(calibration - fn(train, 12))))
            for name, fn in candidates.items()
        }
        winner = min(errors, key=errors.get)
        fn = candidates[winner]
        quantile = float(
            np.quantile(np.abs(calibration - fn(train, 12)), 0.9, method="higher")
        )
        test_forecast = fn(values[:-12], 12)
        report = {
            "province": province,
            "status": "trained",
            "model": winner,
            "train_months": len(train),
            "calibration_months": 12,
            "test_months": 12,
            "validation_mae": errors,
            "test_mae": float(np.mean(np.abs(test - test_forecast))),
            "test_interval_coverage": float(
                np.mean(np.abs(test - test_forecast) <= quantile)
            ),
            "interval_nominal": 0.9,
            "last_observed": str(dates.iloc[-1].date()),
        }
        reports.append(report)
        predictions = fn(values, horizon)
        months = pd.date_range(
            dates.iloc[-1] + pd.offsets.MonthBegin(1), periods=horizon, freq="MS"
        )
        for month, value in zip(months, predictions):
            rows.append(
                {
                    "province": province,
                    "period_start": str(month.date()),
                    "predicted_nights": max(0, round(float(value))),
                    "lower": max(0, round(float(value) - quantile)),
                    "upper": max(0, round(float(value) + quantile)),
                    "model": winner,
                    "input_last_month": report["last_observed"],
                }
            )
    return pd.DataFrame(rows), reports
