from __future__ import annotations

from dataclasses import dataclass, field

import pandas as pd

from .compare import check_invariants, reconcile_all
from .data import Inputs
from .reference import reference_metrics
from .warehouse import Warehouse


@dataclass(frozen=True)
class Mutant:
    id: str
    name: str
    bug: str
    overrides: dict = field(hash=False)


def _m(id_: str, name: str, bug: str, file: str, *pairs: tuple[str, str]) -> Mutant:
    return Mutant(id_, name, bug, {file: list(pairs)})


MAC, STG, GEO, SHA, REST, REQ, GAP, FUN = ("00_macros.sql", "01_stg_aei.sql", "02_geo_usage.sql", "03_shares.sql",
                                           "04_vs_rest.sql", "05_request_mix.sql", "06_platform_gap.sql",
                                           "07_function_exposure.sql")

MUTANTS: list[Mutant] = [
    _m("M01", "wilson_z_wrong", "Confidence intervals use z = 1.645 instead of 1.96", MAC, ("1.96", "1.645")),
    _m("M02", "wilson_centre_dropped", "The lower Wilson bound drops its centre adjustment and no longer matches the upper bound",
       MAC, ("(x + 1.96 * 1.96 / 2.0 - 1.96 * sqrt(", "(x - 1.96 * sqrt(")),
    _m("M03", "unclassified_geography_counted", "Conversations with no usable country are counted as a place",
       STG, ("(geo_id IN ('NONE', 'not_classified') OR geo_id LIKE '%-not_classified')", "FALSE")),
    _m("M04", "min_sample_guard_removed", "Tiny geographies enter the usage index", GEO, (">= 200", ">= 0")),
    _m("M05", "missing_population_kept", "A country with no population stays in the peer set and inflates the pooled rate",
       GEO, ("JOIN dim_country c ON c.iso2 = u.geo_id", "LEFT JOIN dim_country c ON c.iso2 = u.geo_id"),
       (" AND c.population > 0", "")),
    _m("M06", "per_capita_units_wrong", "Conversations per 100,000 residents is computed per million",
       GEO, ("100000.0", "1000000.0")),
    _m("M07", "index_interval_z_wrong", "The usage-index interval uses z = 1.645", GEO, ("1.96 / sqrt", "1.645 / sqrt")),
    _m("M08", "province_share_denominator_too_wide", "Provincial shares are divided by every subregion in the file, not the provinces",
       GEO, ("FROM usage u\n    JOIN dim_province p ON p.geo_id = u.geo_id\n    WHERE u.geo_level = 'subregion'\n),",
             "FROM usage u\n    LEFT JOIN dim_province p ON p.geo_id = u.geo_id\n    WHERE u.geo_level = 'subregion'\n),")),
    _m("M09", "automation_is_only_directive", "Automation share ignores the feedback-loop pattern",
       SHA, ("WHEN cluster IN ('directive', 'feedback loop') THEN n ELSE 0 END) AS automation",
             "WHEN cluster IN ('directive') THEN n ELSE 0 END) AS automation")),
    _m("M10", "collaboration_denominator_drops_validation", "Validation conversations vanish from the denominator",
       SHA, ("'task iteration', 'validation')", "'task iteration')")),
    _m("M11", "success_denominator_includes_unclassified", "Unclassified success labels count as failures",
       SHA, ("WHEN cluster IN ('yes', 'no') THEN n ELSE 0 END) AS classified",
             "WHEN cluster IN ('yes', 'no', 'not_classified') THEN n ELSE 0 END) AS classified")),
    _m("M12", "use_case_none_counted", "The 'none' use-case bucket is counted in the denominator",
       SHA, ("WHEN cluster IN ('work', 'personal', 'coursework') THEN n ELSE 0 END) AS classified",
             "WHEN cluster IN ('work', 'personal', 'coursework', 'none') THEN n ELSE 0 END) AS classified")),
    _m("M13", "share_guard_removed", "Shares are reported for geographies with almost no data", SHA, ("WHERE n >= 200;", "WHERE n >= 0;")),
    _m("M14", "rest_includes_geography", "The 'rest of world' comparison group still contains the geography itself",
       REST, ("p.x - c.x AS x_rest", "p.x AS x_rest"), ("p.n - c.n AS n_rest", "p.n AS n_rest")),
    _m("M15", "province_compared_with_world", "Provinces are compared with the whole world instead of the rest of Canada",
       REST, ("CASE s.geo_level WHEN 'country' THEN 'GLOBAL' ELSE s.country_code END AS parent_id", "'GLOBAL' AS parent_id")),
    _m("M16", "difference_interval_one_sample", "The interval for a difference ignores the variance of the comparison group",
       REST, (" + share_rest * (1 - share_rest) / n_rest)", ")")),
    _m("M17", "unclassified_category_in_mix", "The 'not_classified' request bucket is treated as a use case",
       REQ, ("      AND cluster <> 'not_classified'\n", "")),
    _m("M18", "lq_interval_ignores_rest", "The location-quotient interval ignores sampling error in the comparison group",
       REQ, ("sqrt(1.0 / x - 1.0 / n + 1.0 / x_rest - 1.0 / n_rest)", "sqrt(1.0 / x - 1.0 / n)")),
    _m("M19", "category_guard_removed", "Location quotients are reported for categories with a handful of conversations",
       REQ, ("    WHERE x >= 30", "    WHERE x >= 0")),
    _m("M20", "lq_rest_is_parent", "The comparison group for a category is the whole parent, not the parent minus the geography",
       REQ, ("g.x - s.x AS x_rest", "g.x AS x_rest")),
    _m("M21", "platform_gap_flipped", "The platform gap is Claude.ai minus API, the opposite of the label",
       GAP, ("b.share - a.share AS diff", "a.share - b.share AS diff")),
    _m("M22", "platform_gap_interval_one_sample", "The platform-gap interval uses only the Claude.ai variance",
       GAP, (" + b.share * (1 - b.share) / b.n)", ")")),
    _m("M23", "mean_exposure_of_exposed_only", "Mean exposure is taken over occupations that have any exposure",
       FUN, ("AVG(observed_exposure) AS mean_exposure", "AVG(observed_exposure) FILTER (WHERE observed_exposure > 0) AS mean_exposure")),
    _m("M24", "median_is_mean", "The median exposure is actually the mean",
       FUN, ("percentile_cont(0.5) WITHIN GROUP (ORDER BY observed_exposure) AS median_exposure",
             "AVG(observed_exposure) AS median_exposure")),
    _m("M25", "dense_rank_used", "Ties in the exposure ranking do not leave a gap", FUN, ("RANK() OVER", "DENSE_RANK() OVER")),
    _m("M26", "comparison_group_guard_removed", "A comparison group of a handful of conversations is accepted",
       REST, ("WHERE p.n - c.n >= 200", "WHERE p.n > c.n")),
]


