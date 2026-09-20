from __future__ import annotations

import json
import textwrap
from pathlib import Path

import numpy as np
import pandas as pd
import plotly.graph_objects as go
import streamlit as st

ROOT = Path(__file__).parent
ART = ROOT / "artifacts"

INK, MUTED = "#2B2420", "#6E6056"
IVORY, SAND, LINE, GRID = "#FBF8F3", "#F0E7DA", "#E3D6C6", "#EBE1D4"
TAUPE, TAUPE_DARK, CAMEL, CLAY, COCOA = "#B39B82", "#9C846C", "#B98F6A", "#A9513A", "#5B4636"
METRIC_ORDER = ["work_share", "coursework_share", "automation_share", "success_rate"]
METRIC_LABELS = {"work_share": "Work-related", "coursework_share": "Coursework", "automation_share": "Automation pattern",
                 "success_rate": "Classified success"}
PLOT_CONFIG = {"displayModeBar": False}

st.set_page_config(page_title="AdoptionLens", layout="wide")
st.markdown(f"""
<style>
.block-container {{ padding-top: 2.5rem; padding-bottom: 3rem; max-width: 1180px; }}
[data-testid="stMetric"] {{ background: {SAND}; border: 1px solid {LINE}; border-radius: 12px; padding: 16px 20px 12px 20px; }}
[data-testid="stMetricLabel"] p {{ color: {MUTED}; font-size: 0.9rem; }}
[data-testid="stMetricValue"] {{ color: {INK}; font-weight: 600; }}
</style>
""", unsafe_allow_html=True)


@st.cache_data
def load() -> dict:
    g, q = ART / "gold", ART / "qa"
    if not (g / "geo_usage.csv").exists():
        return {}
    d = {name: pd.read_csv(g / f"{name}.csv", keep_default_na=False, na_values=[""], dtype={"soc_group": str})
         for name in ("geo_usage", "shares", "vs_rest", "request_mix", "platform_gap", "function_exposure", "geo_names")}
    d["brief"] = (ART / "brief.md").read_text()
    d["summary"] = json.loads((q / "summary.json").read_text())
    d["manifest"] = json.loads((ART / "source_manifest.json").read_text())
    for name in ("data_quality", "reconciliation", "invariants", "mutation", "rollup_gaps"):
        path = q / f"{name}.csv"
        d[name] = pd.read_csv(path, keep_default_na=False, na_values=[""]) if path.exists() else None
    jobs = ROOT / "data" / "reference" / "job_exposure.csv"
    d["jobs"] = pd.read_csv(jobs, dtype={"occ_code": str}) if jobs.exists() else None
    return d


D = load()
if not D:
    st.error("No artifacts found. Build them with the pipeline first, then reload this page.")
    st.stop()

names = dict(zip(D["geo_names"]["geo_id"], D["geo_names"]["name"]))
names["GLOBAL"] = "the world"
S = D["summary"]


def label(geo_id: str) -> str:
    return names.get(geo_id, geo_id)


def wrap(text: str, width: int = 58) -> str:
    return "<br>".join(textwrap.wrap(text, width))


def show(fig: go.Figure, height: int = 420, legend: bool = False) -> None:
    fig.update_layout(
        height=height, margin=dict(l=8, r=20, t=16, b=8), plot_bgcolor="rgba(0,0,0,0)", paper_bgcolor="rgba(0,0,0,0)",
        font=dict(color=INK, size=13), showlegend=legend,
        hoverlabel=dict(bgcolor="#FFFFFF", bordercolor=LINE, font=dict(color=INK)))
    fig.update_xaxes(gridcolor=GRID, zeroline=False, linecolor=LINE, tickfont=dict(color=MUTED),
                     title_font=dict(color=MUTED, size=12), automargin=True)
    fig.update_yaxes(gridcolor=GRID, zeroline=False, linecolor=LINE, tickfont=dict(color=INK),
                     title_font=dict(color=MUTED, size=12), automargin=True)
    st.plotly_chart(fig, config=PLOT_CONFIG)


st.title("GenAI usage in Canada")
st.markdown(f'<div style="height:3px;width:56px;background:{CLAY};border-radius:2px;margin:-0.5rem 0 1rem 0"></div>',
            unsafe_allow_html=True)
st.caption("Public data: Anthropic Economic Index, week of 5 to 12 February 2026. About one million sampled Claude.ai "
           "conversations and one million first-party API conversations. Sampled conversations, not people.")

