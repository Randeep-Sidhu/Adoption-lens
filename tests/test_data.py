import pandas as pd
import pytest

from adoption_lens.data import SchemaError, load_reference, read_aei, read_countries
from adoption_lens.config import DATA_REF

from conftest import FIXTURES


def test_country_code_NA_is_namibia_not_a_missing_value():
    df = read_aei(FIXTURES / "aei_slice_claude_ai.csv", "claude_ai")
    assert df["geo_id"].notna().all()
    assert (df["geo_id"] == "NA").any()


def test_source_column_is_added_and_dates_are_parsed():
    df = read_aei(FIXTURES / "aei_slice_api.csv", "api")
    assert set(df["source"]) == {"api"}
    assert pd.api.types.is_datetime64_any_dtype(df["date_start"])


def test_a_changed_column_layout_is_refused(tmp_path):
    bad = pd.read_csv(FIXTURES / "aei_slice_api.csv").rename(columns={"variable": "metric"})
    path = tmp_path / "changed.csv"
    bad.to_csv(path, index=False)
    with pytest.raises(SchemaError):
        read_aei(path, "api")


def test_geonames_file_is_parsed_including_short_rows():
    countries = read_countries(DATA_REF / "countryInfo.txt")
    assert countries["iso2"].is_unique
    assert countries.loc[countries["iso2"] == "NA", "country"].iloc[0] == "Namibia"
    assert countries.loc[countries["iso2"] == "CA", "population"].iloc[0] > 30_000_000


def test_provincial_populations_add_up_to_the_published_canada_total():
    ref = load_reference()
    assert int(ref["provinces"]["population"].sum()) == ref["canada_population"]
    assert len(ref["provinces"]) == 13


def test_reference_tables_have_the_expected_shape():
    ref = load_reference()
    assert len(ref["soc_groups"]) == 23
    assert ref["job_exposure"]["occ_code"].is_unique
    assert set(ref["territories"].columns) == {"parent", "subregion", "territory"}


def test_country_populations_come_from_the_world_bank_table():
    countries = load_reference()["countries"].set_index("iso2")
    assert countries.loc["CA", "population"] == 41_288_599
    assert (countries["population"].dropna() > 0).all()


def test_a_country_without_a_world_bank_figure_has_no_population():
    countries = load_reference()["countries"].set_index("iso2")
    assert pd.isna(countries.loc["TW", "population"])
