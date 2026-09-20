import json
import shutil

import pytest

from adoption_lens.config import SOURCES
from adoption_lens.pipeline import run

from conftest import FIXTURES


def test_the_pipeline_writes_every_artifact_from_real_rows(tmp_path):
    raw = tmp_path / "raw"
    raw.mkdir()
    shutil.copy(FIXTURES / "aei_slice_claude_ai.csv", raw / SOURCES["claude_ai"]["file"])
    shutil.copy(FIXTURES / "aei_slice_api.csv", raw / SOURCES["api"]["file"])
    out = tmp_path / "out"
    summary = run(out=out, raw_dir=raw, mutation=False)
    assert summary["reconciliation"]["mismatches"] == 0 and summary["brief"]["verified"]
    assert summary["sources_match_published_checksums"] is False
    assert summary["all_gates_passed"] is False
    for name in ("brief.md", "source_manifest.json", "qa/summary.json", "qa/data_quality.csv", "qa/rollup_gaps.csv",
                 "gold/geo_usage.csv", "gold/request_mix.csv", "gold/geo_names.csv"):
        assert (out / name).exists(), name
    assert json.loads((out / "qa" / "summary.json").read_text())["source_rows"]["api"] == 70


def test_the_pipeline_refuses_to_run_without_the_source_files(tmp_path):
    with pytest.raises(FileNotFoundError):
        run(out=tmp_path / "out", raw_dir=tmp_path / "nothing")


@pytest.mark.realdata
def test_the_full_pipeline_passes_every_gate_on_the_real_files(real, tmp_path):
    summary = run(out=tmp_path / "out")
    assert summary["all_gates_passed"] is True
    assert summary["mutation"]["killed"] == summary["mutation"]["total"]
