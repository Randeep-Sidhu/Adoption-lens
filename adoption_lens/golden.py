"""A small hand-built dataset in the real file layout, with expected results worked out from first principles.

Each geography exists to exercise one rule: unclassified geographies (NONE, not_classified, CA-not_classified),
the minimum-sample guard (XX, CA-NB), a country with no population (ZZ), a state whose parent is a country
(US-CA), a category below the minimum count (D in CA), a tie in the exposure ranking (groups 13 and 43),
a subregion that is almost all of its country (QQ-A, too little left for a comparison group), and a use-case 'none'
bucket that must stay out of the denominator.
"""
from __future__ import annotations

import math

import pandas as pd

from .data import Inputs

PLATFORM = {"claude_ai": "Claude AI (Free, Pro, and Max)", "api": "1P API"}
A = "Assist with software development, debugging, and programming across multiple platforms"
B = "Provide financial information, tax guidance, and consumer purchase assistance"
C = "Assist with academic research, scientific writing, and educational content creation"
D = "Analyze political media, misinformation, and criminal investigations"

USAGE = {"CA": 1000, "US": 3000, "GB": 500, "XX": 100, "ZZ": 800, "QQ": 300, "NONE": 50, "not_classified": 450}
SUBREGION_USAGE = {"CA-ON": 500, "CA-BC": 300, "CA-NB": 180, "CA-not_classified": 20, "US-CA": 3000, "QQ-A": 250, "QQ-B": 50}

CATEGORICAL: dict[tuple[str, str, str], dict[str, float]] = {
    ("claude_ai", "GLOBAL", "use_case"): {"work": 45000, "personal": 42000, "coursework": 12000, "none": 30},
    ("claude_ai", "CA", "use_case"): {"work": 600, "personal": 300, "coursework": 100},
    ("claude_ai", "CA-ON", "use_case"): {"work": 300, "personal": 150, "coursework": 50},
    ("claude_ai", "CA-BC", "use_case"): {"work": 150, "personal": 100, "coursework": 50},
    ("claude_ai", "CA-NB", "use_case"): {"work": 100, "personal": 50, "coursework": 30},
    ("claude_ai", "US", "use_case"): {"work": 1500, "personal": 1000, "coursework": 500},
    ("claude_ai", "US-CA", "use_case"): {"work": 700, "personal": 400, "coursework": 200},
    ("claude_ai", "GB", "use_case"): {"work": 200, "personal": 200, "coursework": 100},
    ("claude_ai", "XX", "use_case"): {"work": 40, "personal": 40, "coursework": 20},
    ("claude_ai", "ZZ", "use_case"): {"work": 400, "personal": 300, "coursework": 100},
    ("claude_ai", "QQ", "use_case"): {"work": 150, "personal": 100, "coursework": 50},
    ("claude_ai", "QQ-A", "use_case"): {"work": 120, "personal": 90, "coursework": 40},
    ("api", "GLOBAL", "use_case"): {"work": 7400, "personal": 2000, "coursework": 600, "none": 5},
    ("claude_ai", "GLOBAL", "collaboration"): {"directive": 30000, "feedback loop": 12000, "learning": 22000,
                                               "task iteration": 26000, "validation": 5000, "none": 3000,
                                               "not_classified": 500},
    ("claude_ai", "CA", "collaboration"): {"directive": 300, "feedback loop": 100, "learning": 250,
                                           "task iteration": 250, "validation": 100, "none": 40, "not_classified": 10},
    ("claude_ai", "CA-ON", "collaboration"): {"directive": 150, "feedback loop": 50, "learning": 125,
                                              "task iteration": 125, "validation": 50},
    ("claude_ai", "US", "collaboration"): {"directive": 900, "feedback loop": 300, "learning": 800,
                                           "task iteration": 800, "validation": 200},
    ("api", "GLOBAL", "collaboration"): {"directive": 5800, "feedback loop": 900, "learning": 400,
                                         "task iteration": 900, "validation": 300, "none": 1500},
    ("claude_ai", "GLOBAL", "task_success"): {"yes": 70000, "no": 30000, "not_classified": 100},
    ("claude_ai", "CA", "task_success"): {"yes": 720, "no": 280, "not_classified": 5},
    ("claude_ai", "CA-ON", "task_success"): {"yes": 370, "no": 130},
    ("api", "GLOBAL", "task_success"): {"yes": 5000, "no": 5000, "not_classified": 1},
    ("claude_ai", "GLOBAL", "request"): {A: 40000, B: 10000, C: 45000, D: 2000, "not_classified": 5000},
    ("claude_ai", "CA", "request"): {A: 300, B: 120, C: 500, D: 20, "not_classified": 60},
    ("claude_ai", "CA-ON", "request"): {A: 150, B: 60, C: 250, D: 10},
    ("claude_ai", "US", "request"): {A: 1500, B: 300, C: 1100, D: 100},
    ("claude_ai", "GB", "request"): {A: 100, B: 40, C: 300, D: 30},
    ("api", "GLOBAL", "request"): {"Assist with software development, debugging, and code management tasks": 6000,
                                   "Automate business operations and develop enterprise software systems": 4000},
}

