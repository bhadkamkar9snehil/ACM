/*
91_create_representation_run_views.sql

Purpose:
- Bring the live run-insight views under source control.
- Make run-level operator views representation-aware without breaking the
  existing legacy score/health tables or dashboards.
*/

USE ACM;
GO

CREATE OR ALTER VIEW dbo.vw_ACM_RunOutputCoverage
AS
WITH score_rows AS (
    SELECT RunID, EquipID, COUNT(*) AS ScoreRows
    FROM dbo.ACM_Scores_Wide
    GROUP BY RunID, EquipID
),
health_rows AS (
    SELECT RunID, EquipID, COUNT(*) AS HealthRows
    FROM dbo.ACM_HealthTimeline
    GROUP BY RunID, EquipID
),
regime_rows AS (
    SELECT RunID, EquipID, COUNT(*) AS RegimeRows
    FROM dbo.ACM_RegimeTimeline
    GROUP BY RunID, EquipID
),
episode_rows AS (
    SELECT RunID, EquipID, COUNT(*) AS EpisodeRows
    FROM dbo.ACM_EpisodeDiagnostics
    GROUP BY RunID, EquipID
),
hotspot_rows AS (
    SELECT RunID, EquipID, COUNT(*) AS HotspotRows
    FROM dbo.ACM_SensorHotspots
    GROUP BY RunID, EquipID
),
representation_rows AS (
    SELECT RunID, EquipID, COUNT(*) AS RepresentationRows
    FROM dbo.ACM_RepresentationStatus
    GROUP BY RunID, EquipID
),
signal_profile_rows AS (
    SELECT RunID, EquipID, COUNT(*) AS SignalProfileRows
    FROM dbo.ACM_SignalProfiles
    GROUP BY RunID, EquipID
),
schema_rows AS (
    SELECT RunID, EquipID, COUNT(*) AS SchemaRows
    FROM dbo.ACM_RepresentationSchemas
    GROUP BY RunID, EquipID
),
baseline_rows AS (
    SELECT RunID, EquipID, COUNT(*) AS BaselineRows
    FROM dbo.ACM_BaselineGovernance
    GROUP BY RunID, EquipID
)
SELECT
    r.RunID,
    r.EquipID,
    e.EquipCode,
    e.EquipName,
    r.StartedAt,
    r.CompletedAt,
    ISNULL(sr.ScoreRows, 0) AS ScoreRows,
    ISNULL(hr.HealthRows, 0) AS HealthRows,
    ISNULL(rr.RegimeRows, 0) AS RegimeRows,
    ISNULL(er.EpisodeRows, 0) AS EpisodeRows,
    ISNULL(hor.HotspotRows, 0) AS HotspotRows,
    ISNULL(rpr.RepresentationRows, 0) AS RepresentationRows,
    ISNULL(spr.SignalProfileRows, 0) AS SignalProfileRows,
    ISNULL(scr.SchemaRows, 0) AS SchemaRows,
    ISNULL(br.BaselineRows, 0) AS BaselineRows,
    CONVERT(bit, CASE
        WHEN ISNULL(r.RepresentationAuthoritative, 0) = 1
         AND ISNULL(r.RepresentationScoreAllowed, 1) = 0
        THEN 0
        ELSE 1
    END) AS ScoreArtifactsExpected
FROM dbo.ACM_Runs r
INNER JOIN dbo.Equipment e
    ON e.EquipID = r.EquipID
LEFT JOIN score_rows sr
    ON sr.RunID = r.RunID AND sr.EquipID = r.EquipID
LEFT JOIN health_rows hr
    ON hr.RunID = r.RunID AND hr.EquipID = r.EquipID
LEFT JOIN regime_rows rr
    ON rr.RunID = r.RunID AND rr.EquipID = r.EquipID
LEFT JOIN episode_rows er
    ON er.RunID = r.RunID AND er.EquipID = r.EquipID
LEFT JOIN hotspot_rows hor
    ON hor.RunID = r.RunID AND hor.EquipID = r.EquipID
LEFT JOIN representation_rows rpr
    ON rpr.RunID = r.RunID AND rpr.EquipID = r.EquipID
LEFT JOIN signal_profile_rows spr
    ON spr.RunID = r.RunID AND spr.EquipID = r.EquipID
