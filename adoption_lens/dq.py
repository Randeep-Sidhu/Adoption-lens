from __future__ import annotations

import pandas as pd

from .config import MIN_CONVERSATIONS
from .data import Inputs

CATEGORICAL = ("use_case", "collaboration", "task_success", "human_only_ability", "multitasking", "request")
_FACETS = ", ".join(f"'{f}'" for f in CATEGORICAL)
_KEY = "source, geo_id, facet, level, variable, COALESCE(cluster_name, '')"

_ROLLUP = """
WITH sub AS (SELECT split_part(geo_id, '-', 1) AS cc, SUM(value) AS s FROM aei_raw
             WHERE source = 'claude_ai' AND geography = 'country-state' AND facet = 'country-state'
               AND variable = 'usage_count' GROUP BY 1),
     ctry AS (SELECT geo_id AS cc, value AS v FROM aei_raw
              WHERE source = 'claude_ai' AND geography = 'country' AND facet = 'country' AND variable = 'usage_count'),
     terr AS (SELECT t.parent AS cc, SUM(c.value) AS t FROM dim_territory t
              JOIN aei_raw c ON c.source = 'claude_ai' AND c.geography = 'country' AND c.facet = 'country'
                            AND c.variable = 'usage_count' AND c.geo_id = t.territory
              GROUP BY t.parent)
SELECT {select} AS v FROM sub JOIN ctry USING (cc) LEFT JOIN terr USING (cc) WHERE {where}
"""

