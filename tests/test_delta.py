import pytest
from tourism.medallion import merge, session
from tourism.quality import QualityFailure, validate_silver


@pytest.fixture(scope="module")
def spark():
    engine = session()
    yield engine
    engine.stop()


def test_real_delta_merge_updates_and_inserts_without_duplicates(spark, tmp_path):
    first = spark.createDataFrame([("a", 1.0), ("b", 2.0)], ["id", "value"])
    merge(spark, first, tmp_path, "gold", "items", ["id"])
    next_batch = spark.createDataFrame([("a", 9.0), ("c", 3.0)], ["id", "value"])
    merge(spark, next_batch, tmp_path, "gold", "items", ["id"])
    repeated = merge(spark, next_batch, tmp_path, "gold", "items", ["id"])
    assert {r.id: r.value for r in repeated.collect()} == {"a": 9.0, "b": 2.0, "c": 3.0}
    assert repeated.count() == 3


def test_quality_gate_refuses_unknown_scale_negative_and_duplicate_key(spark):
    schema = "record_key string, period_start date, scale_factor double, value double, year int"
    from datetime import date

    bad = spark.createDataFrame([("a", date(2025, 1, 1), None, -1.0, 2025)], schema)
    with pytest.raises(QualityFailure, match="recognized_scale"):
        validate_silver(bad)
    duplicate = spark.createDataFrame(
        [("a", date(2025, 1, 1), 1.0, 1.0, 2025)] * 2, schema
    )
    with pytest.raises(QualityFailure, match="duplicadas"):
        validate_silver(duplicate)
