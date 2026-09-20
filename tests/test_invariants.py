import pytest

from adoption_lens.compare import check_invariants


def _failed(inv):
    return set(inv.loc[~inv["passed"], "invariant"])


def _copy(metrics):
    return {k: v.copy() for k, v in metrics.items()}


def test_invariants_hold_on_real_rows(real_slice):
    inv = check_invariants(real_slice.warehouse.metrics(), real_slice.inputs)
    assert inv["passed"].all(), inv[~inv["passed"]].to_string()
    assert len(inv) == 18


def test_invariants_hold_on_the_golden_data(golden):
    assert check_invariants(golden.warehouse.metrics(), golden.inputs)["passed"].all()


@pytest.mark.realdata
def test_invariants_hold_on_the_full_files(real):
    assert check_invariants(real.warehouse.metrics(), real.inputs)["passed"].all()


def test_a_share_above_one_is_caught(golden):
    m = _copy(golden.warehouse.metrics())
    m["shares"].loc[0, "share"] = 1.2
    assert "Shares are between 0 and 1" in _failed(check_invariants(m, golden.inputs))


def test_an_index_that_does_not_average_to_one_is_caught(golden):
    m = _copy(golden.warehouse.metrics())
    m["geo_usage"].loc[0, "usage_index"] *= 1.5
    assert "Population-weighted mean usage index is 1 within each peer set" in _failed(check_invariants(m, golden.inputs))


def test_a_rest_group_that_contains_the_geography_is_caught(golden):
    m = _copy(golden.warehouse.metrics())
    vs = m["vs_rest"]
    vs["x_rest"] = vs["x"] + vs["x_rest"]
    vs["n_rest"] = vs["n"] + vs["n_rest"]
    assert "A geography plus its rest-of-parent group reproduces the parent's own share" in _failed(check_invariants(m, golden.inputs))


def test_an_unclassified_geography_in_the_output_is_caught(golden):
    m = _copy(golden.warehouse.metrics())
    m["shares"].loc[0, "geo_id"] = "CA-not_classified"
    assert "No unclassified geography reaches a metric" in _failed(check_invariants(m, golden.inputs))


def test_a_lost_occupation_is_caught(golden):
    m = _copy(golden.warehouse.metrics())
    m["function_exposure"].loc[0, "occupations"] -= 1
    assert "Occupation counts add up to the input table" in _failed(check_invariants(m, golden.inputs))