OCCUPATIONS = [
    ("13-2051", "Financial and Investment Analysts", 0.5), ("13-2011", "Accountants and Auditors", 0.125),
    ("13-1111", "Management Analysts", 0.125),
    ("15-1251", "Computer Programmers", 0.75), ("15-1252", "Software Developers", 0.5),
    ("15-1211", "Computer Systems Analysts", 0.0),
    ("43-9021", "Data Entry Keyers", 0.625), ("43-9111", "Statistical Assistants", 0.125),
    ("43-4051", "Customer Service Representatives", 0.0),
    ("47-2061", "Construction Laborers", 0.0), ("47-2111", "Electricians", 0.0), ("47-2152", "Plumbers", 0.0),
]


def _geography(geo_id: str) -> str:
    if geo_id == "GLOBAL":
        return "global"
    return "country-state" if "-" in geo_id else "country"


def _row(source, geo_id, facet, level, variable, cluster, value):
    return {"geo_id": geo_id, "geography": _geography(geo_id), "date_start": pd.Timestamp("2026-02-05"),
            "date_end": pd.Timestamp("2026-02-12"), "platform_and_product": PLATFORM[source], "facet": facet,
            "level": level, "variable": variable, "cluster_name": cluster, "value": float(value), "source": source}


def golden_aei() -> pd.DataFrame:
    rows = []
    global_sample = sum(CATEGORICAL[("claude_ai", "GLOBAL", "use_case")].values())
    for geo, n in USAGE.items():
        rows += [_row("claude_ai", geo, "country", 0, "usage_count", None, n),
                 _row("claude_ai", geo, "country", 0, "usage_pct", None, 100.0 * n / global_sample)]
    for geo, n in SUBREGION_USAGE.items():
        parent = USAGE[geo.split("-")[0]]
        rows += [_row("claude_ai", geo, "country-state", 0, "usage_count", None, n),
                 _row("claude_ai", geo, "country-state", 0, "usage_pct", None, 100.0 * n / parent)]
    for (source, geo, facet), counts in CATEGORICAL.items():
        level = 2 if facet == "request" else 0
        total = sum(counts.values())
        for cluster, n in counts.items():
            rows.append(_row(source, geo, facet, level, f"{facet}_count", cluster, n))
            rows.append(_row(source, geo, facet, level, f"{facet}_pct", cluster, 100.0 * n / total))
    df = pd.DataFrame(rows)
    return df[["source", "geo_id", "geography", "date_start", "date_end", "platform_and_product", "facet", "level",
               "variable", "cluster_name", "value"]]


def golden_inputs() -> Inputs:
    countries = pd.DataFrame([
        {"iso2": "CA", "iso3": "CAN", "country": "Canada", "population": 40_000_000, "continent": "NA"},
        {"iso2": "US", "iso3": "USA", "country": "United States", "population": 320_000_000, "continent": "NA"},
        {"iso2": "GB", "iso3": "GBR", "country": "United Kingdom", "population": 60_000_000, "continent": "EU"},
        {"iso2": "XX", "iso3": "XXX", "country": "Xland", "population": 1_000_000, "continent": "EU"},
    ])
    provinces = pd.DataFrame([
        {"geo_id": "CA-ON", "name": "Ontario", "population": 16_000_000},
        {"geo_id": "CA-BC", "name": "British Columbia", "population": 5_000_000},
        {"geo_id": "CA-NB", "name": "New Brunswick", "population": 800_000},
    ])
    soc = pd.DataFrame({"soc_group": ["13", "15", "43", "47"],
                        "name": ["Business and Financial Operations", "Computer and Mathematical",
                                 "Office and Administrative Support", "Construction and Extraction"]})
    jobs = pd.DataFrame(OCCUPATIONS, columns=["occ_code", "title", "observed_exposure"])
    return Inputs(aei=golden_aei(), countries=countries, provinces=provinces,
                  canada_population=int(provinces["population"].sum()), soc_groups=soc, job_exposure=jobs,
                  finance_lens=pd.DataFrame({"cluster": [B]}),
                  territories=pd.DataFrame({"parent": [], "subregion": [], "territory": []}, dtype="string"))


