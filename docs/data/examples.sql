-- SQLite; dates in Hong Kong local calendar.
SELECT station, variable, MIN(date), MAX(date), COUNT(*) FROM climate_daily GROUP BY station, variable;
SELECT station, trace_policy, split, COUNT(*), SUM(target_ge25mm) FROM core_features GROUP BY station, trace_policy, split;
SELECT * FROM core_features WHERE station='HKO' AND trace_policy='exclude' AND split='train' ORDER BY target_date;
SELECT station,date,value,source_path,source_line FROM climate_daily WHERE variable='RF' AND date='2023-09-07' ORDER BY value DESC;
SELECT document_id, title, publisher, url FROM knowledge_documents;
SELECT source_id,fetched_at_utc,source_url FROM realtime_snapshots;
