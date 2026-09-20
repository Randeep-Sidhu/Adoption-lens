CREATE OR REPLACE VIEW m_request_mix AS
WITH req AS (
    SELECT source, geo_id, geo_level, country_code, cluster, value AS x
    FROM stg_aei
    WHERE facet = 'request'
      AND level = 2
      AND variable = 'request_count'
      AND cluster <> 'not_classified'
      AND NOT is_unclassified_geo
),
tot AS (
    SELECT source, geo_id, SUM(x) AS n
    FROM req
    GROUP BY source, geo_id
),
scope AS (
    SELECT r.source, r.geo_id,
           CASE r.geo_level WHEN 'country' THEN 'GLOBAL' ELSE r.country_code END AS parent_id,
           r.cluster, r.x, t.n
    FROM req r
    JOIN tot t ON t.source = r.source AND t.geo_id = r.geo_id
    WHERE r.source = 'claude_ai'
      AND t.n >= 200
      AND (r.geo_level = 'country'
           OR (r.geo_level = 'subregion' AND r.geo_id IN (SELECT geo_id FROM dim_province)))
),
joined AS (
    SELECT s.source, s.geo_id, s.parent_id, s.cluster, s.x, s.n,
           g.x - s.x AS x_rest,
           tp.n - s.n AS n_rest
    FROM scope s
    JOIN req g ON g.source = s.source AND g.geo_id = s.parent_id AND g.cluster = s.cluster
    JOIN tot tp ON tp.source = s.source AND tp.geo_id = s.parent_id
    WHERE g.x > s.x AND tp.n > s.n
),
scored AS (
    SELECT *,
           x / n AS share,
           x_rest / n_rest AS share_rest,
           (x / n) / (x_rest / n_rest) AS lq,
           sqrt(1.0 / x - 1.0 / n + 1.0 / x_rest - 1.0 / n_rest) AS se_log_lq
    FROM joined
    WHERE x >= 30
)
SELECT source, geo_id, parent_id, cluster, x, n, share, x_rest, n_rest, share_rest, lq,
       exp(ln(lq) - 1.96 * se_log_lq) AS lq_lo,
       exp(ln(lq) + 1.96 * se_log_lq) AS lq_hi,
       cluster IN (SELECT cluster FROM finance_lens) AS is_finance_lens
FROM scored;