LEFT JOIN schema_rows scr
    ON scr.RunID = r.RunID AND scr.EquipID = r.EquipID
LEFT JOIN baseline_rows br
    ON br.RunID = r.RunID AND br.EquipID = r.EquipID;
GO

CREATE OR ALTER VIEW dbo.vw_ACM_RunQualityGates
AS
WITH latest_representation AS (
    SELECT
        rs.*,
        ROW_NUMBER() OVER (
            PARTITION BY rs.RunID, rs.EquipID
            ORDER BY rs.CreatedAt DESC, rs.Timestamp DESC
        ) AS rn
    FROM dbo.ACM_RepresentationStatus rs
),
latest_baseline AS (
    SELECT
        bg.*,
        ROW_NUMBER() OVER (
            PARTITION BY bg.RunID, bg.EquipID
            ORDER BY bg.CreatedAt DESC, bg.Timestamp DESC
        ) AS rn
    FROM dbo.ACM_BaselineGovernance bg
),
log_counts AS (
    SELECT
        rl.RunID,
        SUM(CASE WHEN UPPER(rl.Level) IN ('WARN', 'WARNING') THEN 1 ELSE 0 END) AS WarnCount,
        SUM(CASE WHEN UPPER(rl.Level) = 'ERROR' THEN 1 ELSE 0 END) AS ErrorCount
    FROM dbo.ACM_RunLogs rl
    GROUP BY rl.RunID
)
SELECT
    r.RunID,
    r.EquipID,
    e.EquipCode,
    e.EquipName,
    r.StartedAt,
    r.CompletedAt,
    r.DurationSeconds,
    r.TrainRowCount,
    r.ScoreRowCount,
    r.EpisodeCount,
    r.HealthStatus,
    r.DataQualityScore,
    r.ZeroDayStatus,
    r.ZeroDaySurfaceType,
    r.ZeroDayChannelCount,
    CONVERT(bit, COALESCE(CONVERT(int, r.RepresentationAuthoritative), CONVERT(int, lr.Authoritative), 0)) AS RepresentationAuthoritative,
    CONVERT(bit, COALESCE(CONVERT(int, r.RepresentationScoreAllowed), CONVERT(int, lr.ScoreAllowed), 0)) AS RepresentationScoreAllowed,
    CONVERT(bit, COALESCE(CONVERT(int, r.RepresentationLearnAllowed), CONVERT(int, lr.LearnAllowed), 0)) AS RepresentationLearnAllowed,
    COALESCE(r.RepresentationContextLabel, lr.ContextLabel, 'UNASSESSED') AS RepresentationContextLabel,
    COALESCE(r.RepresentationRuntimeMode, lb.RuntimeMode, 'UNASSESSED') AS RepresentationRuntimeMode,
    COALESCE(r.RepresentationSchemaCompatibility, lr.SchemaCompatibility, 'UNASSESSED') AS RepresentationSchemaCompatibility,
    COALESCE(r.RepresentationBasisCompatibility, lr.BasisCompatibility, 'UNASSESSED') AS RepresentationBasisCompatibility,
    COALESCE(r.RepresentationBaselineCompatibility, lr.BaselineCompatibility, 'UNASSESSED') AS RepresentationBaselineCompatibility,
    COALESCE(r.RepresentationSuppressedReasons, lr.SuppressedReasonsJson, '[]') AS RepresentationSuppressedReasons,
    COALESCE(r.RepresentationDegradedReasons, lr.DegradedReasonsJson, '[]') AS RepresentationDegradedReasons,
    lb.ReadinessState,
    lb.BaselineCandidateState,
    lb.ContaminationVerdict,
    lb.FreezeState,
    lb.ShadowRefreshState,
    lb.ReasonCodesJson AS BaselineReasonCodesJson,
    ISNULL(lc.WarnCount, 0) AS WarnCount,
    ISNULL(lc.ErrorCount, 0) AS ErrorCount,
    CASE
        WHEN r.CompletedAt IS NULL THEN 'IN_PROGRESS'
        WHEN COALESCE(CONVERT(int, r.RepresentationAuthoritative), CONVERT(int, lr.Authoritative), 0) = 1
         AND COALESCE(CONVERT(int, r.RepresentationScoreAllowed), CONVERT(int, lr.ScoreAllowed), 0) = 0
         AND COALESCE(CONVERT(int, r.RepresentationLearnAllowed), CONVERT(int, lr.LearnAllowed), 0) = 1
        THEN 'BASELINE_FORMATION'
        WHEN COALESCE(CONVERT(int, r.RepresentationAuthoritative), CONVERT(int, lr.Authoritative), 0) = 1
         AND COALESCE(CONVERT(int, r.RepresentationScoreAllowed), CONVERT(int, lr.ScoreAllowed), 1) = 0
         AND COALESCE(CONVERT(int, r.RepresentationLearnAllowed), CONVERT(int, lr.LearnAllowed), 1) = 0
        THEN 'SUPPRESSED_VALID'
        WHEN ISNULL(lc.ErrorCount, 0) > 0 THEN 'FAIL'
        WHEN r.ErrorMessage IS NOT NULL
         AND LTRIM(RTRIM(r.ErrorMessage)) <> ''
         AND r.ErrorMessage NOT LIKE '{"degraded_steps":%'
        THEN 'FAIL'
        WHEN ISNULL(r.ScoreRowCount, 0) = 0 AND ISNULL(r.TrainRowCount, 0) = 0 THEN 'NOOP_VALID'
        ELSE 'SCORED_OR_LEARNING'
    END AS RunClassification
