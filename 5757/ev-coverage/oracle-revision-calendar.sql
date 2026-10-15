SELECT EXTRACT(YEAR FROM created) AS year,COUNT(*) AS revision_count,
MIN(created) AS first_revision,MAX(created) AS last_revision
FROM EV.REVISION GROUP BY EXTRACT(YEAR FROM created) ORDER BY year
FETCH FIRST 20 ROWS ONLY
