import json, re

BASE = 'c:/Users/bhadk/Documents/ACM V8 SQL/ACM/grafana_dashboards/'

# ─── Fix acm_master_complete.json ─────────────────────────────────────────────
with open(BASE + 'acm_master_complete.json', encoding='utf-8') as f:
    d = json.load(f)

for p in d.get('panels', []):
    pid = p.get('id')
    for t in p.get('targets', []):
        sql = t.get('rawSql', '')
        if not sql:
            continue

        # EntryDateTime → Timestamp (catch-all for Scores_Wide)
        if 'EntryDateTime' in sql:
            t['rawSql'] = sql.replace('EntryDateTime', 'Timestamp')
            sql = t['rawSql']

        # P4: Time in Zone — ACM_AlertAge doesn't exist
        if pid == 4 and 'ACM_AlertAge' in sql:
            t['rawSql'] = (
                "SELECT DATEDIFF(HOUR,\n"
                "  (SELECT MIN(Timestamp) FROM dbo.ACM_HealthTimeline WHERE EquipID = $equipment\n"
                "     AND HealthZone IN ('WATCH','ALERT')\n"
                "     AND RunID = (SELECT TOP 1 RunID FROM dbo.ACM_Runs WHERE EquipID = $equipment ORDER BY StartedAt DESC)),\n"
                "  (SELECT MAX(Timestamp) FROM dbo.ACM_HealthTimeline WHERE EquipID = $equipment\n"
                "     AND HealthZone IN ('WATCH','ALERT')\n"
                "     AND RunID = (SELECT TOP 1 RunID FROM dbo.ACM_Runs WHERE EquipID = $equipment ORDER BY StartedAt DESC))\n"
                ") AS DurationHours"
            )

        # P5: Episodes — ACM_EpisodeMetrics doesn't exist
        elif pid == 5 and 'ACM_EpisodeMetrics' in sql:
            t['rawSql'] = (
                "SELECT COUNT(*) AS TotalEpisodes\n"
                "FROM dbo.ACM_Episodes\n"
                "WHERE EquipID = $equipment\n"
                "  AND RunID = (SELECT TOP 1 RunID FROM dbo.ACM_Runs WHERE EquipID = $equipment ORDER BY StartedAt DESC)"
            )

        # P6: Defect Status — ACM_DefectSummary doesn't exist
        elif pid == 6 and 'ACM_DefectSummary' in sql:
            t['rawSql'] = (
                "SELECT TOP 1 HealthZone AS Status\n"
                "FROM dbo.ACM_HealthTimeline\n"
                "WHERE EquipID = $equipment\n"
                "ORDER BY Timestamp DESC"
            )

        # P7: Worst Sensor — ACM_DefectSummary doesn't exist
        elif pid == 7 and 'ACM_DefectSummary' in sql:
            t['rawSql'] = (
                "SELECT TOP 1 SensorName AS WorstSensor\n"
                "FROM dbo.ACM_SensorHotspots\n"
                "WHERE EquipID = $equipment\n"
                "  AND RunID = (SELECT TOP 1 RunID FROM dbo.ACM_Runs WHERE EquipID = $equipment ORDER BY StartedAt DESC)\n"
                "ORDER BY MaxAbsZ DESC"
            )

        # P23: Regime Dwell — ACM_RegimeDwellStats doesn't exist
        elif pid == 23 and 'ACM_RegimeDwellStats' in sql:
            t['rawSql'] = (
                "SELECT\n"
                "  ro.RegimeLabel,\n"
                "  ROUND(ro.DwellTimeHours, 2) AS DwellTimeHours,\n"
                "  ROUND(ro.DwellFraction * 100, 1) AS DwellPct,\n"
                "  ro.EntryCount\n"
                "FROM dbo.ACM_RegimeOccupancy ro\n"
                "WHERE ro.EquipID = $equipment\n"
                "  AND ro.RunID = (SELECT TOP 1 RunID FROM dbo.ACM_Runs WHERE EquipID = $equipment ORDER BY StartedAt DESC)\n"
                "ORDER BY ro.DwellTimeHours DESC"
            )

        # P61: Health Histogram — ACM_HealthHistogram doesn't exist
        elif pid == 61 and 'ACM_HealthHistogram' in sql:
            t['rawSql'] = (
                "SELECT\n"
                "  CAST(FLOOR(HealthIndex / 10) * 10 AS varchar) + '-' +\n"
                "  CAST(FLOOR(HealthIndex / 10) * 10 + 10 AS varchar) AS HealthBin,\n"
                "  COUNT(*) AS RecordCount\n"
                "FROM dbo.ACM_HealthTimeline\n"
                "WHERE EquipID = $equipment\n"
                "  AND RunID = (SELECT TOP 1 RunID FROM dbo.ACM_Runs WHERE EquipID = $equipment ORDER BY StartedAt DESC)\n"
                "GROUP BY FLOOR(HealthIndex / 10)\n"
                "ORDER BY FLOOR(HealthIndex / 10)"
            )

        # P63: Daily Anomaly Rate — ACM_SensorAnomalyByPeriod doesn't exist
        elif pid == 63 and 'ACM_SensorAnomalyByPeriod' in sql:
            t['rawSql'] = (
                "SELECT\n"
                "  sd.DetectorType,\n"
                "  ROUND(sd.ViolationPct, 1) AS AnomalyRatePct,\n"
                "  ROUND(sd.MaxZ, 2) AS MaxZ,\n"
                "  ROUND(sd.AvgZ, 2) AS AvgZ\n"
                "FROM dbo.ACM_SensorDefects sd\n"
                "WHERE sd.EquipID = $equipment\n"
                "  AND sd.RunID = (SELECT TOP 1 RunID FROM dbo.ACM_Runs WHERE EquipID = $equipment ORDER BY StartedAt DESC)\n"
                "ORDER BY sd.ViolationPct DESC"
            )

        # P81: Recent Pipeline Runs — RunLog (now ACM_RunLogs but wrong schema)
        elif pid == 81 and ('ACM_RunLogs' in sql or 'RunLog' in sql):
            t['rawSql'] = (
                "SELECT TOP 20\n"
                "  eq.EquipCode AS Equipment,\n"
                "  r.HealthStatus,\n"
                "  r.ScoreRowCount,\n"
                "  r.EpisodeCount,\n"
                "  r.DurationSeconds,\n"
                "  CONVERT(varchar(19), r.StartedAt, 120) AS StartedAt\n"
                "FROM dbo.ACM_Runs r\n"
                "JOIN dbo.Equipment eq ON eq.EquipID = r.EquipID\n"
                "WHERE r.EquipID = $equipment\n"
                "  AND r.StartedAt BETWEEN $__timeFrom() AND $__timeTo()\n"
                "ORDER BY r.StartedAt DESC"
            )

        # P82: Run Outcome Distribution
        elif pid == 82 and ('ACM_RunLogs' in sql or 'RunLog' in sql):
            t['rawSql'] = (
                "SELECT\n"
                "  r.HealthStatus,\n"
                "  COUNT(*) AS RunCount\n"
                "FROM dbo.ACM_Runs r\n"
                "WHERE r.EquipID = $equipment\n"
                "  AND r.StartedAt BETWEEN $__timeFrom() AND $__timeTo()\n"
                "GROUP BY r.HealthStatus\n"
                "ORDER BY RunCount DESC"
            )

        # P83: Run Duration History
        elif pid == 83 and ('ACM_RunLogs' in sql or 'RunLog' in sql):
            t['rawSql'] = (
                "SELECT\n"
                "  r.StartedAt AS time,\n"
                "  r.DurationSeconds AS value,\n"
                "  'Duration (s)' AS metric\n"
                "FROM dbo.ACM_Runs r\n"
                "WHERE r.EquipID = $equipment\n"
                "  AND r.StartedAt BETWEEN $__timeFrom() AND $__timeTo()\n"
                "ORDER BY r.StartedAt"
            )

