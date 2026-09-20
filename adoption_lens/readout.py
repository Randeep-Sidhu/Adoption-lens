from __future__ import annotations

from dataclasses import dataclass, field
from typing import Callable

import numpy as np
import pandas as pd

from .config import FOCUS_COUNTRY
from .data import Inputs


@dataclass
class Ctx:
    m: dict[str, pd.DataFrame]
    country_names: dict[str, str]
    province_names: dict[str, str]


def make_ctx(metrics: dict[str, pd.DataFrame], inputs: Inputs) -> Ctx:
    return Ctx(metrics, dict(zip(inputs.countries["iso2"], inputs.countries["country"])),
               dict(zip(inputs.provinces["geo_id"], inputs.provinces["name"])))


def _countries(c: Ctx) -> pd.DataFrame:
    g = c.m["geo_usage"]
    return g[g["geo_level"] == "country"].sort_values("usage_index", ascending=False).reset_index(drop=True)


def _provinces(c: Ctx) -> pd.DataFrame:
    g = c.m["geo_usage"]
    return g[g["geo_level"] == "subregion"].sort_values("usage_index", ascending=False).reset_index(drop=True)


def n_countries(c: Ctx) -> int:
    return len(_countries(c))


def focus_rank(c: Ctx) -> int:
    return int(_countries(c).index[_countries(c)["geo_id"] == FOCUS_COUNTRY][0]) + 1


def focus(c: Ctx, col: str) -> float:
    g = c.m["geo_usage"].set_index("geo_id")
    return float(g.loc[FOCUS_COUNTRY, col])


def top_country(c: Ctx) -> str:
    return str(c.country_names[_countries(c).iloc[0]["geo_id"]])


def top_country_index(c: Ctx) -> float:
    return float(_countries(c).iloc[0]["usage_index"])


def province_name(c: Ctx, which: str) -> str:
    p = _provinces(c)
    return c.province_names[p.iloc[0 if which == "best" else -1]["geo_id"]]


def province_index(c: Ctx, which: str) -> float:
    p = _provinces(c)
    return float(p.iloc[0 if which == "best" else -1]["usage_index"])


def province_spread(c: Ctx) -> float:
    p = _provinces(c)
    return float(p["usage_index"].max() / p["usage_index"].min())


def lowest_province_col(c: Ctx, col: str) -> float:
    return float(_provinces(c).iloc[-1][col])


def vs(c: Ctx, geo: str, metric: str, col: str) -> float:
    v = c.m["vs_rest"]
    row = v[(v["source"] == "claude_ai") & (v["geo_id"] == geo) & (v["metric"] == metric)].iloc[0]
    return float(row[col])


def _focus_requests(c: Ctx) -> pd.DataFrame:
    r = c.m["request_mix"]
    return r[r["geo_id"] == FOCUS_COUNTRY]


def top_request(c: Ctx, direction: str) -> str:
    r = _focus_requests(c)
    if direction == "over":
        r = r[r["lq_lo"] > 1].sort_values("lq", ascending=False)
    else:
        r = r[r["lq_hi"] < 1].sort_values("lq")
    return str(r.iloc[0]["cluster"]) if len(r) else "none"


def request_col(c: Ctx, cluster: str, col: str) -> float:
    r = _focus_requests(c)
    row = r[r["cluster"] == cluster]
    return float(row.iloc[0][col]) if len(row) else float("nan")


def lens_count(c: Ctx, direction: str) -> int:
    r = _focus_requests(c)
    r = r[r["is_finance_lens"]]
    return int((r["lq_lo"] > 1).sum() if direction == "over" else (r["lq_hi"] < 1).sum())


def lens_total(c: Ctx) -> int:
    return int(_focus_requests(c)["is_finance_lens"].sum())


def lens_names(c: Ctx, direction: str) -> str:
    r = _focus_requests(c)
    r = r[r["is_finance_lens"]]
    r = r[r["lq_lo"] > 1] if direction == "over" else r[r["lq_hi"] < 1]
    return "; ".join(sorted(r["cluster"]))


def gap(c: Ctx, metric: str, col: str) -> float:
    g = c.m["platform_gap"].set_index("metric")
    return float(g.loc[metric, col])


def group13(c: Ctx, col: str):
    f = c.m["function_exposure"].set_index("soc_group")
    v = f.loc["13", col]
    return str(v) if isinstance(v, str) else float(v)