SQL_CHECKS: list[tuple[str, str, str, float, str, str]] = [
    ("source", "both_sources_loaded", "error", 0, "Sources missing from the load (expects claude_ai and api)",
     "SELECT 2 - COUNT(DISTINCT source) AS v FROM aei_raw"),
    ("source", "duplicate_keys", "error", 0, "Key groups (source, geo, facet, level, variable, cluster) that occur more than once",
     f"SELECT COUNT(*) AS v FROM (SELECT 1 FROM aei_raw GROUP BY {_KEY} HAVING COUNT(*) > 1)"),
    ("source", "null_values", "error", 0, "Rows with a missing value, geography, facet or variable",
     "SELECT COUNT(*) AS v FROM aei_raw WHERE value IS NULL OR geo_id IS NULL OR facet IS NULL OR variable IS NULL"),
    ("source", "negative_values", "error", 0, "Rows with a negative value, other than confidence-interval lower bounds",
     "SELECT COUNT(*) AS v FROM aei_raw WHERE value < 0 AND variable NOT LIKE '%\\_ci\\_lower' ESCAPE '\\'"),
    ("source", "negative_ci_lower_bounds", "info", float("inf"),
     "Confidence-interval lower bounds below zero for quantities that cannot be negative (not used here)",
     "SELECT COUNT(*) AS v FROM aei_raw WHERE value < 0 AND variable LIKE '%\\_ci\\_lower' ESCAPE '\\'"),
    ("source", "percentages_out_of_range", "error", 0, "Percentage rows outside 0-100",
     """SELECT COUNT(*) AS v FROM aei_raw
        WHERE variable LIKE '%\\_pct' ESCAPE '\\' AND variable NOT LIKE '%histogram%'
          AND (value < 0 OR value > 100.000001)"""),
    ("source", "period_is_one_week", "error", 0, "Sources whose rows do not all cover the same seven-day period",
     """SELECT COUNT(*) AS v FROM (SELECT source FROM aei_raw GROUP BY source
        HAVING COUNT(DISTINCT date_start) <> 1 OR COUNT(DISTINCT date_end) <> 1 OR MAX(date_end - date_start) <> 7
            OR MIN(date_end - date_start) <> 7)"""),
    ("consistency", "shares_sum_to_100", "error", 0, "Category groups whose percentages do not add up to 100",
     f"""SELECT COUNT(*) AS v FROM (SELECT source, geo_id, facet, level, SUM(value) AS total FROM aei_raw
        WHERE facet IN ({_FACETS}) AND variable = facet || '_pct' GROUP BY source, geo_id, facet, level
        HAVING ABS(SUM(value) - 100) > 0.01)"""),
    ("consistency", "counts_agree_with_percentages", "error", 0, "Category rows where the percentage differs from count / total",
     f"""WITH c AS (SELECT source, geo_id, facet, level, cluster_name, value AS n FROM aei_raw
                   WHERE facet IN ({_FACETS}) AND variable = facet || '_count'),
             t AS (SELECT source, geo_id, facet, level, SUM(n) AS total FROM c GROUP BY ALL),
             p AS (SELECT source, geo_id, facet, level, cluster_name, value AS pct FROM aei_raw
                   WHERE facet IN ({_FACETS}) AND variable = facet || '_pct')
        SELECT COUNT(*) AS v FROM c JOIN t USING (source, geo_id, facet, level)
        JOIN p USING (source, geo_id, facet, level, cluster_name)
        WHERE ABS(100.0 * c.n / t.total - p.pct) > 0.0001"""),
    ("geography", "unknown_country_codes", "error", 0, "Country codes that are not in the GeoNames country list",
     """SELECT COUNT(DISTINCT geo_id) AS v FROM aei_raw WHERE geography = 'country'
        AND geo_id NOT IN ('NONE', 'not_classified') AND geo_id NOT IN (SELECT iso2 FROM dim_country)"""),
    ("geography", "unknown_subregion_parents", "error", 0, "Subregion codes whose country prefix is not a known country",
     """SELECT COUNT(DISTINCT geo_id) AS v FROM aei_raw WHERE geography = 'country-state'
        AND split_part(geo_id, '-', 1) NOT IN (SELECT iso2 FROM dim_country)"""),
    ("geography", "unexplained_rollup_gaps", "error", 0,
     "Countries whose subregion counts exceed or fall short of the country count by more than the overseas territories listed under both",
     _ROLLUP.format(select="COUNT(*)", where="(s - v) - COALESCE(t, 0) <> 0")),
    ("geography", "documented_rollup_gaps", "info", float("inf"),
     "Countries whose subregion counts differ from the country count (explained by territories listed twice)",
     _ROLLUP.format(select="COUNT(*)", where="s <> v")),
    ("coverage", "countries_missing_from_sample_total", "warn", 0.02,
     "Share of the sampled conversations not accounted for by any country row (small countries are not published)",
     """SELECT 1.0 - (SELECT SUM(value) FROM aei_raw WHERE source = 'claude_ai' AND geography = 'country'
                     AND facet = 'country' AND variable = 'usage_count')
                   / (SELECT SUM(value) FROM aei_raw WHERE source = 'claude_ai' AND geo_id = 'GLOBAL'
                      AND facet = 'use_case' AND variable = 'use_case_count') AS v"""),
    ("coverage", "unclassified_geography_share", "warn", 0.25,
     "Share of sampled conversations with no usable country (NONE or not_classified)",
     """SELECT (SELECT SUM(value) FROM aei_raw WHERE source = 'claude_ai' AND geography = 'country' AND facet = 'country'
               AND variable = 'usage_count' AND geo_id IN ('NONE', 'not_classified'))
              / (SELECT SUM(value) FROM aei_raw WHERE source = 'claude_ai' AND geo_id = 'GLOBAL'
                 AND facet = 'use_case' AND variable = 'use_case_count') AS v"""),
    ("coverage", "countries_without_population", "info", float("inf"),
     "Countries with enough conversations for the index that have no World Bank population figure and are left out",
     f"""SELECT COUNT(*) AS v FROM aei_raw a JOIN dim_country c ON c.iso2 = a.geo_id
        WHERE a.source = 'claude_ai' AND a.geography = 'country' AND a.facet = 'country' AND a.variable = 'usage_count'
          AND a.value >= {MIN_CONVERSATIONS} AND c.population IS NULL"""),
    ("coverage", "small_count_cells", "warn", 0.15,
     "Share of published count cells below 15 conversations (treat small cells with caution)",
     """SELECT AVG(CASE WHEN value < 15 THEN 1.0 ELSE 0.0 END) AS v FROM aei_raw
        WHERE variable LIKE '%\\_count' ESCAPE '\\' AND variable NOT LIKE '%histogram%'"""),
    ("reference", "finance_lens_clusters_exist", "error", 0, "Finance-lens categories that do not exist in the global request taxonomy",
     """SELECT COUNT(*) AS v FROM finance_lens WHERE cluster NOT IN
        (SELECT cluster_name FROM aei_raw WHERE source = 'claude_ai' AND geo_id = 'GLOBAL' AND facet = 'request'
         AND level = 2 AND variable = 'request_count')"""),
    ("reference", "job_exposure_contract", "error", 0, "Occupation rows with a bad code, duplicate code or exposure outside 0-1",
     """SELECT (SELECT COUNT(*) FROM job_exposure WHERE NOT regexp_matches(occ_code, '^[0-9]{2}-[0-9]{4}$')
                 OR observed_exposure < 0 OR observed_exposure > 1)
              + (SELECT COUNT(*) - COUNT(DISTINCT occ_code) FROM job_exposure) AS v"""),
]


def run_dq(wh, inputs: Inputs | None = None, layers: tuple[str, ...] | None = None) -> pd.DataFrame:
    rows = []
    for layer, check, severity, max_allowed, description, sql in SQL_CHECKS:
        if layers is not None and layer not in layers:
            continue
        value = wh.df(sql)["v"].iloc[0]
        value = 0.0 if pd.isna(value) else float(value)
        rows.append({"layer": layer, "check": check, "severity": severity, "value": value,
                     "max_allowed": max_allowed, "passed": abs(value) <= max_allowed, "description": description})
    if inputs is not None and (layers is None or "reference" in layers):
        gap = abs(int(inputs.provinces["population"].sum()) - inputs.canada_population)
        rows.append({"layer": "reference", "check": "province_population_adds_up", "severity": "error",
                     "value": float(gap), "max_allowed": 0, "passed": gap == 0,
                     "description": "Difference between the provincial populations and the published Canada total"})
    return pd.DataFrame(rows)
