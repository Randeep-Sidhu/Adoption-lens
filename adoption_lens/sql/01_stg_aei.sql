CREATE OR REPLACE VIEW stg_aei AS
SELECT source,
       geo_id,
       CASE geography WHEN 'country-state' THEN 'subregion' ELSE geography END AS geo_level,
       CASE geography WHEN 'country-state' THEN split_part(geo_id, '-', 1)
                      WHEN 'country' THEN geo_id END AS country_code,
       (geo_id IN ('NONE', 'not_classified') OR geo_id LIKE '%-not_classified') AS is_unclassified_geo,
       facet,
       level,
       variable,
       COALESCE(cluster_name, '') AS cluster,
       value
FROM aei_raw;
