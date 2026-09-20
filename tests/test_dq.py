import pandas as pd
import pytest

from adoption_lens.dq import SQL_CHECKS, run_dq
from adoption_lens.golden import golden_inputs
from adoption_lens.warehouse import Warehouse


def _status(inputs):
    dq = run_dq(Warehouse(inputs), inputs)
    return dq.set_index("check")["passed"]


def _with(aei=None, **replacements):
    inputs = golden_inputs()
    if aei is not None:
        inputs.aei = aei(inputs.aei.copy())
    for k, v in replacements.items():
        setattr(inputs, k, v)
    return inputs


def test_every_check_has_a_layer_a_severity_and_a_description():
    assert len({c[1] for c in SQL_CHECKS}) == len(SQL_CHECKS)
    assert all(c[0] and c[2] in {"error", "warn", "info"} and c[4] for c in SQL_CHECKS)


@pytest.mark.realdata
def test_the_real_files_pass_every_check(real):
    dq = run_dq(real.warehouse, real.inputs)
    assert dq["passed"].all(), dq[~dq["passed"]].to_string()
    assert len(dq) == 20


@pytest.mark.realdata
def test_the_real_files_carry_the_documented_findings(real):
    dq = run_dq(real.warehouse, real.inputs).set_index("check")["value"]
    assert dq["documented_rollup_gaps"] == 3 and dq["unexplained_rollup_gaps"] == 0
    assert dq["negative_ci_lower_bounds"] == 46 and dq["countries_without_population"] == 2


def test_a_duplicated_row_is_flagged():
    inputs = _with(aei=lambda d: pd.concat([d, d.iloc[[0]]], ignore_index=True))
    assert not _status(inputs)["duplicate_keys"]


def test_a_negative_count_is_flagged():
    def corrupt(d):
        d.loc[d["variable"] == "use_case_count", "value"] = -1.0
        return d
    assert not _status(_with(aei=corrupt))["negative_values"]


def test_a_missing_value_is_flagged():
    def corrupt(d):
        d.loc[0, "value"] = float("nan")
        return d
    assert not _status(_with(aei=corrupt))["null_values"]


def test_a_percentage_above_100_is_flagged():
    def corrupt(d):
        d.loc[d["variable"] == "use_case_pct", "value"] = 150.0
        return d
    assert not _status(_with(aei=corrupt))["percentages_out_of_range"]


def test_shares_that_do_not_add_up_are_flagged():
    def corrupt(d):
        i = d.index[(d["variable"] == "task_success_pct") & (d["geo_id"] == "CA")][0]
        d.loc[i, "value"] += 5
        return d
    status = _status(_with(aei=corrupt))
    assert not status["shares_sum_to_100"] and not status["counts_agree_with_percentages"]


def test_an_unknown_country_code_is_flagged():
    def corrupt(d):
        d.loc[d["geo_id"] == "GB", "geo_id"] = "ZQ"
        return d
    assert not _status(_with(aei=corrupt))["unknown_country_codes"]


def test_an_unknown_subregion_parent_is_flagged():
    def corrupt(d):
        d.loc[d["geo_id"] == "QQ-A", "geo_id"] = "ZQ-A"
        return d
    assert not _status(_with(aei=corrupt))["unknown_subregion_parents"]


def test_a_period_that_is_not_one_week_is_flagged():
    def corrupt(d):
        d.loc[d.index[0], "date_end"] = pd.Timestamp("2026-02-20")
        return d
    assert not _status(_with(aei=corrupt))["period_is_one_week"]


def test_a_missing_source_is_flagged():
    assert not _status(_with(aei=lambda d: d[d["source"] == "claude_ai"]))["both_sources_loaded"]


def test_a_subregion_gap_that_no_territory_explains_is_flagged():
    def corrupt(d):
        d.loc[(d["geo_id"] == "CA-ON") & (d["variable"] == "usage_count"), "value"] += 7
        return d
    status = _status(_with(aei=corrupt))
    assert not status["unexplained_rollup_gaps"]


def test_the_golden_data_has_no_roll_up_gaps_to_begin_with():
    inputs = golden_inputs()
    dq = run_dq(Warehouse(inputs), inputs).set_index("check")["value"]
    assert dq["unexplained_rollup_gaps"] == 0 and dq["documented_rollup_gaps"] == 0


def test_a_territory_listed_under_both_a_country_and_a_subregion_explains_the_gap():
    def corrupt(d):
        sub = d[(d["geo_id"] == "CA-ON") & (d["variable"] == "usage_count")].copy()
        sub["geo_id"], sub["value"] = "CA-XT", 7.0
        country = d[(d["geo_id"] == "XX") & (d["variable"] == "usage_count")].copy()
        country["geo_id"], country["value"] = "XT", 7.0
        return pd.concat([d, sub, country], ignore_index=True)
    territories = pd.DataFrame({"parent": ["CA"], "subregion": ["CA-XT"], "territory": ["XT"]})
    inputs = _with(aei=corrupt, territories=territories)
    dq = run_dq(Warehouse(inputs), inputs).set_index("check")["value"]
    assert dq["documented_rollup_gaps"] == 1 and dq["unexplained_rollup_gaps"] == 0


def test_a_finance_category_that_does_not_exist_is_flagged():
    inputs = _with(finance_lens=pd.DataFrame({"cluster": ["A category that is not in the data"]}))
    assert not _status(inputs)["finance_lens_clusters_exist"]


def test_a_bad_occupation_row_is_flagged():
    jobs = golden_inputs().job_exposure.copy()
    jobs.loc[0, "observed_exposure"] = 1.7
    assert not _status(_with(job_exposure=jobs))["job_exposure_contract"]


def test_provincial_populations_that_do_not_add_up_are_flagged():
    inputs = golden_inputs()
    inputs.canada_population += 1
    assert not _status(inputs)["province_population_adds_up"]
