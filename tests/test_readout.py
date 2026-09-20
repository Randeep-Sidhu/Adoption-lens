from adoption_lens.mutants import MUTANTS
from adoption_lens.readout import _ordinal, build_readout, make_ctx
from adoption_lens.warehouse import Warehouse


def _brief(corpus, metrics=None):
    metrics = corpus.warehouse.metrics() if metrics is None else metrics
    return build_readout(make_ctx(metrics, corpus.inputs), make_ctx(corpus.reference, corpus.inputs))


def test_the_brief_verifies_on_real_rows(real_slice):
    r = _brief(real_slice)
    assert r.verified and "NOT VERIFIED" not in r.markdown
    assert r.n_facts > 40 and r.facts["match"].all()


def test_the_brief_says_where_the_data_comes_from_and_what_it_cannot_show(real_slice):
    md = _brief(real_slice).markdown
    assert "Anthropic Economic Index" in md and "One week of data" in md and "classifier label" in md


def test_the_brief_is_deterministic(real_slice):
    assert _brief(real_slice).markdown == _brief(real_slice).markdown


def test_a_defective_metric_layer_blocks_the_brief(real_slice):
    wh = Warehouse(real_slice.inputs)
    wh.build_models(next(m for m in MUTANTS if m.name == "automation_is_only_directive").overrides)
    r = _brief(real_slice, wh.metrics())
    assert not r.verified and "NOT VERIFIED" in r.markdown and r.mismatches


def test_ordinals():
    assert [_ordinal(n) for n in (1, 2, 3, 4, 11, 12, 13, 21, 22, 101, 112)] == \
        ["1st", "2nd", "3rd", "4th", "11th", "12th", "13th", "21st", "22nd", "101st", "112th"]


def test_the_golden_data_also_produces_a_verified_brief(golden):
    assert _brief(golden).verified
