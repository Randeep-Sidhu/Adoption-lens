CREATE OR REPLACE VIEW m_geo_usage AS
WITH usage AS (
    SELECT geo_id, geo_level, value AS conversations
    FROM stg_aei
    WHERE source = 'claude_ai'
      AND variable = 'usage_count'
      AND facet IN ('country', 'country-state')
      AND NOT is_unclassified_geo
),
known_totals AS (
    SELECT 'country' AS geo_level, SUM(conversations) AS known_conversations
    FROM usage
    WHERE geo_level = 'country'
    UNION ALL
    SELECT 'subregion', SUM(u.conversations)
    FROM usage u
    JOIN dim_province p ON p.geo_id = u.geo_id
    WHERE u.geo_level = 'subregion'
),
pool AS (
    SELECT u.geo_id, u.geo_level, u.conversations, c.population
    FROM usage u
    JOIN dim_country c ON c.iso2 = u.geo_id
    WHERE u.geo_level = 'country' AND u.conversations >= 200 AND c.population > 0
    UNION ALL
    SELECT u.geo_id, u.geo_level, u.conversations, p.population
    FROM usage u
    JOIN dim_province p ON p.geo_id = u.geo_id
    WHERE u.geo_level = 'subregion' AND u.conversations >= 200
),
pooled AS (
    SELECT *,
           SUM(conversations) OVER (PARTITION BY geo_level) AS pool_conversations,
           SUM(population) OVER (PARTITION BY geo_level) AS pool_population
    FROM pool
)
SELECT p.geo_id,
       p.geo_level,
       p.conversations,
       p.population,
       p.conversations / k.known_conversations AS share_of_known,
       p.conversations * 100000.0 / p.population AS per_100k,
       (p.conversations / p.population) / (p.pool_conversations / p.pool_population) AS usage_index,
       (p.conversations / p.population) / (p.pool_conversations / p.pool_population)
           * (1 - 1.96 / sqrt(p.conversations)) AS usage_index_lo,
       (p.conversations / p.population) / (p.pool_conversations / p.pool_population)
           * (1 + 1.96 / sqrt(p.conversations)) AS usage_index_hi
FROM pooled p
JOIN known_totals k ON k.geo_level = p.geo_level;