def n_groups(c: Ctx) -> int:
    return len(c.m["function_exposure"])


def top_group(c: Ctx) -> str:
    f = c.m["function_exposure"]
    return str(f.sort_values(["rank_by_mean", "soc_group"]).iloc[0]["soc_name"])


@dataclass
class Readout:
    markdown: str
    facts: pd.DataFrame
    verified: bool
    n_facts: int = 0
    mismatches: list = field(default_factory=list)


class _Builder:
    def __init__(self, ctx: Ctx):
        self.ctx, self.facts = ctx, []

    def f(self, label: str, fn: Callable[[Ctx], object], fmt: str = "{:.1f}") -> str:
        value = fn(self.ctx)
        self.facts.append({"label": label, "fn": fn, "value": value})
        return value if isinstance(value, str) else fmt.format(value)

    def raw(self, label: str, fn: Callable[[Ctx], object]):
        value = fn(self.ctx)
        self.facts.append({"label": label, "fn": fn, "value": value})
        return value


def _pts(x: str) -> str:
    return x.lstrip("+-")


def _ordinal(n: int) -> str:
    suffix = "th" if 10 <= n % 100 <= 20 else {1: "st", 2: "nd", 3: "rd"}.get(n % 10, "th")
    return f"{n}{suffix}"


def build_readout(sut: Ctx, ref: Ctx) -> Readout:
    b = _Builder(sut)
    pct = "{:.1f}"

    n_c = b.f("countries in the index", n_countries, "{:d}")
    rank = b.f("Canada's rank on usage index", focus_rank, "{:d}")
    idx = b.f("Canada usage index", lambda c: focus(c, "usage_index"), "{:.2f}")
    idx_lo = b.f("Canada usage index, lower bound", lambda c: focus(c, "usage_index_lo"), "{:.2f}")
    idx_hi = b.f("Canada usage index, upper bound", lambda c: focus(c, "usage_index_hi"), "{:.2f}")
    conv = b.f("Canada sampled conversations", lambda c: focus(c, "conversations"), "{:,.0f}")
    top_c = b.f("highest-index country", top_country)
    top_i = b.f("highest-index country, index", top_country_index, "{:.2f}")

    best_p = b.f("highest-index province", lambda c: province_name(c, "best"))
    best_i = b.f("highest-index province, index", lambda c: province_index(c, "best"), "{:.2f}")
    worst_p = b.f("lowest-index province", lambda c: province_name(c, "worst"))
    worst_i = b.f("lowest-index province, index", lambda c: province_index(c, "worst"), "{:.2f}")
    worst_lo = b.f("lowest-index province, lower bound", lambda c: lowest_province_col(c, "usage_index_lo"), "{:.2f}")
    worst_hi = b.f("lowest-index province, upper bound", lambda c: lowest_province_col(c, "usage_index_hi"), "{:.2f}")
    spread = b.f("province spread (highest / lowest)", province_spread, "{:.1f}")

    w_ca = b.f("Canada work share (%)", lambda c: 100 * vs(c, FOCUS_COUNTRY, "work_share", "share"), pct)
    w_row = b.f("rest-of-world work share (%)", lambda c: 100 * vs(c, FOCUS_COUNTRY, "work_share", "share_rest"), pct)
    w_diff = b.f("work share gap (points)", lambda c: 100 * vs(c, FOCUS_COUNTRY, "work_share", "diff"), "{:+.1f}")
    w_lo = b.f("work share gap, lower (points)", lambda c: 100 * vs(c, FOCUS_COUNTRY, "work_share", "diff_lo"), "{:+.1f}")
    w_hi = b.f("work share gap, upper (points)", lambda c: 100 * vs(c, FOCUS_COUNTRY, "work_share", "diff_hi"), "{:+.1f}")
    c_diff = b.f("coursework share gap (points)", lambda c: 100 * vs(c, FOCUS_COUNTRY, "coursework_share", "diff"), "{:+.1f}")
    a_ca = b.f("Canada automation share (%)", lambda c: 100 * vs(c, FOCUS_COUNTRY, "automation_share", "share"), pct)
    a_row = b.f("rest-of-world automation share (%)", lambda c: 100 * vs(c, FOCUS_COUNTRY, "automation_share", "share_rest"), pct)
    s_ca = b.f("Canada classified success rate (%)", lambda c: 100 * vs(c, FOCUS_COUNTRY, "success_rate", "share"), pct)
    s_row = b.f("rest-of-world classified success rate (%)", lambda c: 100 * vs(c, FOCUS_COUNTRY, "success_rate", "share_rest"), pct)
    s_lo = b.f("success gap, lower (points)", lambda c: 100 * vs(c, FOCUS_COUNTRY, "success_rate", "diff_lo"), "{:+.1f}")
    s_hi = b.f("success gap, upper (points)", lambda c: 100 * vs(c, FOCUS_COUNTRY, "success_rate", "diff_hi"), "{:+.1f}")

    over = b.raw("most over-indexed request category", lambda c: top_request(c, "over"))
    under = b.raw("most under-indexed request category", lambda c: top_request(c, "under"))
    over_lq = b.f("over-indexed category, index", lambda c: request_col(c, over, "lq"), "{:.2f}")
    over_lo = b.f("over-indexed category, lower bound", lambda c: request_col(c, over, "lq_lo"), "{:.2f}")
    over_hi = b.f("over-indexed category, upper bound", lambda c: request_col(c, over, "lq_hi"), "{:.2f}")
    under_lq = b.f("under-indexed category, index", lambda c: request_col(c, under, "lq"), "{:.2f}")
    under_lo = b.f("under-indexed category, lower bound", lambda c: request_col(c, under, "lq_lo"), "{:.2f}")
    under_hi = b.f("under-indexed category, upper bound", lambda c: request_col(c, under, "lq_hi"), "{:.2f}")
    n_lens = b.f("finance-lens categories", lens_total, "{:d}")
    lens_over = b.f("finance-lens categories that over-index", lambda c: lens_count(c, "over"), "{:d}")
    lens_under = b.f("finance-lens categories that under-index", lambda c: lens_count(c, "under"), "{:d}")
    lens_over_names = b.raw("finance-lens categories that over-index (names)", lambda c: lens_names(c, "over"))
    lens_under_names = b.raw("finance-lens categories that under-index (names)", lambda c: lens_names(c, "under"))

    g_w_chat = b.f("Claude.ai work share, global (%)", lambda c: 100 * gap(c, "work_share", "claude_ai_share"), pct)
    g_w_api = b.f("API work share, global (%)", lambda c: 100 * gap(c, "work_share", "api_share"), pct)
    g_a_chat = b.f("Claude.ai automation share, global (%)", lambda c: 100 * gap(c, "automation_share", "claude_ai_share"), pct)
    g_a_api = b.f("API automation share, global (%)", lambda c: 100 * gap(c, "automation_share", "api_share"), pct)
    g_s_chat = b.f("Claude.ai classified success rate, global (%)", lambda c: 100 * gap(c, "success_rate", "claude_ai_share"), pct)
    g_s_api = b.f("API classified success rate, global (%)", lambda c: 100 * gap(c, "success_rate", "api_share"), pct)

    r13 = b.f("Business and Financial Operations rank", lambda c: group13(c, "rank_by_mean"), "{:.0f}")
    n_g = b.f("occupation groups", n_groups, "{:d}")
    m13 = b.f("Business and Financial Operations mean exposure", lambda c: group13(c, "mean_exposure"), "{:.3f}")
    e13 = b.f("Business and Financial Operations share with any exposure (%)", lambda c: 100 * group13(c, "share_with_exposure"), "{:.0f}")
    occ13 = b.f("most exposed occupation in Business and Financial Operations", lambda c: group13(c, "most_exposed_occupation"))
    occ13_v = b.f("its exposure", lambda c: group13(c, "max_exposure"), "{:.2f}")
    top_g = b.f("highest-exposure occupation group", top_group)

    def sentence_direction(diff: str, more: str, less: str) -> str:
        return more if float(diff) > 0 else less

    work_dir = "lower" if float(w_diff) < 0 else "higher"
    course_dir = sentence_direction(c_diff, "higher", "lower")
    auto_dir = "less" if float(a_ca) < float(a_row) else "more"
    succ_clear = float(s_lo) > 0 or float(s_hi) < 0
    succ_text = (f"the gap is statistically clear (interval {s_lo} to {s_hi} points)" if succ_clear
                 else f"the gap is within sampling noise (interval {s_lo} to {s_hi} points)")
    lens_text = (f"Of the {n_lens} finance-adjacent categories I flagged, {lens_over} over-index"
                 + (f' ("{lens_over_names}")' if int(lens_over) else "")
                 + f" and {lens_under} under-index" + (f' ("{lens_under_names}")' if int(lens_under) else "") + ".")
    over_text = (f"The most over-represented request category in Canada is \"{over}\" (index {over_lq}, band {over_lo} to {over_hi})."
                 if over != "none" else "No request category over-indexes with a band that excludes 1.")
    under_text = (f"The most under-represented is \"{under}\" (index {under_lq}, band {under_lo} to {under_hi})."
                  if under != "none" else "")

    md = f"""# Canada GenAI usage brief

Week of 5 to 12 February 2026. Source: Anthropic Economic Index, roughly one million sampled Claude.ai conversations and one million first-party API conversations. Every figure below comes from the SQL metrics and was re-derived by a separate implementation before this brief was written.

## What stands out

**1. Canada is a high-use market.** Its {conv} sampled conversations put it {_ordinal(int(rank))} of {n_c} countries on usage per resident (index {idx}, 95% band {idx_lo} to {idx_hi}; 1.0 is the pooled average of those countries). {top_c} is highest at {top_i}.
*Reading it:* the index says how much a place uses the product relative to its population, not what share of people use it.

**2. Use per resident varies {spread}-fold across provinces.** {best_p} is highest ({best_i}) and {worst_p} lowest ({worst_i}, band {worst_lo} to {worst_hi}). Provinces with fewer than 200 sampled conversations are left out.
*For an internal rollout:* a regional gap this size is a reason to check whether local enablement differs before assuming a product problem. That is a hypothesis to test, not a finding.

**3. Canadian use leans away from work.** {w_ca}% of Canadian conversations are work-related against {w_row}% elsewhere, which is {_pts(w_diff)} points {work_dir} (95% interval {w_lo} to {w_hi}). Coursework share is {_pts(c_diff)} points {course_dir}, and the automation pattern, where the person delegates a task and reviews the result, is {auto_dir} common ({a_ca}% against {a_row}%). Classified task success is {s_ca}% against {s_row}%; {succ_text}.
*For an internal rollout:* consumer habits in Canada point toward personal and study use, so work-specific examples are the thing an enterprise assistant has to supply. Again a hypothesis.

**4. Some request types over- and under-index.** {over_text} {under_text} {lens_text}

**5. API usage looks different from chat.** In the first-party API sample {g_w_api}% of conversations are work-related (Claude.ai: {g_w_chat}%), {g_a_api}% follow an automation pattern ({g_a_chat}%), and {g_s_api}% are classified as successful ({g_s_chat}%). A deployed, programmatic use case is a different thing to measure than a person chatting.

**6. Exposure differs by occupation group.** Business and Financial Operations ranks {r13} of {n_g} groups on mean observed exposure ({m13}); {e13}% of its occupations show any exposure. Its most exposed occupation is {occ13} ({occ13_v}). {top_g} ranks first.

## Read before quoting

- These are sampled, model-classified conversations, not a census of users. Small geographies carry wide bands.
- "Success" is a classifier label assigned to a conversation, not an outcome reported by the person.
- "Rest of world" means every other sampled conversation, including those with no usable country.
- One week of data: nothing here shows change over time.
"""
    return _verify(md, b.facts, ref)


def _verify(markdown: str, facts: list[dict], ref: Ctx) -> Readout:
    rows = []
    for f in facts:
        r = f["fn"](ref)
        v = f["value"]
        ok = (v == r) if isinstance(v, str) else bool(np.isclose(v, r, rtol=1e-9, atol=1e-9, equal_nan=True))
        rows.append({"label": f["label"], "value": v, "reference": r, "match": ok})
    df = pd.DataFrame(rows)
    bad = df.loc[~df["match"], "label"].tolist()
    stamp = (f"\n---\n*Verification: {len(df)} of {len(df)} figures matched the independent implementation.*\n"
             if not bad else f"\n---\n**NOT VERIFIED. Do not use.** {len(bad)} figure(s) disagree with the independent "
                              f"implementation: {', '.join(bad)}.\n")
    return Readout(markdown=markdown + stamp, facts=df, verified=not bad, n_facts=len(df), mismatches=bad)