tabs = st.tabs(["Countries", "Provinces", "How Canadians use it", "Request types", "Chat and API", "Occupations", "Brief",
                "Data checks"])

with tabs[0]:
    geo = D["geo_usage"]
    c = geo[geo["geo_level"] == "country"].sort_values("usage_index", ascending=False).reset_index(drop=True)
    c["name"] = c["geo_id"].map(label)
    rank = int(c.index[c["geo_id"] == "CA"][0]) + 1
    ca = c[c["geo_id"] == "CA"].iloc[0]
    a, b, k = st.columns(3)
    a.metric("Canada's rank on usage per resident", f"{rank} of {len(c)}")
    a.caption("Countries with a population figure and at least 200 sampled conversations")
    b.metric("Canada's usage index", f"{ca['usage_index']:.2f}")
    b.caption(f"95% band {ca['usage_index_lo']:.2f} to {ca['usage_index_hi']:.2f}. 1.0 is the peer-set average")
    k.metric("Sampled Canadian conversations", f"{int(ca['conversations']):,}")
    k.caption("Claude.ai, 5 to 12 February 2026")
    top_n = st.slider("Countries to show", 10, len(c), 25)
    shown = c.head(top_n)
    if "CA" not in set(shown["geo_id"]):
        shown = pd.concat([shown, c[c["geo_id"] == "CA"]])
    shown = shown.iloc[::-1]
    fig = go.Figure(go.Bar(
        x=shown["usage_index"], y=shown["name"], orientation="h",
        marker_color=[CLAY if g == "CA" else TAUPE for g in shown["geo_id"]],
        error_x=dict(type="data", symmetric=False, array=shown["usage_index_hi"] - shown["usage_index"],
                     arrayminus=shown["usage_index"] - shown["usage_index_lo"], color=COCOA, thickness=1.2, width=3),
        hovertemplate="%{y}: %{x:.2f}<extra></extra>"))
    fig.add_vline(x=1, line_dash="dot", line_color=MUTED)
    fig.update_layout(xaxis_title="Usage index (1.0 is the average of the peer set)", bargap=0.28)
    show(fig, 120 + 24 * len(shown))
    st.caption("Peer set: countries with at least 200 sampled conversations and a World Bank population figure for 2024. "
               "The index is conversations per resident relative to the pooled rate of that set. Bars show a 95% band.")

with tabs[1]:
    p = D["geo_usage"]
    p = p[p["geo_level"] == "subregion"].sort_values("usage_index").copy()
    p["name"] = p["geo_id"].map(label)
    fig = go.Figure(go.Bar(
        x=p["usage_index"], y=p["name"], orientation="h", marker_color=CAMEL,
        error_x=dict(type="data", symmetric=False, array=p["usage_index_hi"] - p["usage_index"],
                     arrayminus=p["usage_index"] - p["usage_index_lo"], color=COCOA, thickness=1.2, width=3),
        hovertemplate="%{y}: %{x:.2f}<extra></extra>"))
    fig.add_vline(x=1, line_dash="dot", line_color=MUTED)
    fig.update_layout(xaxis_title="Usage index (1.0 is the Canadian average across these provinces)", bargap=0.32)
    show(fig, 120 + 46 * len(p))
    table = p.sort_values("usage_index", ascending=False).rename(columns={
        "name": "Province", "conversations": "Sampled conversations", "population": "Population",
        "share_of_known": "Share of Canadian usage", "per_100k": "Per 100,000 residents", "usage_index": "Index"})
    st.dataframe(table[["Province", "Sampled conversations", "Population", "Share of Canadian usage",
                        "Per 100,000 residents", "Index"]].style.format({
        "Sampled conversations": "{:,.0f}", "Population": "{:,.0f}", "Share of Canadian usage": "{:.1%}",
        "Per 100,000 residents": "{:.1f}", "Index": "{:.2f}"}), hide_index=True, width="stretch")
    st.caption("Provinces with fewer than 200 sampled conversations are left out, and the territories do not appear in "
               "the file. Populations are Statistics Canada's estimates for 1 April 2026.")

