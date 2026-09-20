from __future__ import annotations

from typing import Mapping, Sequence

import duckdb
import pandas as pd

from .config import SQL_DIR
from .data import Inputs

METRICS: dict[str, tuple[str, list[str]]] = {
    "geo_usage": ("m_geo_usage", ["geo_id"]),
    "shares": ("m_shares", ["source", "geo_id", "metric"]),
    "vs_rest": ("m_vs_rest", ["source", "geo_id", "metric"]),
    "request_mix": ("m_request_mix", ["source", "geo_id", "cluster"]),
    "platform_gap": ("m_platform_gap", ["metric"]),
    "function_exposure": ("m_function_exposure", ["soc_group"]),
}

Override = Mapping[str, Sequence[tuple[str, str]]]


def load_sql() -> dict[str, str]:
    return {p.name: p.read_text() for p in sorted(SQL_DIR.glob("*.sql"))}


def apply_overrides(sql_files: dict[str, str], overrides: Override | None) -> dict[str, str]:
    out = dict(sql_files)
    for fname, pairs in (overrides or {}).items():
        for old, new in pairs:
            if old not in out[fname]:
                raise ValueError(f"override target not found in {fname}: {old!r}")
            out[fname] = out[fname].replace(old, new)
    return out


class Warehouse:
    def __init__(self, inputs: Inputs):
        self.con = duckdb.connect(":memory:")
        frames = {
            "_aei": inputs.aei,
            "_countries": inputs.countries,
            "_provinces": inputs.provinces,
            "_soc": inputs.soc_groups,
            "_jobs": inputs.job_exposure,
            "_fin": inputs.finance_lens,
            "_terr": inputs.territories,
        }
        for name, frame in frames.items():
            self.con.register(name, frame)
        self.con.execute("""
            CREATE TABLE aei_raw AS
            SELECT source, geo_id, geography, CAST(date_start AS DATE) AS date_start, CAST(date_end AS DATE) AS date_end,
                   platform_and_product, facet, CAST(level AS INTEGER) AS level, variable, cluster_name,
                   CAST(value AS DOUBLE) AS value
            FROM _aei""")
        self.con.execute("""
            CREATE TABLE dim_country AS
            SELECT iso2, iso3, country, CAST(population AS BIGINT) AS population, continent FROM _countries""")
        self.con.execute("""
            CREATE TABLE dim_province AS
            SELECT geo_id, name, CAST(population AS BIGINT) AS population FROM _provinces""")
        self.con.execute("CREATE TABLE dim_soc_group AS SELECT CAST(soc_group AS VARCHAR) AS soc_group, name FROM _soc")
        self.con.execute("""
            CREATE TABLE job_exposure AS
            SELECT CAST(occ_code AS VARCHAR) AS occ_code, CAST(title AS VARCHAR) AS title,
                   CAST(observed_exposure AS DOUBLE) AS observed_exposure FROM _jobs""")
        self.con.execute("CREATE TABLE finance_lens AS SELECT CAST(cluster AS VARCHAR) AS cluster FROM _fin")
        self.con.execute("""
            CREATE TABLE dim_territory AS
            SELECT CAST(parent AS VARCHAR) AS parent, CAST(subregion AS VARCHAR) AS subregion,
                   CAST(territory AS VARCHAR) AS territory FROM _terr""")
        self.build_models()

    def build_models(self, overrides: Override | None = None) -> None:
        for sql in apply_overrides(load_sql(), overrides).values():
            self.con.execute(sql)

    def df(self, sql: str) -> pd.DataFrame:
        return self.con.execute(sql).df()

    def metrics(self) -> dict[str, pd.DataFrame]:
        return {name: self.df(f"SELECT * FROM {view} ORDER BY {', '.join(keys)}")
                for name, (view, keys) in METRICS.items()}
