from __future__ import annotations

import argparse
import sys

import numpy as np
import pandas as pd

from .compare import check_invariants, reconcile_all
from .data import load_inputs
from .mutants import MUTANTS, make_corpus
from .warehouse import METRICS, Warehouse


def rollup_report(wh: Warehouse) -> pd.DataFrame:
    return wh.df("""
        WITH sub AS (SELECT split_part(geo_id, '-', 1) AS parent, COUNT(*) AS subregions, SUM(value) AS subregion_sum
                     FROM aei_raw WHERE source = 'claude_ai' AND geography = 'country-state' AND facet = 'country-state'
                       AND variable = 'usage_count' GROUP BY 1),
             ctry AS (SELECT geo_id AS parent, value AS country_count FROM aei_raw
                      WHERE source = 'claude_ai' AND geography = 'country' AND facet = 'country' AND variable = 'usage_count'),
             terr AS (SELECT t.parent, string_agg(t.territory || '=' || CAST(CAST(c.value AS INTEGER) AS VARCHAR), ', '
                                                  ORDER BY t.territory) AS territories, SUM(c.value) AS territory_sum
                      FROM dim_territory t JOIN aei_raw c ON c.source = 'claude_ai' AND c.geography = 'country'
                       AND c.facet = 'country' AND c.variable = 'usage_count' AND c.geo_id = t.territory
                      GROUP BY t.parent)
        SELECT s.parent, s.subregions, c.country_count, s.subregion_sum, s.subregion_sum - c.country_count AS gap,
               t.territories, t.territory_sum,
               (s.subregion_sum - c.country_count) - COALESCE(t.territory_sum, 0) AS unexplained
        FROM sub s JOIN ctry c USING (parent) LEFT JOIN terr t USING (parent)
        WHERE s.subregion_sum <> c.country_count
        ORDER BY s.parent""")


def mutant_report(mutant_id: str) -> None:
    mutant = next((m for m in MUTANTS if m.id == mutant_id.upper()), None)
    if mutant is None:
        raise SystemExit(f"unknown mutant {mutant_id!r}")
    corpus = make_corpus("real", load_inputs())
    corpus.warehouse.build_models(mutant.overrides)
    sut = corpus.warehouse.metrics()
    issues = reconcile_all(sut, corpus.reference)
    inv = check_invariants(sut, corpus.inputs)
    pd.set_option("display.width", 200)
    pd.set_option("display.max_columns", 20)
    print(f"\n{mutant.id} {mutant.name}\nBug injected: {mutant.bug}\n")
    print(f"reconciliation: {'caught' if len(issues) else 'not caught'} ({len(issues)} mismatched cells)")
    print(f"invariants:     {'caught' if (~inv['passed']).any() else 'not caught'} {list(inv.loc[~inv['passed'], 'invariant'])}")
    if issues.empty:
        print("\nNothing to drill into on this data.")
        return
    moved = sorted(issues["metric"].unique())
    print(f"\nmetrics that moved: {moved}\nmetrics that did not: {sorted(set(METRICS) - set(moved))}")
    print("\ncells by metric and column")
    print(issues.groupby(["metric", "column"]).size().rename("cells").to_string())
    v = issues.dropna(subset=["sut_value", "ref_value"]).copy()
    v["error_pct"] = 100 * (v["sut_value"] - v["ref_value"]) / v["ref_value"].abs().replace(0, np.nan)
    print("\nlargest relative errors")
    print(v.reindex(v["error_pct"].abs().sort_values(ascending=False).index).head(8)
          [["metric", "key", "column", "sut_value", "ref_value", "error_pct"]].round(4).to_string(index=False))


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="Drill into a data finding or an injected defect")
    ap.add_argument("target", nargs="?", help="'rollup' or a mutant id such as M07")
    ap.add_argument("--list", action="store_true")
    a = ap.parse_args(argv)
    if a.list or not a.target:
        print("rollup   subregion counts that do not add up to the country count")
        for m in MUTANTS:
            print(f"{m.id}     {m.bug}")
        return 0
    if a.target == "rollup":
        print(rollup_report(Warehouse(load_inputs())).to_string(index=False))
        return 0
    mutant_report(a.target)
    return 0


if __name__ == "__main__":
    sys.exit(main())
