CREATE OR REPLACE VIEW m_function_exposure AS
WITH occ AS (
    SELECT left(occ_code, 2) AS soc_group, occ_code, title, observed_exposure,
           ROW_NUMBER() OVER (PARTITION BY left(occ_code, 2)
                              ORDER BY observed_exposure DESC, title ASC) AS pos
    FROM job_exposure
),
grouped AS (
    SELECT soc_group,
           COUNT(*) AS occupations,
           AVG(observed_exposure) AS mean_exposure,
           percentile_cont(0.5) WITHIN GROUP (ORDER BY observed_exposure) AS median_exposure,
           AVG(CASE WHEN observed_exposure > 0 THEN 1.0 ELSE 0.0 END) AS share_with_exposure,
           MAX(observed_exposure) AS max_exposure,
           MAX(CASE WHEN pos = 1 THEN title END) AS most_exposed_occupation
    FROM occ
    GROUP BY soc_group
)
SELECT g.soc_group,
       s.name AS soc_name,
       g.occupations,
       g.mean_exposure,
       g.median_exposure,
       g.share_with_exposure,
       g.max_exposure,
       g.most_exposed_occupation,
       RANK() OVER (ORDER BY g.mean_exposure DESC) AS rank_by_mean
FROM grouped g
JOIN dim_soc_group s ON s.soc_group = g.soc_group;
