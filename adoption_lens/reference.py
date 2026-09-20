from __future__ import annotations

import numpy as np
import pandas as pd

from .config import AUTOMATION, AUGMENTATION, MIN_CATEGORY_COUNT, MIN_CONVERSATIONS, SUCCESS, USE_CASES, Z
from .data import Inputs


def wilson(x: pd.Series, n: pd.Series, z: float = Z) -> tuple[pd.Series, pd.Series]:
    p = x / n
    denom = 1 + z ** 2 / n
    center = (p + z ** 2 / (2 * n)) / denom
    half = z * np.sqrt(p * (1 - p) / n + z ** 2 / (4 * n ** 2)) / denom
    return center - half, center + half


def _prepare(aei: pd.DataFrame) -> pd.DataFrame:
    a = aei.copy()
    a["cluster"] = a["cluster_name"].fillna("").astype(str)
    a["geo_id"] = a["geo_id"].astype(str)
    a["unclassified"] = a["geo_id"].isin(["NONE", "not_classified"]) | a["geo_id"].str.endswith("-not_classified")
    a["geo_level"] = a["geography"].astype(str).replace({"country-state": "subregion"})
    prefix = a["geo_id"].str.split("-").str[0]
    a["country_code"] = np.where(a["geo_level"] == "subregion", prefix, np.where(a["geo_level"] == "country", a["geo_id"], None))
    return a


def _geo_usage(a: pd.DataFrame, inp: Inputs) -> pd.DataFrame:
    use = a[(a["source"] == "claude_ai") & (a["variable"] == "usage_count") & a["facet"].isin(["country", "country-state"])
            & ~a["unclassified"]][["geo_id", "geo_level", "value"]].rename(columns={"value": "conversations"})
    country_pop = inp.countries.set_index("iso2")["population"]
    province_pop = inp.provinces.set_index("geo_id")["population"]
    known_country = use.loc[use["geo_level"] == "country", "conversations"].sum()
    known_province = use.loc[use["geo_id"].isin(province_pop.index) & (use["geo_level"] == "subregion"), "conversations"].sum()

    countries = use[(use["geo_level"] == "country") & (use["conversations"] >= MIN_CONVERSATIONS)].copy()
    countries["population"] = countries["geo_id"].map(country_pop).astype("float64")
    countries = countries[countries["population"] > 0]
    provinces = use[(use["geo_level"] == "subregion") & use["geo_id"].isin(province_pop.index)
                    & (use["conversations"] >= MIN_CONVERSATIONS)].copy()
    provinces["population"] = provinces["geo_id"].map(province_pop)

    out = []
    for pool, known in ((countries, known_country), (provinces, known_province)):
        pool = pool.copy()
        pooled_rate = pool["conversations"].sum() / pool["population"].sum()
        pool["share_of_known"] = pool["conversations"] / known
        pool["per_100k"] = pool["conversations"] * 100000.0 / pool["population"]
        pool["usage_index"] = (pool["conversations"] / pool["population"]) / pooled_rate
        margin = Z / np.sqrt(pool["conversations"])
        pool["usage_index_lo"] = pool["usage_index"] * (1 - margin)
        pool["usage_index_hi"] = pool["usage_index"] * (1 + margin)
        out.append(pool)
    res = pd.concat(out, ignore_index=True)
    res["population"] = res["population"].astype("int64")
    return res[["geo_id", "geo_level", "conversations", "population", "share_of_known", "per_100k", "usage_index",
                "usage_index_lo", "usage_index_hi"]].sort_values("geo_id").reset_index(drop=True)