def _wilson(x: float, n: float, z: float = 1.96) -> tuple[float, float]:
    p = x / n
    centre = (p + z * z / (2 * n)) / (1 + z * z / n)
    half = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / (1 + z * z / n)
    return centre - half, centre + half


def _level(geo: str) -> str:
    return "global" if geo == "GLOBAL" else ("subregion" if "-" in geo else "country")


def _expected_geo_usage() -> pd.DataFrame:
    country_pop = {"CA": 40_000_000, "US": 320_000_000, "GB": 60_000_000, "XX": 1_000_000}
    province_pop = {"CA-ON": 16_000_000, "CA-BC": 5_000_000, "CA-NB": 800_000}
    rows = []
    known = sum(n for g, n in USAGE.items() if g not in ("NONE", "not_classified"))
    pool = {g: n for g, n in USAGE.items() if n >= 200 and g in country_pop}
    rate = sum(pool.values()) / sum(country_pop[g] for g in pool)
    for g, n in pool.items():
        index = (n / country_pop[g]) / rate
        rows.append((g, "country", n, country_pop[g], n / known, n * 1e5 / country_pop[g], index,
                     index * (1 - 1.96 / math.sqrt(n)), index * (1 + 1.96 / math.sqrt(n))))
    known_p = sum(SUBREGION_USAGE[g] for g in province_pop)
    pool_p = {g: SUBREGION_USAGE[g] for g in province_pop if SUBREGION_USAGE[g] >= 200}
    rate_p = sum(pool_p.values()) / sum(province_pop[g] for g in pool_p)
    for g, n in pool_p.items():
        index = (n / province_pop[g]) / rate_p
        rows.append((g, "subregion", n, province_pop[g], n / known_p, n * 1e5 / province_pop[g], index,
                     index * (1 - 1.96 / math.sqrt(n)), index * (1 + 1.96 / math.sqrt(n))))
    return pd.DataFrame(rows, columns=["geo_id", "geo_level", "conversations", "population", "share_of_known",
                                       "per_100k", "usage_index", "usage_index_lo", "usage_index_hi"])


def _expected_shares() -> pd.DataFrame:
    rows = []
    for (source, geo, facet), c in CATEGORICAL.items():
        if facet == "request":
            continue
        if facet == "use_case":
            n = c["work"] + c["personal"] + c["coursework"]
            pairs = [("work_share", c["work"]), ("coursework_share", c["coursework"])]
        elif facet == "collaboration":
            n = c["directive"] + c["feedback loop"] + c["learning"] + c["task iteration"] + c["validation"]
            pairs = [("automation_share", c["directive"] + c["feedback loop"])]
        else:
            n = c["yes"] + c["no"]
            pairs = [("success_rate", c["yes"])]
        if n < 200:
            continue
        country = None if geo == "GLOBAL" else geo.split("-")[0]
        for metric, x in pairs:
            lo, hi = _wilson(x, n)
            rows.append((source, geo, _level(geo), country, metric, x, n, x / n, lo, hi))
    return pd.DataFrame(rows, columns=["source", "geo_id", "geo_level", "country_code", "metric", "x", "n", "share",
                                       "lo", "hi"])


def _expected_vs_rest(shares: pd.DataFrame) -> pd.DataFrame:
    lookup = {(r.source, r.geo_id, r.metric): r for r in shares.itertuples()}
    rows = []
    for r in shares.itertuples():
        if r.geo_level == "global":
            continue
        parent = "GLOBAL" if r.geo_level == "country" else r.country_code
        p = lookup.get((r.source, parent, r.metric))
        if p is None or p.n - r.n < 200:
            continue
        x_rest, n_rest = p.x - r.x, p.n - r.n
        rest = x_rest / n_rest
        diff = r.share - rest
        se = math.sqrt(r.share * (1 - r.share) / r.n + rest * (1 - rest) / n_rest)
        rows.append((r.source, r.geo_id, r.metric, parent, r.x, r.n, r.share, x_rest, n_rest, rest, diff,
                     diff - 1.96 * se, diff + 1.96 * se))
    return pd.DataFrame(rows, columns=["source", "geo_id", "metric", "parent_id", "x", "n", "share", "x_rest",
                                       "n_rest", "share_rest", "diff", "diff_lo", "diff_hi"])