FROM dbo.ACM_Runs r
INNER JOIN dbo.Equipment e
    ON e.EquipID = r.EquipID
LEFT JOIN latest_representation lr
    ON lr.RunID = r.RunID
   AND lr.EquipID = r.EquipID
   AND lr.rn = 1
LEFT JOIN latest_baseline lb
    ON lb.RunID = r.RunID
   AND lb.EquipID = r.EquipID
   AND lb.rn = 1
LEFT JOIN log_counts lc
    ON lc.RunID = r.RunID;
GO

CREATE OR ALTER VIEW dbo.vw_ACM_RunFact
AS
SELECT
    q.RunID,
    q.EquipID,
    q.EquipCode,
    q.EquipName,
    q.StartedAt,
    q.CompletedAt,
    q.DurationSeconds,
    q.TrainRowCount,
    q.ScoreRowCount,
    q.EpisodeCount,
    q.HealthStatus,
    q.DataQualityScore,
    q.ZeroDayStatus,
    q.ZeroDaySurfaceType,
    q.ZeroDayChannelCount,
    q.RepresentationAuthoritative,
    q.RepresentationScoreAllowed,
    q.RepresentationLearnAllowed,
    q.RepresentationContextLabel,
    q.RepresentationRuntimeMode,
    q.RepresentationSchemaCompatibility,
    q.RepresentationBasisCompatibility,
    q.RepresentationBaselineCompatibility,
    q.RepresentationSuppressedReasons,
    q.RepresentationDegradedReasons,
    q.ReadinessState,
    q.BaselineCandidateState,
    q.ContaminationVerdict,
    q.FreezeState,
    q.ShadowRefreshState,
    q.BaselineReasonCodesJson,
    q.WarnCount,
    q.ErrorCount,
    q.RunClassification,
    c.ScoreRows,
    c.HealthRows,
    c.RegimeRows,
    c.EpisodeRows,
    c.HotspotRows,
    c.RepresentationRows,
    c.SignalProfileRows,
    c.SchemaRows,
    c.BaselineRows,
    c.ScoreArtifactsExpected
FROM dbo.vw_ACM_RunQualityGates q
LEFT JOIN dbo.vw_ACM_RunOutputCoverage c
    ON c.RunID = q.RunID
   AND c.EquipID = q.EquipID;
GO

