import pytest

from adoption_lens.compare import reconcile_metric
from adoption_lens.warehouse import METRICS


@pytest.mark.parametrize("metric", list(METRICS))
def test_sql_reproduces_the_hand_computed_values(golden, metric):
    issues = reconcile_metric(metric, golden.warehouse.metrics()[metric], golden.expected[metric])
    assert issues.empty, issues.to_string()


@pytest.mark.parametrize("metric", list(METRICS))
def test_reference_reproduces_the_hand_computed_values(golden, metric):
    issues = reconcile_metric(metric, golden.reference[metric], golden.expected[metric])
    assert issues.empty, issues.to_string()


def _shares(golden):
    return golden.warehouse.metrics()["shares"]


def test_wilson_interval_matches_textbook_values(golden):
    row = golden.warehouse.df("SELECT wilson_lo(50.0, 100.0) AS lo, wilson_hi(50.0, 100.0) AS hi").iloc[0]
    assert round(row["lo"], 4) == 0.4038 and round(row["hi"], 4) == 0.5962


def test_unclassified_geographies_never_reach_a_metric(golden):
    m = golden.warehouse.metrics()
    ids = set(m["geo_usage"]["geo_id"]) | set(m["shares"]["geo_id"]) | set(m["request_mix"]["geo_id"])
    assert not ids & {"NONE", "not_classified", "CA-not_classified"}


def test_unclassified_conversations_stay_out_of_the_share_denominator(golden):
    ca = golden.warehouse.metrics()["geo_usage"].set_index("geo_id").loc["CA"]
    assert ca["share_of_known"] == pytest.approx(1000 / 5700)


def test_tiny_geographies_are_left_out(golden):
    m = golden.warehouse.metrics()
    assert "XX" not in set(m["geo_usage"]["geo_id"]) and "CA-NB" not in set(m["geo_usage"]["geo_id"])
    assert "XX" not in set(m["shares"]["geo_id"]) and "CA-NB" not in set(m["shares"]["geo_id"])


def test_a_country_without_a_population_has_shares_but_no_index(golden):
    m = golden.warehouse.metrics()
    assert "ZZ" not in set(m["geo_usage"]["geo_id"])
    assert "ZZ" in set(m["shares"]["geo_id"])


def test_use_case_none_bucket_is_not_in_the_denominator(golden):
    g = _shares(golden)
    row = g[(g["source"] == "claude_ai") & (g["geo_id"] == "GLOBAL") & (g["metric"] == "work_share")].iloc[0]
    assert row["n"] == 99000


def test_a_subregion_is_compared_with_the_rest_of_its_country(golden):
    v = golden.warehouse.metrics()["vs_rest"]
    row = v[(v["geo_id"] == "CA-ON") & (v["metric"] == "work_share")].iloc[0]
    assert row["parent_id"] == "CA" and row["n_rest"] == 500 and row["x_rest"] == 300


def test_a_comparison_group_that_is_too_small_is_dropped(golden):
    v = golden.warehouse.metrics()["vs_rest"]
    assert "QQ-A" not in set(v["geo_id"])
    assert "QQ" in set(v["geo_id"])


def test_a_rare_category_gets_no_location_quotient(golden):
    r = golden.warehouse.metrics()["request_mix"]
    ca = r[r["geo_id"] == "CA"]
    assert len(ca) == 3 and not ca["cluster"].str.startswith("Analyze political").any()


def test_the_boundary_count_is_included(golden):
    r = golden.warehouse.metrics()["request_mix"]
    assert ((r["geo_id"] == "GB") & r["cluster"].str.startswith("Analyze political")).any()


def test_ties_in_the_exposure_ranking_share_a_rank_and_leave_a_gap(golden):
    f = golden.warehouse.metrics()["function_exposure"].set_index("soc_group")
    assert list(f["rank_by_mean"]) == [2, 1, 2, 4]
    assert f.loc["47", "most_exposed_occupation"] == "Construction Laborers"
