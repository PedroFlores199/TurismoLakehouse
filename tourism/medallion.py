import os
import sys
from pathlib import Path
from delta import configure_spark_with_delta_pip
from delta.tables import DeltaTable
from pyspark.sql import SparkSession, Window, functions as F, types as T
from .catalog import PROVINCES, SCALE_FACTORS
from .quality import validate_silver

POINT_SCHEMA = T.StructType(
    [
        T.StructField("Fecha", T.LongType()),
        T.StructField("FK_TipoDato", T.IntegerType()),
        T.StructField("FK_Periodo", T.IntegerType()),
        T.StructField("Anyo", T.IntegerType()),
        T.StructField("Valor", T.DoubleType()),
        T.StructField("Secreto", T.BooleanType()),
    ]
)
RAW_SCHEMA = T.StructType(
    [
        T.StructField(k, t, False)
        for k, t in [
            ("source_table", T.IntegerType()),
            ("series_code", T.StringType()),
            ("series_name", T.StringType()),
            ("unit_id", T.IntegerType()),
            ("scale_id", T.IntegerType()),
            ("frequency", T.StringType()),
            ("point_json", T.StringType()),
            ("retrieved", T.StringType()),
            ("record_key", T.StringType()),
            ("content_hash", T.StringType()),
        ]
    ]
)


def session():
    active = SparkSession.getActiveSession()
    if active is not None:
        return active
    os.environ.setdefault("PYSPARK_PYTHON", sys.executable)
    os.environ.setdefault("PYSPARK_DRIVER_PYTHON", sys.executable)
    builder = (
        SparkSession.builder.appName("TurismoLakehouse")
        .master("local[2]")
        .config("spark.driver.memory", "2g")
        .config("spark.sql.shuffle.partitions", "4")
        .config("spark.sql.session.timeZone", "Europe/Madrid")
        .config("spark.sql.extensions", "io.delta.sql.DeltaSparkSessionExtension")
        .config(
            "spark.sql.catalog.spark_catalog",
            "org.apache.spark.sql.delta.catalog.DeltaCatalog",
        )
    )
    spark = configure_spark_with_delta_pip(builder).getOrCreate()
    spark.sparkContext.setLogLevel("WARN")
    return spark


def merge(spark, frame, root, layer, name, keys, catalog=None):
    identifier = (
        f"{catalog}.{layer}.{name}" if catalog else str(Path(root) / layer / name)
    )
    exists = (
        spark.catalog.tableExists(identifier)
        if catalog
        else DeltaTable.isDeltaTable(spark, identifier)
    )
    if exists:
        table = (
            DeltaTable.forName(spark, identifier)
            if catalog
            else DeltaTable.forPath(spark, identifier)
        )
        predicate = " AND ".join(f"t.`{key}`=s.`{key}`" for key in keys)
        table.alias("t").merge(
            frame.alias("s"), predicate
        ).whenMatchedUpdateAll().whenNotMatchedInsertAll().execute()
    elif catalog:
        frame.write.format("delta").saveAsTable(identifier)
    else:
        frame.write.format("delta").save(identifier)
    return (
        spark.table(identifier)
        if catalog
        else spark.read.format("delta").load(identifier)
    )


