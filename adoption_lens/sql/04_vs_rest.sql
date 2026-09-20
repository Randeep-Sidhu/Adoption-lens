CREATE OR REPLACE VIEW m_vs_rest AS
WITH child AS (
    SELECT s.*,
           CASE s.geo_level WHEN 'country' THEN 'GLOBAL' ELSE s.country_code END AS parent_id
    FROM m_shares s
    WHERE s.geo_level IN ('country', 'subregion')
),
paired AS (
    SELECT c.source, c.geo_id, c.metric, c.parent_id,
           c.x, c.n, c.share,
           p.x - c.x AS x_rest,
           p.n - c.n AS n_rest
    FROM child c
    JOIN m_shares p
      ON p.source = c.source AND p.metric = c.metric AND p.geo_id = c.parent_id
    WHERE p.n - c.n >= 200
),
rates AS (
    SELECT *, x_rest / n_rest AS share_rest FROM paired
)
SELECT source, geo_id, metric, parent_id, x, n, share, x_rest, n_rest, share_rest,
       share - share_rest AS diff,
       share - share_rest - 1.96 * sqrt(share * (1 - share) / n + share_rest * (1 - share_rest) / n_rest) AS diff_lo,
       share - share_rest + 1.96 * sqrt(share * (1 - share) / n + share_rest * (1 - share_rest) / n_rest) AS diff_hi
FROM rates;
