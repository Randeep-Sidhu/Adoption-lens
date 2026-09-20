CREATE OR REPLACE VIEW m_platform_gap AS
SELECT a.metric,
       a.share AS claude_ai_share,
       a.n AS claude_ai_n,
       b.share AS api_share,
       b.n AS api_n,
       b.share - a.share AS diff,
       b.share - a.share - 1.96 * sqrt(a.share * (1 - a.share) / a.n + b.share * (1 - b.share) / b.n) AS diff_lo,
       b.share - a.share + 1.96 * sqrt(a.share * (1 - a.share) / a.n + b.share * (1 - b.share) / b.n) AS diff_hi
FROM m_shares a
JOIN m_shares b ON b.metric = a.metric AND b.geo_id = 'GLOBAL'
WHERE a.geo_id = 'GLOBAL' AND a.source = 'claude_ai' AND b.source = 'api';