@dataclass
class Corpus:
    name: str
    inputs: Inputs
    warehouse: Warehouse
    reference: dict
    expected: dict | None = None


def make_corpus(name: str, inputs: Inputs, expected: dict | None = None) -> Corpus:
    return Corpus(name, inputs, Warehouse(inputs), reference_metrics(inputs), expected)


def evaluate_mutant(corpus: Corpus, mutant: Mutant) -> dict:
    try:
        corpus.warehouse.build_models(mutant.overrides)
        sut = corpus.warehouse.metrics()
    except Exception as exc:
        return {"error": str(exc)[:200], "layers": [], "mismatches": 0, "metrics": []}
    layers, moved = [], set()
    issues = reconcile_all(sut, corpus.reference)
    if len(issues):
        layers.append("reconciliation")
        moved |= set(issues["metric"])
    inv = check_invariants(sut, corpus.inputs)
    if (~inv["passed"]).any():
        layers.append("invariants")
    if corpus.expected is not None:
        hand = reconcile_all(sut, corpus.expected)
        if len(hand):
            layers.append("hand-computed")
            moved |= set(hand["metric"])
    return {"error": None, "layers": layers, "mismatches": int(len(issues)), "metrics": sorted(moved)}


def run_mutation_suite(corpora: list[Corpus], mutants: list[Mutant] | None = None) -> pd.DataFrame:
    mutants = MUTANTS if mutants is None else mutants
    results = {m.id: {"id": m.id, "name": m.name, "bug": m.bug, "killed": False, "detected_by": set(),
                      "caught_on": [], "metrics_affected": set(), "error": None} for m in mutants}
    for corpus in corpora:
        try:
            for m in mutants:
                r = evaluate_mutant(corpus, m)
                out = results[m.id]
                if r["error"]:
                    out["error"] = r["error"]
                    continue
                if r["layers"]:
                    out["killed"] = True
                    out["caught_on"].append(corpus.name)
                    out["detected_by"] |= set(r["layers"])
                    out["metrics_affected"] |= set(r["metrics"])
        finally:
            corpus.warehouse.build_models()
    rows = []
    for out in results.values():
        rows.append({**out, "detected_by": ", ".join(sorted(out["detected_by"])), "caught_on": ", ".join(out["caught_on"]),
                     "metrics_affected": ", ".join(sorted(out["metrics_affected"]))})
    return pd.DataFrame(rows)
