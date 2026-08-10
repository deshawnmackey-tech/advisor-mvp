from datetime import timedelta
from pathlib import Path

from feast import Entity, FeatureView, Field, FileSource
from feast.data_format import ParquetFormat
from feast.types import Float32, Float64


client = Entity(name="client_id", join_keys=["client_id"])

DATA_PATH = str(Path(__file__).resolve().parent / "data" / "client_profiles.parquet")


client_profile_source = FileSource(
    name="client_profile_source",
    path=DATA_PATH,
    timestamp_field="event_timestamp",
    file_format=ParquetFormat(),
)


business_profile_fv = FeatureView(
    name="business_profile_fv",
    entities=[client],
    ttl=timedelta(days=365),
    schema=[
        Field(name="revenue_ttm", dtype=Float64),
        Field(name="ebitda_ttm", dtype=Float64),
        Field(name="debt_service", dtype=Float64),
        Field(name="working_capital_ratio", dtype=Float32),
        Field(name="customer_concentration", dtype=Float32),
        Field(name="revenue_growth_yoy", dtype=Float32),
        Field(name="doc_completeness", dtype=Float32),
        Field(name="clinical_revenue", dtype=Float32),
        Field(name="payer_mix_score", dtype=Float32),
    ],
    source=client_profile_source,
)