def _shares(a: pd.DataFrame) -> pd.DataFrame:
    keys = ["source", "geo_id", "geo_level"]
    geo_lookup = a[keys + ["country_code"]].drop_duplicates(keys).set_index(keys)["country_code"]
    families = [
        ("use_case", "use_case_count", set(USE_CASES), {"work"}, "work_share"),
        ("use_case", "use_case_count", set(USE_CASES), {"coursework"}, "coursework_share"),
        ("collaboration", "collaboration_count", set(AUTOMATION) | set(AUGMENTATION), set(AUTOMATION), "automation_share"),
        ("task_success", "task_success_count", set(SUCCESS), {"yes"}, "success_rate"),
    ]
    parts = []
    for facet, variable, classified, numerator, metric in families:
        d = a[(a["facet"] == facet) & (a["variable"] == variable) & ~a["unclassified"]]
        n = d["value"].where(d["cluster"].isin(classified), 0.0).groupby([d[k] for k in keys]).sum()
        x = d["value"].where(d["cluster"].isin(numerator), 0.0).groupby([d[k] for k in keys]).sum()
        t = pd.DataFrame({"x": x, "n": n}).reset_index()
        t["metric"] = metric
        parts.append(t)
    s = pd.concat(parts, ignore_index=True)
    s = s[s["n"] >= MIN_CONVERSATIONS].copy()
    s["country_code"] = [geo_lookup.get((r.source, r.geo_id, r.geo_level)) for r in s.itertuples()]
    s["share"] = s["x"] / s["n"]
    s["lo"], s["hi"] = wilson(s["x"], s["n"])
    return s[["source", "geo_id", "geo_level", "country_code", "metric", "x", "n", "share", "lo", "hi"]]


def _vs_rest(shares: pd.DataFrame) -> pd.DataFrame:
    child = shares[shares["geo_level"].isin(["country", "subregion"])].copy()
    child["parent_id"] = np.where(child["geo_level"] == "country", "GLOBAL", child["country_code"])
    parent = shares[["source", "metric", "geo_id", "x", "n"]].rename(columns={"geo_id": "parent_id", "x": "px", "n": "pn"})
    m = child.merge(parent, on=["source", "metric", "parent_id"])
    m = m[m["pn"] - m["n"] >= MIN_CONVERSATIONS].copy()
    m["x_rest"] = m["px"] - m["x"]
    m["n_rest"] = m["pn"] - m["n"]
    m["share_rest"] = m["x_rest"] / m["n_rest"]
    m["diff"] = m["share"] - m["share_rest"]
    se = np.sqrt(m["share"] * (1 - m["share"]) / m["n"] + m["share_rest"] * (1 - m["share_rest"]) / m["n_rest"])
    m["diff_lo"] = m["diff"] - Z * se
    m["diff_hi"] = m["diff"] + Z * se
    return m[["source", "geo_id", "metric", "parent_id", "x", "n", "share", "x_rest", "n_rest", "share_rest", "diff",
              "diff_lo", "diff_hi"]].sort_values(["source", "geo_id", "metric"]).reset_index(drop=True)


def _request_mix(a: pd.DataFrame, inp: Inputs) -> pd.DataFrame:
    d = a[(a["facet"] == "request") & (a["level"] == 2) & (a["variable"] == "request_count")
          & (a["cluster"] != "not_classified") & ~a["unclassified"]]
    req = d[["source", "geo_id", "geo_level", "country_code", "cluster", "value"]].rename(columns={"value": "x"})
    total = req.groupby(["source", "geo_id"])["x"].sum().rename("n").reset_index()
    provinces = set(inp.provinces["geo_id"])
    scope = req.merge(total, on=["source", "geo_id"])
    scope = scope[(scope["source"] == "claude_ai") & (scope["n"] >= MIN_CONVERSATIONS)
                  & ((scope["geo_level"] == "country") | ((scope["geo_level"] == "subregion") & scope["geo_id"].isin(provinces)))].copy()
    scope["parent_id"] = np.where(scope["geo_level"] == "country", "GLOBAL", scope["country_code"])
    parent_x = req.rename(columns={"geo_id": "parent_id", "x": "px"})[["source", "parent_id", "cluster", "px"]]
    parent_n = total.rename(columns={"geo_id": "parent_id", "n": "pn"})
    m = scope.merge(parent_x, on=["source", "parent_id", "cluster"]).merge(parent_n, on=["source", "parent_id"])
    m = m[(m["px"] > m["x"]) & (m["pn"] > m["n"]) & (m["x"] >= MIN_CATEGORY_COUNT)].copy()
    m["x_rest"] = m["px"] - m["x"]
    m["n_rest"] = m["pn"] - m["n"]
    m["share"] = m["x"] / m["n"]
    m["share_rest"] = m["x_rest"] / m["n_rest"]
    m["lq"] = m["share"] / m["share_rest"]
    se = np.sqrt(1.0 / m["x"] - 1.0 / m["n"] + 1.0 / m["x_rest"] - 1.0 / m["n_rest"])
    m["lq_lo"] = np.exp(np.log(m["lq"]) - Z * se)
    m["lq_hi"] = np.exp(np.log(m["lq"]) + Z * se)
    m["is_finance_lens"] = m["cluster"].isin(set(inp.finance_lens["cluster"]))
    return m[["source", "geo_id", "parent_id", "cluster", "x", "n", "share", "x_rest", "n_rest", "share_rest", "lq",
              "lq_lo", "lq_hi", "is_finance_lens"]].sort_values(["source", "geo_id", "cluster"]).reset_index(drop=True)