with open(BASE + 'acm_master_complete.json', 'w', encoding='utf-8') as f:
    json.dump(d, f, indent=2, ensure_ascii=False)
print("master_complete: fixed")

# ─── Fix acm_fleet_overview.json — Zone → HealthZone ─────────────────────────
with open(BASE + 'acm_fleet_overview.json', encoding='utf-8') as f:
    d2 = json.load(f)

for p in d2.get('panels', []):
    for t in p.get('targets', []):
        sql = t.get('rawSql', '')
        if not sql:
            continue
        new = sql
        new = new.replace("Zone = 'ALERT'", "HealthZone = 'ALERT'")
        new = new.replace("Zone = 'WATCH'", "HealthZone = 'WATCH'")
        new = new.replace("Zone = 'GOOD'", "HealthZone = 'GOOD'")
        new = new.replace("h.Zone", "h.HealthZone")
        new = new.replace("Zone AS value", "HealthZone AS value")
        new = new.replace(",\n  h.Zone", ",\n  h.HealthZone AS Zone")
        if new != sql:
            t['rawSql'] = new

with open(BASE + 'acm_fleet_overview.json', 'w', encoding='utf-8') as f:
    json.dump(d2, f, indent=2, ensure_ascii=False)
print("fleet_overview: fixed")

print("All done.")
