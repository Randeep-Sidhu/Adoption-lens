import pytest

from adoption_lens.mutants import MUTANTS, Mutant, evaluate_mutant
from adoption_lens.warehouse import apply_overrides, load_sql


def _caught_on(mutant, corpora):
    caught = []
    try:
        for corpus in corpora:
            result = evaluate_mutant(corpus, mutant)
            assert result["error"] is None, f"{mutant.id} produced invalid SQL: {result['error']}"
            if result["layers"]:
                caught.append(corpus.name)
    finally:
        for corpus in corpora:
            corpus.warehouse.build_models()
    return caught


def test_a_clean_run_raises_no_alarm(golden, real_slice):
    baseline = Mutant("M00", "baseline", "no defect", {})
    assert _caught_on(baseline, [golden, real_slice]) == []


@pytest.mark.parametrize("mutant", MUTANTS, ids=lambda m: f"{m.id}-{m.name}")
def test_the_injected_defect_is_caught(mutant, golden, real_slice):
    caught = _caught_on(mutant, [golden, real_slice])
    assert caught, f"{mutant.id} ({mutant.bug}) survived: nothing in the QA layer can see it"


@pytest.mark.parametrize("mutant", MUTANTS, ids=lambda m: f"{m.id}-{m.name}")
def test_every_mutant_really_changes_the_sql(mutant):
    assert apply_overrides(load_sql(), mutant.overrides) != load_sql()


def test_mutant_ids_are_unique():
    assert len({m.id for m in MUTANTS}) == len(MUTANTS)


@pytest.mark.realdata
def test_the_real_files_alone_would_miss_the_tie_ranking_defect(real):
    survivors = [m.id for m in MUTANTS if not _caught_on(m, [real])]
    assert survivors == ["M25"]
