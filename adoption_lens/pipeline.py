from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path

import pandas as pd

from .compare import check_invariants, reconcile_all, reconciliation_summary
from .config import ARTIFACTS, DATA_RAW, SOURCES
from .data import Inputs, load_inputs
from .dq import run_dq
from .fetch import sha256_of
from .golden import golden_expected, golden_inputs
from .investigate import rollup_report
from .mutants import make_corpus, run_mutation_suite
from .readout import build_readout, make_ctx
from .reference import reference_metrics
from .warehouse import Warehouse


def _names(inputs: Inputs) -> pd.DataFrame:
    countries = inputs.countries.rename(columns={"iso2": "geo_id", "country": "name"})[["geo_id", "name", "iso3"]]
    countries = countries.assign(level="country")
    provinces = inputs.provinces[["geo_id", "name"]].assign(iso3=None, level="subregion")
    return pd.concat([countries, provinces], ignore_index=True)


def run(out: Path = ARTIFACTS, raw_dir: Path = DATA_RAW, mutation: bool = True) -> dict:
    t0 = time.time()
    out, raw_dir = Path(out), Path(raw_dir)
    missing = [s["file"] for s in SOURCES.values() if not (raw_dir / s["file"]).exists()]
    if missing:
        raise FileNotFoundError(f"missing source files in {raw_dir}: {', '.join(missing)}")
    for sub in ("gold", "qa"):
        (out / sub).mkdir(parents=True, exist_ok=True)

    print("loading and verifying sources")
    manifest = {}
    for key, spec in SOURCES.items():
        path = raw_dir / spec["file"]
        digest = sha256_of(path)
        manifest[key] = {"file": spec["file"], "url": spec["url"], "bytes": path.stat().st_size, "sha256": digest,
                         "matches_published_sha256": digest == spec["sha256"]}
    inputs = load_inputs(raw_dir)

    print("building the SQL metric layer")
    wh = Warehouse(inputs)
    sut = wh.metrics()

    print("computing the independent reference")
    ref = reference_metrics(inputs)

    print("running data checks, reconciliation and invariants")
    dq = run_dq(wh, inputs)
    recon = reconciliation_summary(sut, ref)
    issues = reconcile_all(sut, ref)
    inv = check_invariants(sut, inputs)

    print("writing and verifying the brief")
    brief = build_readout(make_ctx(sut, inputs), make_ctx(ref, inputs))

    mut = None
    if mutation:
        print("injecting defects into the SQL")
        corpora = [make_corpus("real data", inputs), make_corpus("golden data", golden_inputs(), golden_expected())]
        mut = run_mutation_suite(corpora)

    for name, df in sut.items():
        df.to_csv(out / "gold" / f"{name}.csv", index=False)
    _names(inputs).to_csv(out / "gold" / "geo_names.csv", index=False)
    (out / "brief.md").write_text(brief.markdown)
    brief.facts.to_csv(out / "qa" / "brief_facts.csv", index=False)
    recon.to_csv(out / "qa" / "reconciliation.csv", index=False)
    issues.to_csv(out / "qa" / "reconciliation_issues.csv", index=False)
    inv.to_csv(out / "qa" / "invariants.csv", index=False)
    dq.to_csv(out / "qa" / "data_quality.csv", index=False)
    rollup_report(wh).to_csv(out / "qa" / "rollup_gaps.csv", index=False)
    if mut is not None:
        mut.to_csv(out / "qa" / "mutation.csv", index=False)
    (out / "source_manifest.json").write_text(json.dumps(manifest, indent=2))

    counts = {k: int((inputs.aei["source"] == k).sum()) for k in SOURCES}
    summary = {
        "source_rows": counts,
        "sources_match_published_checksums": all(m["matches_published_sha256"] for m in manifest.values()),
        "reconciliation": {"cells_compared": int(recon["cells_compared"].sum()), "mismatches": int(recon["mismatches"].sum())},
        "invariants": {"total": int(len(inv)), "passed": int(inv["passed"].sum())},
        "data_checks": {"total": int(len(dq)), "passed": int(dq["passed"].sum()),
                        "info": int((dq["severity"] == "info").sum())},
        "mutation": ({"total": int(len(mut)), "killed": int(mut["killed"].sum())} if mut is not None else None),
        "brief": {"figures": int(brief.n_facts), "verified": bool(brief.verified)},
    }
    gate = (summary["sources_match_published_checksums"] and summary["reconciliation"]["mismatches"] == 0
            and summary["invariants"]["passed"] == summary["invariants"]["total"]
            and summary["data_checks"]["passed"] == summary["data_checks"]["total"] and summary["brief"]["verified"]
            and (mut is None or summary["mutation"]["killed"] == summary["mutation"]["total"]))
    summary["all_gates_passed"] = bool(gate)
    (out / "qa" / "summary.json").write_text(json.dumps(summary, indent=2))
    print(f"\nfinished in {time.time() - t0:.0f}s\n{json.dumps(summary, indent=2)}")
    return summary


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="Build metrics, run the QA gates and write the artifacts")
    ap.add_argument("--out", type=Path, default=ARTIFACTS)
    ap.add_argument("--raw", type=Path, default=DATA_RAW)
    ap.add_argument("--skip-mutation", action="store_true")
    a = ap.parse_args(argv)
    return 0 if run(a.out, a.raw, mutation=not a.skip_mutation)["all_gates_passed"] else 1


if __name__ == "__main__":
    sys.exit(main())
