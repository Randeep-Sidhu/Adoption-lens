import pytest

from adoption_lens.compare import reconcile_all, reconcile_metric, reconciliation_summary
from adoption_lens.warehouse import METRICS


def test_sql_matches_the_independent_implementation_on_real_rows(real_slice):
    summary = reconciliation_summary(real_slice.warehouse.metrics(), real_slice.reference)
    assert summary["mismatches"].sum() == 0, summary.to_string()
    assert summary["cells_compared"].sum() > 3000


@pytest.mark.realdata
def test_sql_matches_the_independent_implementation_on_the_full_files(real):
    summary = reconciliation_summary(real.warehouse.metrics(), real.reference)
    assert summary["mismatches"].sum() == 0, summary.to_string()
    assert summary["cells_compared"].sum() > 50_000


def test_the_reconciler_finds_and_locates_a_tampered_cell(real_slice):
    sut = {k: v.copy() for k, v in real_slice.warehouse.metrics().items()}
    sut["shares"].loc[3, "x"] += 1
    issues = reconcile_all(sut, real_slice.reference)
    assert set(issues["column"]) >= {"x"} and (issues["metric"] == "shares").all()
    assert issues.loc[issues["column"] == "x", "sut_value"].iloc[0] == issues.loc[issues["column"] == "x", "ref_value"].iloc[0] + 1


def test_the_reconciler_reports_missing_and_extra_rows(real_slice):
    sut = real_slice.warehouse.metrics()
    fewer = reconcile_metric("geo_usage", sut["geo_usage"].iloc[:-1], real_slice.reference["geo_usage"])
    assert (fewer["kind"] == "row_missing_in_sql").sum() == 1
    more = reconcile_metric("geo_usage", sut["geo_usage"], real_slice.reference["geo_usage"].iloc[:-1])
    assert (more["kind"] == "row_only_in_sql").sum() == 1


def test_text_columns_are_compared_too(real_slice):
    sut = {k: v.copy() for k, v in real_slice.warehouse.metrics().items()}
    sut["function_exposure"].loc[0, "most_exposed_occupation"] = "Someone Else"
    issues = reconcile_metric("function_exposure", sut["function_exposure"], real_slice.reference["function_exposure"])
    assert list(issues["column"]) == ["most_exposed_occupation"]


def test_every_metric_has_a_reference_and_a_key(real_slice):
    assert set(real_slice.reference) == set(METRICS)
