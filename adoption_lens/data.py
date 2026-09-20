from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import pandas as pd

from .config import AEI_COLUMNS, DATA_RAW, DATA_REF, SOURCES


class SchemaError(ValueError):
    pass


@dataclass
class Inputs:
    aei: pd.DataFrame
    countries: pd.DataFrame
    provinces: pd.DataFrame
    canada_population: int
    soc_groups: pd.DataFrame
    job_exposure: pd.DataFrame
    finance_lens: pd.DataFrame
    territories: pd.DataFrame


def read_aei(path: Path, source: str) -> pd.DataFrame:
    head = pd.read_csv(path, nrows=0)
    if list(head.columns) != AEI_COLUMNS:
        raise SchemaError(f"{path.name}: expected columns {AEI_COLUMNS}, found {list(head.columns)}")
    df = pd.read_csv(path, dtype={"geo_id": "string", "geography": "string", "platform_and_product": "string",
                                  "facet": "string", "variable": "string", "cluster_name": "string"},
                     keep_default_na=False, na_values=[""], parse_dates=["date_start", "date_end"])
    df["cluster_name"] = df["cluster_name"].astype("string")
    df.insert(0, "source", source)
    return df


def read_countries(path: Path) -> pd.DataFrame:
    rows = []
    for line in path.read_text(encoding="utf-8").splitlines():
        if not line or line.startswith("#"):
            continue
        f = line.split("\t")
        rows.append({"iso2": f[0], "iso3": f[1], "country": f[4], "population": int(f[7]) if f[7] else None,
                     "continent": f[8]})
    return pd.DataFrame(rows)


def load_reference(ref_dir: Path = DATA_REF) -> dict:
    ref_dir = Path(ref_dir)
    pop = pd.read_csv(ref_dir / "ca_population.csv")
    countries = read_countries(ref_dir / "countryInfo.txt").drop(columns="population")
    world_bank = pd.read_csv(ref_dir / "population_wb_2024.csv")[["iso3", "population"]]
    countries = countries.merge(world_bank, on="iso3", how="left")
    countries["population"] = countries["population"].astype("Int64")
    return {
        "countries": countries,
        "provinces": pop[pop["level"] == "province"][["geo_id", "name", "population"]].reset_index(drop=True),
        "canada_population": int(pop.loc[pop["level"] == "country", "population"].iloc[0]),
        "soc_groups": pd.read_csv(ref_dir / "soc_major_groups.csv", dtype={"soc_group": "string"}),
        "job_exposure": pd.read_csv(ref_dir / "job_exposure.csv", dtype={"occ_code": "string"}),
        "finance_lens": pd.read_csv(ref_dir / "finance_lens.csv"),
        "territories": pd.read_csv(ref_dir / "territories.csv"),
    }


def load_inputs(raw_dir: Path = DATA_RAW, ref_dir: Path = DATA_REF) -> Inputs:
    aei = pd.concat([read_aei(Path(raw_dir) / spec["file"], key) for key, spec in SOURCES.items()], ignore_index=True)
    return Inputs(aei=aei, **load_reference(ref_dir))
