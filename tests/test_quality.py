import numpy as np
import pandas as pd
import pytest
from tourism.forecast import forecast, seasonal_naive
from tourism.weather import number


def test_seasonal_baseline_repeats_previous_year():
    assert np.array_equal(
        seasonal_naive(np.arange(24), 15), np.r_[np.arange(12, 24), np.arange(12, 15)]
    )


def test_aemet_trace_precipitation_is_not_fabricated_zero():
    assert number("Ip") is None and number("12,4") == 12.4


def test_forecast_keeps_temporal_holdouts_and_positive_intervals():
    dates = pd.date_range("2020-01-01", periods=60, freq="MS")
    frame = pd.DataFrame(
        {
            "province": "Prueba",
            "period_start": dates,
            "nights_total": 10000 + 2000 * np.sin(np.arange(60) * 2 * np.pi / 12),
        }
    )
    predictions, reports = forecast(frame)
    assert len(predictions) == 6
    assert reports[0]["train_months"] == 36 and reports[0]["test_months"] == 12
    assert predictions.iloc[0].period_start == "2025-01-01"
    assert (predictions.lower <= predictions.predicted_nights).all()
    assert (predictions.predicted_nights <= predictions.upper).all()


def test_forecast_refuses_gaps():
    dates = pd.date_range("2020-01-01", periods=61, freq="MS").delete(30)
    with pytest.raises(ValueError):
        forecast(
            pd.DataFrame(
                {
                    "province": "Prueba",
                    "period_start": dates,
                    "nights_total": np.ones(60) * 100,
                }
            )
        )


def test_insufficient_history_does_not_create_predictions():
    frame = pd.DataFrame(
        {
            "province": "Prueba",
            "period_start": pd.date_range("2026-01-01", periods=5, freq="MS"),
            "nights_total": 100,
        }
    )
    predictions, reports = forecast(frame)
    assert predictions.empty and reports[0]["status"] == "insufficient"