with tabs[2]:
    vr = D["vs_rest"]
    options = sorted(set(vr[vr["source"] == "claude_ai"]["geo_id"]), key=lambda g: (g != "CA", label(g)))
    choice = st.selectbox("Geography", options, format_func=label, index=0)
    rows = vr[(vr["source"] == "claude_ai") & (vr["geo_id"] == choice)].copy()
    rows["label"] = rows["metric"].map(METRIC_LABELS)
    rows = rows.sort_values("metric", key=lambda s: s.map(METRIC_ORDER.index))
    parent = label(rows["parent_id"].iloc[0]) if len(rows) else ""
    diff = 100 * rows["diff"]
    fig = go.Figure(go.Scatter(
        x=diff, y=rows["label"], mode="markers+text", text=[f"{v:+.1f}" for v in diff], textposition="top center",
        textfont=dict(color=INK, size=12),
        marker=dict(color=CLAY if choice == "CA" else COCOA, size=12, line=dict(color=IVORY, width=1.5)),
        error_x=dict(type="data", symmetric=False, array=100 * (rows["diff_hi"] - rows["diff"]),
                     arrayminus=100 * (rows["diff"] - rows["diff_lo"]), color=COCOA, thickness=1.5, width=4),
        hovertemplate="%{y}: %{x:+.1f} points<extra></extra>"))
    fig.add_vline(x=0, line_dash="dot", line_color=MUTED)
    fig.update_yaxes(autorange="reversed")
    fig.update_layout(xaxis_title=f"{label(choice)} minus the rest of {parent}, percentage points (95% interval)")
    show(fig, 340)
    view = rows[["label", "share", "share_rest", "n", "n_rest"]].copy()
    view["share"], view["share_rest"] = 100 * view["share"], 100 * view["share_rest"]
    st.dataframe(view.rename(columns={"label": "Measure", "share": f"{label(choice)} (%)", "share_rest": "Rest (%)",
                                      "n": "Conversations", "n_rest": "Rest conversations"}).style.format({
        f"{label(choice)} (%)": "{:.1f}", "Rest (%)": "{:.1f}", "Conversations": "{:,.0f}", "Rest conversations": "{:,.0f}"}),
        hide_index=True, width="stretch")
    st.caption("Automation pattern: the person delegates a task (directive or feedback loop). Classified success is a label "
               "assigned to the conversation, not something the person reported.")

with tabs[3]:
    rq = D["request_mix"]
    geos = sorted(set(rq["geo_id"]), key=lambda g: (g != "CA", label(g)))
    pick = st.selectbox("Geography", geos, format_func=label, key="req_geo")
    r = rq[rq["geo_id"] == pick].sort_values("lq").copy()
    r["wrapped"] = r["cluster"].map(wrap)
    fig = go.Figure(go.Scatter(
        x=r["lq"], y=r["wrapped"], mode="markers",
        marker=dict(color=[CLAY if f else TAUPE_DARK for f in r["is_finance_lens"].astype(bool)],
                    size=[14 if f else 10 for f in r["is_finance_lens"].astype(bool)], line=dict(color=IVORY, width=1)),
        error_x=dict(type="data", symmetric=False, array=r["lq_hi"] - r["lq"], arrayminus=r["lq"] - r["lq_lo"],
                     color=COCOA, thickness=1, width=3),
        customdata=np.stack([r["share"] * 100, r["share_rest"] * 100], axis=-1),
        hovertemplate="%{y}<br>index %{x:.2f}<br>%{customdata[0]:.1f}% here, %{customdata[1]:.1f}% elsewhere<extra></extra>"))
    fig.add_vline(x=1, line_dash="dot", line_color=MUTED)
    fig.update_layout(xaxis_title="Location quotient (above 1 means over-represented; 95% band)", xaxis_type="log")
    show(fig, 150 + 40 * len(r))
    st.caption("Highlighted points are the four categories I flagged as close to financial services work. The list is a "
               "judgement call, kept in data/reference/finance_lens.csv. Categories with fewer than 30 conversations are omitted.")

