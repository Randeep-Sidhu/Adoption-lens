import re

from adoption_lens import config as C
from adoption_lens.warehouse import METRICS, load_sql

DOC = (C.ROOT / "docs" / "metric_dictionary.md").read_text()


def test_sql_thresholds_match_the_configuration():
    sql = "\n".join(load_sql().values())
    numbers = {int(n) for n in re.findall(r">=\s*(\d+)", sql)}
    assert numbers == {C.MIN_CONVERSATIONS, C.MIN_CATEGORY_COUNT}
    assert {float(z) for z in re.findall(r"(\d\.\d+)\s*(?:\*|/)", sql) if z.startswith("1.9")} == {C.Z}


def test_every_metric_view_is_documented():
    for view, _ in METRICS.values():
        assert view in DOC, f"{view} is missing from docs/metric_dictionary.md"


def test_documented_thresholds_match_the_configuration():
    assert f"{C.MIN_CONVERSATIONS} conversations" in DOC and f"{C.MIN_CATEGORY_COUNT} conversations" in DOC
    assert "1.96" in DOC


def test_the_category_lists_in_the_docs_match_the_configuration():
    for name in (*C.AUTOMATION, *C.AUGMENTATION):
        assert name in DOC
