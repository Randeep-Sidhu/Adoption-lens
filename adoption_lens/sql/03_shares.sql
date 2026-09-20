CREATE OR REPLACE VIEW m_shares AS
WITH cnt AS (
    SELECT source, geo_id, geo_level, country_code, facet, cluster, value AS n
    FROM stg_aei
    WHERE variable IN ('use_case_count', 'collaboration_count', 'task_success_count')
      AND NOT is_unclassified_geo
),
use_case AS (
    SELECT source, geo_id, geo_level, country_code,
           SUM(CASE WHEN cluster IN ('work', 'personal', 'coursework') THEN n ELSE 0 END) AS classified,
           SUM(CASE WHEN cluster = 'work' THEN n ELSE 0 END) AS work,
           SUM(CASE WHEN cluster = 'coursework' THEN n ELSE 0 END) AS coursework
    FROM cnt
    WHERE facet = 'use_case'
    GROUP BY source, geo_id, geo_level, country_code
),
collaboration AS (
    SELECT source, geo_id, geo_level, country_code,
           SUM(CASE WHEN cluster IN ('directive', 'feedback loop', 'learning', 'task iteration', 'validation')
                    THEN n ELSE 0 END) AS classified,
           SUM(CASE WHEN cluster IN ('directive', 'feedback loop') THEN n ELSE 0 END) AS automation
    FROM cnt
    WHERE facet = 'collaboration'
    GROUP BY source, geo_id, geo_level, country_code
),
success AS (
    SELECT source, geo_id, geo_level, country_code,
           SUM(CASE WHEN cluster IN ('yes', 'no') THEN n ELSE 0 END) AS classified,
           SUM(CASE WHEN cluster = 'yes' THEN n ELSE 0 END) AS yes
    FROM cnt
    WHERE facet = 'task_success'
    GROUP BY source, geo_id, geo_level, country_code
),
counts AS (
    SELECT source, geo_id, geo_level, country_code, 'work_share' AS metric, work AS x, classified AS n FROM use_case
    UNION ALL
    SELECT source, geo_id, geo_level, country_code, 'coursework_share', coursework, classified FROM use_case
    UNION ALL
    SELECT source, geo_id, geo_level, country_code, 'automation_share', automation, classified FROM collaboration
    UNION ALL
    SELECT source, geo_id, geo_level, country_code, 'success_rate', yes, classified FROM success
)
SELECT source, geo_id, geo_level, country_code, metric, x, n,
       x / n AS share,
       wilson_lo(x, n) AS lo,
       wilson_hi(x, n) AS hi
FROM counts
WHERE n >= 200;