def _expected_request_mix() -> pd.DataFrame:
    def classified(geo):
        return {k: v for k, v in CATEGORICAL[("claude_ai", geo, "request")].items() if k != "not_classified"}

    glob = classified("GLOBAL")
    glob_n = sum(glob.values())
    rows = []
    for geo, parent in (("CA", "GLOBAL"), ("US", "GLOBAL"), ("GB", "GLOBAL"), ("CA-ON", "CA")):
        cats = classified(geo)
        par = classified(parent)
        n, par_n = sum(cats.values()), sum(par.values())
        for cluster, x in cats.items():
            if x < 30 or par[cluster] <= x:
                continue
            x_rest, n_rest = par[cluster] - x, par_n - n
            share, rest = x / n, x_rest / n_rest
            lq = share / rest
            se = math.sqrt(1 / x - 1 / n + 1 / x_rest - 1 / n_rest)
            rows.append(("claude_ai", geo, parent, cluster, x, n, share, x_rest, n_rest, rest, lq,
                         math.exp(math.log(lq) - 1.96 * se), math.exp(math.log(lq) + 1.96 * se), cluster == B))
    assert glob_n > 0
    return pd.DataFrame(rows, columns=["source", "geo_id", "parent_id", "cluster", "x", "n", "share", "x_rest",
                                       "n_rest", "share_rest", "lq", "lq_lo", "lq_hi", "is_finance_lens"])


def _expected_platform_gap(shares: pd.DataFrame) -> pd.DataFrame:
    g = shares[shares["geo_id"] == "GLOBAL"]
    rows = []
    for metric in sorted(set(g["metric"])):
        a = g[(g["source"] == "claude_ai") & (g["metric"] == metric)].iloc[0]
        b = g[(g["source"] == "api") & (g["metric"] == metric)].iloc[0]
        diff = b.share - a.share
        se = math.sqrt(a.share * (1 - a.share) / a.n + b.share * (1 - b.share) / b.n)
        rows.append((metric, a.share, a.n, b.share, b.n, diff, diff - 1.96 * se, diff + 1.96 * se))
    return pd.DataFrame(rows, columns=["metric", "claude_ai_share", "claude_ai_n", "api_share", "api_n", "diff",
                                       "diff_lo", "diff_hi"])


def _expected_function_exposure() -> pd.DataFrame:
    # group 13: 0.5, 0.125, 0.125  -> mean 0.25, median 0.125, all exposed, max 0.5
    # group 15: 0.75, 0.5, 0.0     -> mean 0.41666.., median 0.5, two of three exposed, max 0.75
    # group 43: 0.625, 0.125, 0.0  -> mean 0.25, median 0.125, two of three exposed, max 0.625
    # group 47: 0.0 x3             -> mean 0, nobody exposed; ties on the top occupation break alphabetically
    # groups 13 and 43 tie on the mean, so both rank 2, group 15 ranks 1 and group 47 ranks 4
    return pd.DataFrame([
        ("13", "Business and Financial Operations", 3, 0.25, 0.125, 1.0, 0.5, "Financial and Investment Analysts", 2),
        ("15", "Computer and Mathematical", 3, 1.25 / 3, 0.5, 2 / 3, 0.75, "Computer Programmers", 1),
        ("43", "Office and Administrative Support", 3, 0.25, 0.125, 2 / 3, 0.625, "Data Entry Keyers", 2),
        ("47", "Construction and Extraction", 3, 0.0, 0.0, 0.0, 0.0, "Construction Laborers", 4),
    ], columns=["soc_group", "soc_name", "occupations", "mean_exposure", "median_exposure", "share_with_exposure",
                "max_exposure", "most_exposed_occupation", "rank_by_mean"])


def golden_expected() -> dict[str, pd.DataFrame]:
    shares = _expected_shares()
    return {
        "geo_usage": _expected_geo_usage(),
        "shares": shares,
        "vs_rest": _expected_vs_rest(shares),
        "request_mix": _expected_request_mix(),
        "platform_gap": _expected_platform_gap(shares),
        "function_exposure": _expected_function_exposure(),
    }
