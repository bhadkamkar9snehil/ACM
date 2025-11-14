/*
 * Script: 56_create_detector_metadata.sql
 * Purpose: Define metadata and human-readable explanations for ACM detector families
 * Context: Used by Grafana operator dashboards to explain which "heads" are active
 *
 * This table is intentionally asset-agnostic: explanations describe what each
 * detector family measures, not equipment-specific details. It can be joined
 * to ACM_SensorDefects via DetectorFamily.
 */

USE ACM;
GO

IF NOT EXISTS (SELECT * FROM sys.tables WHERE name = 'ACM_DetectorMetadata' AND schema_id = SCHEMA_ID('dbo'))
BEGIN
    CREATE TABLE dbo.ACM_DetectorMetadata (
        DetectorFamily      NVARCHAR(50)  NOT NULL PRIMARY KEY,
        ShortName           NVARCHAR(50)  NOT NULL,
        Explanation         NVARCHAR(400) NOT NULL,
        OperatorHint        NVARCHAR(400) NULL,
        CreatedAt           DATETIME2     NOT NULL CONSTRAINT DF_ACM_DetectorMetadata_CreatedAt DEFAULT (SYSUTCDATETIME())
    );
END
GO

;WITH Meta AS (
    SELECT *
    FROM (VALUES
        ('AR1_Z',      'AR1 residuals',
         'Checks if a single feature''s short-term behaviour has changed (auto-regressive residual).',
         'Look for recent trend or step change in the underlying sensor; spikes often mean sudden jumps or oscillations.'),
        ('CUSUM_Z',    'CUSUM trend',
         'Detects gradual drifts over time using cumulative sum statistics.',
         'A rising CUSUM head means a slow drift away from baseline; plan maintenance before it reaches alert.'),
        ('GMM_Z',      'Mixture cluster',
         'Compares current feature pattern against learned operating clusters (Gaussian Mixture Model).',
         'If this head is high, the asset is operating in a pattern rarely seen in training; verify regime and load.'),
        ('IFOREST_Z',  'Isolation forest',
         'Marks points that look globally unusual compared to all historical data.',
         'High values typically indicate rare combinations of sensors; check Sensor Hotspots for culprits.'),
        ('MHAL_Z',     'Mahalanobis',
         'Multivariate distance from the normal operating cloud across all key sensors.',
         'When this head is high the overall pattern is abnormal, even if individual sensors are only mildly off.'),
        ('OMR_Z',      'Operating mode residual',
         'Measures mismatch between current regime model and observed behaviour.',
         'High residuals can indicate the asset is in between known regimes or the regime model is stale.'),
        ('PCA_SPE_Z',  'PCA SPE',
         'Monitors unexplained variation outside the PCA model (Squared Prediction Error).',
         'Elevated SPE means new variation pattern; check for new noise, misalignment, or previously unseen states.'),
        ('PCA_T2_Z',   'PCA T²',
         'Monitors variation within the PCA model along principal components.',
         'High T² usually means the asset is still behaving like known regimes but at an extreme operating point.')
    ) AS t(DetectorFamily, ShortName, Explanation, OperatorHint)
)
MERGE dbo.ACM_DetectorMetadata AS target
USING Meta AS src
    ON target.DetectorFamily = src.DetectorFamily
WHEN MATCHED THEN
    UPDATE SET
        ShortName   = src.ShortName,
        Explanation = src.Explanation,
        OperatorHint = src.OperatorHint
WHEN NOT MATCHED BY TARGET THEN
    INSERT (DetectorFamily, ShortName, Explanation, OperatorHint)
    VALUES (src.DetectorFamily, src.ShortName, src.Explanation, src.OperatorHint);
GO

PRINT 'ACM_DetectorMetadata ensured and seeded.';
GO