def _platform_gap(shares: pd.DataFrame) -> pd.DataFrame:
    g = shares[shares["geo_id"] == "GLOBAL"]
    a = g[g["source"] == "claude_ai"].set_index("metric")
    b = g[g["source"] == "api"].set_index("metric")
    common = a.index.intersection(b.index)
    out = pd.DataFrame({
        "claude_ai_share": a.loc[common, "share"], "claude_ai_n": a.loc[common, "n"],
        "api_share": b.loc[common, "share"], "api_n": b.loc[common, "n"],
    })
    out["diff"] = out["api_share"] - out["claude_ai_share"]
    se = np.sqrt(out["claude_ai_share"] * (1 - out["claude_ai_share"]) / out["claude_ai_n"]
                 + out["api_share"] * (1 - out["api_share"]) / out["api_n"])
    out["diff_lo"] = out["diff"] - Z * se
    out["diff_hi"] = out["diff"] + Z * se
    return out.reset_index().sort_values("metric").reset_index(drop=True)


def _function_exposure(inp: Inputs) -> pd.DataFrame:
    j = inp.job_exposure.copy()
    j["soc_group"] = j["occ_code"].astype(str).str[:2]
    rows = []
    for group, g in j.groupby("soc_group"):
        top = g.sort_values(["observed_exposure", "title"], ascending=[False, True]).iloc[0]
        rows.append({
            "soc_group": group,
            "occupations": len(g),
            "mean_exposure": g["observed_exposure"].mean(),
            "median_exposure": float(np.quantile(g["observed_exposure"], 0.5)),
            "share_with_exposure": float((g["observed_exposure"] > 0).mean()),
            "max_exposure": g["observed_exposure"].max(),
            "most_exposed_occupation": top["title"],
        })
    out = pd.DataFrame(rows).merge(inp.soc_groups.rename(columns={"name": "soc_name"}), on="soc_group")
    out["rank_by_mean"] = out["mean_exposure"].rank(method="min", ascending=False).astype(int)
    return out[["soc_group", "soc_name", "occupations", "mean_exposure", "median_exposure", "share_with_exposure",
                "max_exposure", "most_exposed_occupation", "rank_by_mean"]].sort_values("soc_group").reset_index(drop=True)


def reference_metrics(inp: Inputs) -> dict[str, pd.DataFrame]:
    a = _prepare(inp.aei)
    shares = _shares(a)
    return {
        "geo_usage": _geo_usage(a, inp),
        "shares": shares.sort_values(["source", "geo_id", "metric"]).reset_index(drop=True),
        "vs_rest": _vs_rest(shares),
        "request_mix": _request_mix(a, inp),
        "platform_gap": _platform_gap(shares),
        "function_exposure": _function_exposure(inp),
    }
