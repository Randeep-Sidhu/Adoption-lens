from __future__ import annotations

import numpy as np
import pandas as pd

from .warehouse import METRICS

ISSUE_COLUMNS = ["metric", "key", "column", "sut_value", "ref_value", "sut_text", "ref_text", "kind"]


def _normalize(df: pd.DataFrame, keys: list[str]) -> pd.DataFrame:
    out = df.copy()
    for c in out.columns:
        if pd.api.types.is_datetime64_any_dtype(out[c]):
            out[c] = pd.to_datetime(out[c]).astype("datetime64[ns]")
        elif pd.api.types.is_bool_dtype(out[c]) or pd.api.types.is_numeric_dtype(out[c]):
            out[c] = out[c].astype("float64")
        else:
            out[c] = out[c].astype(object).where(out[c].notna(), None)
    return out.sort_values(keys).reset_index(drop=True)


def _fmt(v) -> str:
    if isinstance(v, (float, np.floating)) and float(v).is_integer():
        return str(int(v))
    return str(v)


def _differs(x: pd.Series, y: pd.Series, rtol: float, atol: float) -> np.ndarray:
    if pd.api.types.is_numeric_dtype(x) and pd.api.types.is_numeric_dtype(y):
        return ~np.isclose(x.to_numpy(dtype=float), y.to_numpy(dtype=float), rtol=rtol, atol=atol, equal_nan=True)
    both_na = x.isna() & y.isna()
    return ((x != y) & ~both_na).to_numpy()


def reconcile_metric(name: str, sut: pd.DataFrame, ref: pd.DataFrame, rtol: float = 1e-9,
                     atol: float = 1e-9) -> pd.DataFrame:
    keys = METRICS[name][1]
    a, b = _normalize(sut, keys), _normalize(ref, keys)
    missing = [c for c in a.columns if c not in b.columns]
    if missing:
        raise KeyError(f"reference for {name} lacks columns {missing}")
    merged = a.merge(b, on=keys, how="outer", suffixes=("_sut", "_ref"), indicator=True)
    values = [c for c in a.columns if c not in keys]
    issues: list[dict] = []

    def base(row, **kw):
        d = {"metric": name, "key": "|".join(f"{k}={_fmt(row[k])}" for k in keys), "column": None,
             "sut_value": np.nan, "ref_value": np.nan, "sut_text": None, "ref_text": None}
        d.update(kw)
        return d

    for _, row in merged[merged["_merge"] == "left_only"].iterrows():
        issues.append(base(row, kind="row_only_in_sql"))
    for _, row in merged[merged["_merge"] == "right_only"].iterrows():
        issues.append(base(row, kind="row_missing_in_sql"))
    both = merged[merged["_merge"] == "both"]
    for c in values:
        x, y = both[f"{c}_sut"], both[f"{c}_ref"]
        bad = _differs(x, y, rtol, atol)
        for (_, row), xv, yv in zip(both[bad].iterrows(), x[bad], y[bad]):
            if isinstance(xv, (int, float, np.number)) and isinstance(yv, (int, float, np.number)):
                issues.append(base(row, kind="value_mismatch", column=c, sut_value=float(xv), ref_value=float(yv)))
            else:
                issues.append(base(row, kind="value_mismatch", column=c, sut_text=str(xv), ref_text=str(yv)))
    return pd.DataFrame(issues, columns=ISSUE_COLUMNS)


def reconcile_all(sut: dict[str, pd.DataFrame], ref: dict[str, pd.DataFrame]) -> pd.DataFrame:
    parts = [reconcile_metric(n, sut[n], ref[n]) for n in METRICS]
    parts = [p for p in parts if len(p)]
    return pd.concat(parts, ignore_index=True) if parts else pd.DataFrame(columns=ISSUE_COLUMNS)


def reconciliation_summary(sut: dict[str, pd.DataFrame], ref: dict[str, pd.DataFrame]) -> pd.DataFrame:
    issues = reconcile_all(sut, ref)
    rows = []
    for n, (_, keys) in METRICS.items():
        cells = len(sut[n]) * (len(sut[n].columns) - len(keys))
        bad = int((issues["metric"] == n).sum()) if len(issues) else 0
        rows.append({"metric": n, "rows_sql": len(sut[n]), "rows_reference": len(ref[n]), "cells_compared": cells,
                     "mismatches": bad, "status": "match" if bad == 0 else "MISMATCH"})
    return pd.DataFrame(rows)