def transform(spark, records, root, catalog=None):
    raw = spark.createDataFrame(
        spark.sparkContext.parallelize(records, 16), RAW_SCHEMA
    ).dropDuplicates(["content_hash"])
    bronze = merge(
        spark, raw, root, "bronze", "observations", ["content_hash"], catalog
    )
    latest = Window.partitionBy("record_key").orderBy(
        F.col("retrieved").desc(), F.col("content_hash").desc()
    )
    df = (
        bronze.withColumn("rank", F.row_number().over(latest))
        .where("rank=1")
        .drop("rank")
        .withColumn("p", F.from_json("point_json", POINT_SCHEMA))
    )
    scales = F.create_map(*[F.lit(x) for pair in SCALE_FACTORS.items() for x in pair])
    df = (
        df.withColumn("scale_factor", scales[F.col("scale_id")])
        .withColumn("year", F.col("p.Anyo"))
        .withColumn("period_start", F.to_date(F.from_unixtime(F.col("p.Fecha") / 1000)))
        .withColumn("is_secret", F.col("p.Secreto"))
        .withColumn(
            "value",
            F.when(
                ~F.coalesce(F.col("p.Secreto"), F.lit(False)),
                F.col("p.Valor") * F.col("scale_factor"),
            ),
        )
    )
    df = df.where(~F.lower("series_name").contains("variación")).where(
        ~F.lower("series_name").contains("acumulado")
    )
    quality = validate_silver(df)
    silver = merge(
        spark, df.drop("p"), root, "silver", "observations", ["record_key"], catalog
    )
    names = [v[0] for v in PROVINCES.values()]
    hotel = (
        silver.where(F.col("source_table") == 2074)
        .withColumn("province", F.regexp_extract("series_name", r"^([^.]+)\.", 1))
        .where(F.col("province").isin(names))
    )
    hotel = hotel.withColumn(
        "measure",
        F.when(F.col("series_name").contains("Pernoctaciones"), "nights").otherwise(
            "travelers"
        ),
    )
    hotel = hotel.withColumn(
        "residence",
        F.when(F.col("series_name").contains("Residentes en el extranjero"), "foreign")
        .when(F.col("series_name").contains("Residentes en España"), "domestic")
        .otherwise("total"),
    )
    hotel = (
        hotel.withColumn("metric", F.concat_ws("_", "measure", "residence"))
        .groupBy("province", "period_start", "year")
        .pivot(
            "metric",
            [
                "travelers_total",
                "travelers_domestic",
                "travelers_foreign",
                "nights_total",
                "nights_domestic",
                "nights_foreign",
            ],
        )
        .agg(F.first("value"))
    )
    occupancy = (
        silver.where(F.col("source_table") == 2066)
        .withColumn("province", F.regexp_extract("series_name", r"^([^.]+)\.", 1))
        .where(F.col("province").isin(names))
    )
    occupancy = (
        occupancy.withColumn(
            "metric",
            F.when(
                F.col("series_name").endswith("Grado de ocupación por plazas."),
                "occupancy_pct",
            )
            .when(
                F.col("series_name").endswith("Número de plazas estimadas."),
                "hotel_beds",
            )
            .when(
                F.col("series_name").endswith(
                    "Número de establecimientos abiertos estimados."
                ),
                "hotels",
            ),
        )
        .where("metric IS NOT NULL")
        .groupBy("province", "period_start")
        .pivot("metric", ["occupancy_pct", "hotel_beds", "hotels"])
        .agg(F.first("value"))
    )
    hotel = hotel.join(occupancy, ["province", "period_start"], "left").withColumn(
        "mean_stay",
        F.when(
            F.col("travelers_total") > 0,
            F.col("nights_total") / F.col("travelers_total"),
        ),
    )
    hotel = merge(
        spark, hotel, root, "gold", "fact_hotel", ["province", "period_start"], catalog
    )
    markets = silver.where(
        (F.col("source_table") == 24746)
        & F.col("series_name").contains(". Andalucía. Dato base.")
    )
    markets = markets.withColumn(
        "country", F.regexp_extract("series_name", r"^([^.]+)\.", 1)
    ).withColumn("region", F.lit("Andalucía"))
    markets = (
        markets.withColumn(
            "metric",
            F.when(F.col("series_name").contains(". Gasto total."), "spend_eur")
            .when(
                F.col("series_name").contains(". Gasto medio por persona."),
                "spend_per_person_eur",
            )
            .when(
                F.col("series_name").contains(". Gasto medio diario por persona."),
                "daily_spend_eur",
            )
            .when(
                F.col("series_name").contains(". Duración media de los viajes."),
                "mean_trip_days",
            ),
        )
        .where("metric IS NOT NULL")
        .groupBy("region", "country", "year")
        .pivot(
            "metric",
            ["spend_eur", "spend_per_person_eur", "daily_spend_eur", "mean_trip_days"],
        )
        .agg(F.first("value"))
    )
    markets = merge(
        spark,
        markets,
        root,
        "gold",
        "fact_markets_annual",
        ["region", "country", "year"],
        catalog,
    )
    regional = silver.where(
        F.col("source_table").isin(10823, 10839)
        & F.col("series_name").startswith("Andalucía.")
    ).withColumn("region", F.lit("Andalucía"))
    regional = (
        regional.withColumn(
            "metric",
            F.when(F.col("source_table") == 10823, "international_tourists")
            .when(F.col("series_name").contains(". Gasto total."), "spend_eur")
            .when(
                F.col("series_name").contains(". Gasto medio por persona."),
                "spend_per_person_eur",
            )
            .when(
                F.col("series_name").contains(". Gasto medio diario por persona."),
                "daily_spend_eur",
            )
            .when(
                F.col("series_name").contains(". Duración media de los viajes."),
                "mean_trip_days",
            ),
        )
        .where("metric IS NOT NULL")
        .groupBy("region", "period_start", "year")
        .pivot(
            "metric",
            [
                "international_tourists",
                "spend_eur",
                "spend_per_person_eur",
                "daily_spend_eur",
                "mean_trip_days",
            ],
        )
        .agg(F.first("value"))
    )
    regional = merge(
        spark,
        regional,
        root,
        "gold",
        "fact_region_monthly",
        ["region", "period_start"],
        catalog,
    )
    housing = (
        silver.where(F.col("source_table") == 39364)
        .withColumn("province", F.regexp_extract("series_name", r"^([^.]+)\.", 1))
        .where(F.col("province").isin(names))
    )
    housing = (
        housing.withColumn(
            "metric",
            F.when(F.col("series_name").contains(". Viviendas turísticas."), "homes")
            .when(
                F.col("series_name").contains(". Plazas por vivienda turística."),
                "beds_per_home",
            )
            .when(F.col("series_name").contains(". Plazas."), "beds"),
        )
        .where("metric IS NOT NULL")
        .groupBy("province", "period_start", "year")
        .pivot("metric", ["homes", "beds", "beds_per_home"])
        .agg(F.first("value"))
    )
    housing = merge(
        spark,
        housing,
        root,
        "gold",
        "fact_housing",
        ["province", "period_start"],
        catalog,
    )
    provinces = spark.createDataFrame(
        [
            (code, name, "Andalucía", float(lat), float(lon))
            for code, (name, lat, lon) in PROVINCES.items()
        ],
        ["code", "province", "region", "latitude", "longitude"],
    )
    provinces = merge(spark, provinces, root, "gold", "dim_province", ["code"], catalog)
    bounds = silver.agg(
        F.min("period_start").alias("start"), F.max("period_start").alias("end")
    )
    calendar = (
        bounds.select(
            F.explode(
                F.sequence(
                    F.trunc("start", "year"),
                    F.last_day(F.add_months("end", 6)),
                    F.expr("interval 1 day"),
                )
            ).alias("date")
        )
        .withColumn("year", F.year("date"))
        .withColumn("month", F.month("date"))
        .withColumn("quarter", F.quarter("date"))
    )
    calendar = merge(spark, calendar, root, "gold", "dim_date", ["date"], catalog)
    return {
        "bronze": bronze.count(),
        "silver": silver.count(),
        "quality": quality,
        "tables": {
            "fact_hotel": hotel,
            "fact_markets_annual": markets,
            "fact_region_monthly": regional,
            "fact_housing": housing,
            "dim_province": provinces,
            "dim_date": calendar,
        },
    }