CREATE OR ALTER VIEW dbo.vw_ACM_RunStory
AS
SELECT
    rf.RunID,
    rf.EquipID,
    rf.EquipCode,
    rf.EquipName,
    rf.StartedAt,
    rf.CompletedAt,
    rf.RunClassification,
    rf.RepresentationRuntimeMode,
    rf.RepresentationAuthoritative,
    rf.RepresentationScoreAllowed,
    rf.RepresentationLearnAllowed,
    rf.RepresentationSchemaCompatibility,
    rf.RepresentationBasisCompatibility,
    rf.RepresentationBaselineCompatibility,
    rf.RepresentationContextLabel,
    rf.RepresentationSuppressedReasons,
    rf.RepresentationDegradedReasons,
    rf.ReadinessState,
    rf.BaselineCandidateState,
    rf.ContaminationVerdict,
    rf.WarnCount,
    rf.ErrorCount,
    CASE
        WHEN rf.RunClassification = 'FAIL'
            THEN 'Run failed; inspect ACM_RunLogs and ErrorMessage.'
        WHEN rf.RunClassification = 'BASELINE_FORMATION'
            THEN 'Baseline formation is active; learning is allowed and scoring is intentionally suppressed.'
        WHEN rf.RunClassification = 'SUPPRESSED_VALID'
         AND rf.RepresentationSuppressedReasons LIKE '%no_score_rows%'
            THEN 'Scoring was suppressed because no score rows remained after baseline seeding.'
        WHEN rf.RunClassification = 'SUPPRESSED_VALID'
         AND rf.RepresentationBasisCompatibility = 'INCOMPATIBLE'
            THEN 'Scoring was suppressed because the active basis contract is incompatible.'
        WHEN rf.RunClassification = 'SUPPRESSED_VALID'
         AND rf.RepresentationSuppressedReasons LIKE '%context_%'
            THEN 'Scoring was suppressed because contextual comparability is not trusted.'
        WHEN rf.RunClassification = 'NOOP_VALID'
            THEN 'Run completed without scoreable or learnable data.'
        ELSE 'Run produced score-oriented outputs or learnable runtime state.'
    END AS RunNarrative,
    CASE
        WHEN rf.RunClassification IN ('SUPPRESSED_VALID', 'BASELINE_FORMATION')
            THEN COALESCE(rf.RepresentationSuppressedReasons, rf.RepresentationDegradedReasons, rf.BaselineReasonCodesJson, '[]')
        WHEN rf.RunClassification = 'FAIL'
            THEN 'Inspect ACM_RunLogs for the failing component.'
        ELSE 'Review score, health, and episode outputs.'
    END AS OperatorFocus
FROM dbo.vw_ACM_RunFact rf;
GO

CREATE OR ALTER VIEW dbo.vw_ACM_EquipCurrentSnapshot
AS
WITH latest_run AS (
    SELECT
        rf.*,
        ROW_NUMBER() OVER (
            PARTITION BY rf.EquipID
            ORDER BY rf.StartedAt DESC, rf.RunID DESC
        ) AS rn
    FROM dbo.vw_ACM_RunFact rf
),
latest_health AS (
    SELECT
        ht.EquipID,
        ht.Timestamp,
        ht.HealthIndex,
        ht.HealthZone,
        ROW_NUMBER() OVER (
            PARTITION BY ht.EquipID
            ORDER BY ht.Timestamp DESC, ht.RunID DESC
        ) AS rn
    FROM dbo.ACM_HealthTimeline ht
)
SELECT
    lr.EquipID,
    lr.EquipCode,
    lr.EquipName,
    lr.RunID,
    lr.StartedAt,
    lr.CompletedAt,
    lr.RunClassification,
    lr.ZeroDayStatus,
    lr.ZeroDaySurfaceType,
    lr.ZeroDayChannelCount,
    lr.RepresentationAuthoritative,
    lr.RepresentationScoreAllowed,
    lr.RepresentationLearnAllowed,
    lr.RepresentationRuntimeMode,
    lr.RepresentationContextLabel,
    lr.RepresentationSchemaCompatibility,
    lr.RepresentationBasisCompatibility,
    lr.RepresentationBaselineCompatibility,
    lr.RepresentationSuppressedReasons,
    lr.RepresentationDegradedReasons,
    lr.ReadinessState,
    lr.BaselineCandidateState,
    lr.ContaminationVerdict,
    lh.HealthIndex,
    lh.HealthZone,
    lh.Timestamp AS HealthTimestamp
FROM latest_run lr
LEFT JOIN latest_health lh
    ON lh.EquipID = lr.EquipID
   AND lh.rn = 1
WHERE lr.rn = 1;
GO

PRINT 'Created or altered representation-aware run insight views:';
PRINT '  - vw_ACM_RunOutputCoverage';
PRINT '  - vw_ACM_RunQualityGates';
PRINT '  - vw_ACM_RunFact';
PRINT '  - vw_ACM_RunStory';
PRINT '  - vw_ACM_EquipCurrentSnapshot';
GO