with tabs[4]:
    pg = D["platform_gap"].copy()
    pg["metric"] = pd.Categorical(pg["metric"], METRIC_ORDER, ordered=True)
    pg = pg.sort_values("metric")
    pg["label"] = pg["metric"].map(METRIC_LABELS)
    fig = go.Figure()
    fig.add_bar(name="Claude.ai", x=pg["label"], y=100 * pg["claude_ai_share"], marker_color=TAUPE,
                texttemplate="%{y:.1f}%", textposition="outside", cliponaxis=False, textfont=dict(color=MUTED))
    fig.add_bar(name="First-party API", x=pg["label"], y=100 * pg["api_share"], marker_color=COCOA,
                texttemplate="%{y:.1f}%", textposition="outside", cliponaxis=False, textfont=dict(color=INK))
    fig.update_layout(barmode="group", bargap=0.35, bargroupgap=0.06, yaxis_title="Share of classified conversations (%)",
                      yaxis_range=[0, 95], legend=dict(orientation="h", y=1.1, x=0))
    show(fig, 400, legend=True)
    view = pg[["label", "claude_ai_share", "api_share", "diff", "diff_lo", "diff_hi"]].copy()
    for col in ("claude_ai_share", "api_share", "diff", "diff_lo", "diff_hi"):
        view[col] = 100 * view[col]
    st.dataframe(view.rename(columns={"label": "Measure", "claude_ai_share": "Claude.ai (%)", "api_share": "API (%)",
                                      "diff": "API minus Claude.ai (points)", "diff_lo": "Lower", "diff_hi": "Upper"})
                 .style.format({c: "{:.1f}" for c in ("Claude.ai (%)", "API (%)", "API minus Claude.ai (points)", "Lower", "Upper")}),
                 hide_index=True, width="stretch")
    st.caption("Global figures. The two sources use different request taxonomies, so request categories are not compared.")

with tabs[5]:
    fx = D["function_exposure"].sort_values("mean_exposure")
    fig = go.Figure(go.Bar(
        x=fx["mean_exposure"], y=fx["soc_name"], orientation="h",
        marker_color=[CLAY if g == "13" else TAUPE for g in fx["soc_group"]], hovertemplate="%{y}: %{x:.3f}<extra></extra>"))
    fig.update_layout(xaxis_title="Mean observed exposure (unweighted across occupations)", bargap=0.28)
    show(fig, 140 + 26 * len(fx))
    if D["jobs"] is not None:
        group = st.selectbox("Occupations in", fx.sort_values("mean_exposure", ascending=False)["soc_group"],
                             format_func=lambda g: dict(zip(fx["soc_group"], fx["soc_name"]))[g])
        jobs = D["jobs"][D["jobs"]["occ_code"].str.startswith(group + "-")].sort_values("observed_exposure", ascending=False)
        st.dataframe(jobs.rename(columns={"occ_code": "Code", "title": "Occupation", "observed_exposure": "Observed exposure"}),
                     hide_index=True, width="stretch")
    st.caption("The highlighted bar is Business and Financial Operations. Exposure scores come from Anthropic's "
               "labor-market-impacts release.")

with tabs[6]:
    st.markdown(D["brief"])

with tabs[7]:
    st.markdown("Everything above comes from SQL. This tab shows the evidence that the SQL is right and that the data is fit to use.")
    mut = S.get("mutation")
    m1, m2, m3, m4, m5 = st.columns(5)
    m1.metric("Source checksums", "match" if S["sources_match_published_checksums"] else "differ")
    m2.metric("Cells reconciled", f"{S['reconciliation']['cells_compared']:,}")
    m2.caption(f"{S['reconciliation']['mismatches']} mismatches")
    m3.metric("Invariants held", f"{S['invariants']['passed']} of {S['invariants']['total']}")
    m4.metric("Data checks passed", f"{S['data_checks']['passed']} of {S['data_checks']['total']}")
    m5.metric("Injected bugs caught", f"{mut['killed']} of {mut['total']}" if mut else "not run")
    st.subheader("Findings in the data")
    if D["rollup_gaps"] is not None:
        st.markdown("In three countries the subregion counts add up to more than the country count. Each gap equals the "
                    "conversations from overseas territories that the file lists both as a subregion of the country and as "
                    "a country of their own.")
        st.dataframe(D["rollup_gaps"], hide_index=True, width="stretch")
    if D["data_quality"] is not None:
        st.subheader("Data checks")
        st.dataframe(D["data_quality"][["layer", "check", "severity", "value", "max_allowed", "passed", "description"]],
                     hide_index=True, width="stretch")
    if D["mutation"] is not None:
        st.subheader("Bugs injected into the SQL")
        mt = D["mutation"].fillna("")
        mt["caught"] = np.where(mt["killed"].astype(bool), "yes", "NO")
        st.dataframe(mt[["id", "bug", "caught", "detected_by", "caught_on"]].rename(columns={
            "id": "Id", "bug": "Bug injected", "caught": "Caught", "detected_by": "Caught by", "caught_on": "Dataset"}),
            hide_index=True, width="stretch")
    st.subheader("Sources")
    st.dataframe(pd.DataFrame(D["manifest"]).T[["file", "bytes", "sha256"]], width="stretch")