def check_invariants(sut: dict[str, pd.DataFrame], inputs) -> pd.DataFrame:
    from .config import MIN_CATEGORY_COUNT

    geo, sh, vr, rq = sut["geo_usage"], sut["shares"], sut["vs_rest"], sut["request_mix"]
    pg, fx = sut["platform_gap"], sut["function_exposure"]
    out: list[dict] = []

    def add(name: str, ok: bool, detail: str = "") -> None:
        out.append({"invariant": name, "passed": bool(ok), "detail": "" if ok else detail})

    add("Shares are between 0 and 1", sh["share"].between(0, 1).all(), "share outside [0, 1]")
    add("Interval brackets the share (shares)", ((sh["lo"] <= sh["share"] + 1e-12) & (sh["share"] <= sh["hi"] + 1e-12)).all(),
        "Wilson interval does not contain the estimate")
    add("Numerator never exceeds denominator", (sh["x"] <= sh["n"]).all(), "x > n")
    add("Usage index is positive and inside its interval",
        ((geo["usage_index"] > 0) & (geo["usage_index_lo"] <= geo["usage_index"])
         & (geo["usage_index"] <= geo["usage_index_hi"])).all(), "index outside its interval")
    weighted = geo.assign(w=geo["population"] * geo["usage_index"]).groupby("geo_level").apply(
        lambda g: g["w"].sum() / g["population"].sum(), include_groups=False)
    add("Population-weighted mean usage index is 1 within each peer set", np.allclose(weighted.to_numpy(), 1.0),
        f"weighted means: {weighted.round(6).to_dict()}")
    add("Shares of known-geography usage add up to at most 1",
        (geo.groupby("geo_level")["share_of_known"].sum() <= 1 + 1e-9).all(), "shares of known usage exceed 1")
    add("Rest-of-parent share is between 0 and 1", vr["share_rest"].between(0, 1).all(), "share_rest outside [0, 1]")
    parent = sh.rename(columns={"geo_id": "parent_id", "share": "parent_share"})[["source", "parent_id", "metric", "parent_share"]]
    joined = vr.merge(parent, on=["source", "parent_id", "metric"], how="left")
    rebuilt = (joined["x"] + joined["x_rest"]) / (joined["n"] + joined["n_rest"])
    add("A geography plus its rest-of-parent group reproduces the parent's own share",
        bool(np.allclose(rebuilt, joined["parent_share"], rtol=1e-9, atol=1e-12)), "parts do not add up to the parent")
    add("Difference interval brackets the difference (vs rest)",
        ((vr["diff_lo"] <= vr["diff"] + 1e-12) & (vr["diff"] <= vr["diff_hi"] + 1e-12)).all(), "interval excludes estimate")
    add("Location quotients are positive and inside their intervals",
        ((rq["lq"] > 0) & (rq["lq_lo"] <= rq["lq"] + 1e-12) & (rq["lq"] <= rq["lq_hi"] + 1e-12)).all(), "bad location quotient")
    add("Every reported category meets the minimum count", (rq["x"] >= MIN_CATEGORY_COUNT).all(), "category below minimum")
    add("Category shares within a geography add up to at most 1",
        (rq.groupby("geo_id")["share"].sum() <= 1 + 1e-9).all(), "category shares exceed 1")
    add("Platform gap equals API share minus Claude.ai share and its interval brackets it",
        (np.allclose(pg["diff"], pg["api_share"] - pg["claude_ai_share"])
         and ((pg["diff_lo"] <= pg["diff"]) & (pg["diff"] <= pg["diff_hi"])).all()), "platform gap inconsistent")
    add("Exposure statistics are consistent",
        (fx["mean_exposure"].between(0, 1).all() and (fx["median_exposure"] <= fx["max_exposure"] + 1e-12).all()
         and fx["share_with_exposure"].between(0, 1).all()), "exposure out of range")
    add("Occupation counts add up to the input table", int(fx["occupations"].sum()) == len(inputs.job_exposure),
        f"{int(fx['occupations'].sum())} vs {len(inputs.job_exposure)}")
    add("Exposure ranks start at 1", fx["rank_by_mean"].min() == 1, "no group ranked first")
    ids = pd.concat([geo["geo_id"], sh["geo_id"], rq["geo_id"]])
    add("No unclassified geography reaches a metric",
        not (ids.isin(["NONE", "not_classified"]) | ids.str.endswith("-not_classified")).any(), "unclassified geography in output")
    known = set(inputs.countries["iso2"]) | set(inputs.provinces["geo_id"])
    add("Every geography in the usage index has a population", set(geo["geo_id"]) <= known, "unknown geography")
    return pd.DataFrame(out)
