from pyspark.sql import functions as F


class QualityFailure(ValueError):
    pass


def validate_silver(frame):
    checks = {
        "record_key_not_null": F.col("record_key").isNotNull(),
        "date_not_null": F.col("period_start").isNotNull(),
        "recognized_scale": F.col("scale_factor").isNotNull(),
        "non_negative_base_value": F.col("value").isNull() | (F.col("value") >= 0),
        "finite_values": F.col("value").isNull()
        | (~F.isnan("value") & (F.abs(F.col("value")) < 1e18)),
        "plausible_year": F.col("year").between(2000, 2100),
    }
    counts = (
        frame.agg(
            *[
                F.sum(
                    F.when(~F.coalesce(condition, F.lit(False)), 1).otherwise(0)
                ).alias(name)
                for name, condition in checks.items()
            ]
        )
        .first()
        .asDict()
    )
    errors = {name: int(number or 0) for name, number in counts.items() if number}
    if errors:
        raise QualityFailure(str(errors))
    if frame.limit(1).count() == 0:
        raise QualityFailure("No hay registros válidos")
    duplicate = frame.groupBy("record_key").count().where("count>1").limit(1).count()
    if duplicate:
        raise QualityFailure("Claves duplicadas después de la deduplicación")
    return {"checks": len(checks) + 1, "failed": errors, "status": "passed"}
