from pathlib import Path

import pandas as pd
import pytest

from adoption_lens.config import DATA_RAW, SOURCES
from adoption_lens.data import Inputs, load_inputs, load_reference, read_aei
from adoption_lens.golden import golden_expected, golden_inputs
from adoption_lens.mutants import make_corpus

FIXTURES = Path(__file__).parent / "fixtures"


def slice_inputs() -> Inputs:
    aei = pd.concat([read_aei(FIXTURES / "aei_slice_claude_ai.csv", "claude_ai"),
                     read_aei(FIXTURES / "aei_slice_api.csv", "api")], ignore_index=True)
    return Inputs(aei=aei, **load_reference())


@pytest.fixture(scope="session")
def golden():
    return make_corpus("golden", golden_inputs(), golden_expected())


@pytest.fixture(scope="session")
def real_slice():
    return make_corpus("real slice", slice_inputs())


@pytest.fixture(scope="session")
def real():
    if not all((DATA_RAW / s["file"]).exists() for s in SOURCES.values()):
        pytest.skip("source files are not downloaded")
    return make_corpus("real data", load_inputs())
