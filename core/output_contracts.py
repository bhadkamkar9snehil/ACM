"""
Output table contracts shared by OutputManager and callsites.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, Literal, Optional, Tuple

# =============================================================================
# ALLOWED_TABLES - v11.0.0 Functionality-Based Table Set
# =============================================================================
# DESIGN PRINCIPLE: Tables chosen based on ACM's core mission:
#   1. What is current health? (HealthTimeline, Scores, Episodes)
#   2. If not healthy, what's the reason? (SensorDefects, Hotspots, Culprits)
#   3. What will future health look like? (RUL, Forecasts)
#   4. What will cause future degradation? (SensorForecast, Drift, Contributions)
#
# Additional tables support: data persistence, model evolution, diagnostics
#
# See docs/ACM_OUTPUT_TABLES_REFINED.md for complete rationale.
#
# TIER 1 - CURRENT STATE (What's happening NOW?)
# TIER 2 - FUTURE STATE (What will happen?)
# TIER 3 - ROOT CAUSE (WHY is this happening/will happen?)
# TIER 4 - DATA & MODEL MANAGEMENT (Long-term storage, model building)
# TIER 5 - OPERATIONS & AUDIT (Is ACM working? What changed?)
# TIER 6 - ADVANCED ANALYTICS (Deep patterns and trends)
# TIER 7 - V11 NEW FEATURES (Typed contracts, maturity lifecycle, seasonality)
# =============================================================================

ALLOWED_TABLES = {
    # TIER 1: CURRENT STATE (6 tables) - Answers "What is current health?"
    "ACM_HealthTimeline",
    "ACM_Scores_Wide",
    "ACM_Episodes",
    "ACM_RegimeTimeline",
    "ACM_SensorDefects",
    "ACM_SensorHotspots",
    # TIER 2: FUTURE STATE (5 tables)
    "ACM_RUL",
    "ACM_HealthForecast",
    "ACM_FailureForecast",
    "ACM_SensorForecast",
    "ACM_MultivariateForecast",
    # TIER 3: ROOT CAUSE (7 tables)
    "ACM_EpisodeCulprits",
    "ACM_EpisodeDiagnostics",
    "ACM_DetectorCorrelation",
    "ACM_DriftSeries",
    "ACM_SensorCorrelations",
    "ACM_FeatureDropLog",
    "ACM_OMR_Diagnostics",
    # TIER 4: DATA & MODEL MANAGEMENT
    "ACM_BaselineBuffer",
    "ACM_HistorianData",
    "ACM_SensorNormalized_TS",
    "ACM_DataQuality",
    "ACM_ForecastingState",
    "ACM_CalibrationSummary",
    "ACM_AdaptiveConfig",
    "ACM_RefitRequests",
    "ACM_PCA_Metrics",
    "ACM_RunMetadata",
    "ACM_RepresentationStatus",
    "ACM_SignalProfiles",
    "ACM_RepresentationSchemas",
    "ACM_BaselineGovernance",
    # TIER 5: OPERATIONS & AUDIT
    "ACM_Runs",
    "ACM_RunLogs",
    "ACM_RunMetrics",
    "ACM_Run_Stats",
    "ACM_Config",
    "ACM_ConfigHistory",
    # TIER 6: ADVANCED ANALYTICS
    "ACM_RegimeOccupancy",
    "ACM_RegimeTransitions",
    "ACM_Regime_Episodes",
    "ACM_RegimePromotionLog",
    "ACM_RegimeState",
    "ACM_ContributionTimeline",
    "ACM_DriftController",
    "ACM_PCA_Models",
    "ACM_PCA_Loadings",
    "ACM_Anomaly_Events",
    # TIER 7: V11 NEW FEATURES
    "ACM_RegimeDefinitions",
    "ACM_ActiveModels",
    "ACM_DataContractValidation",
    "ACM_SeasonalPatterns",
}

# Table-level replace semantics (delete matching keys, then insert payload).
# Centralized here so callsites do not maintain duplicate key definitions.
REPLACE_POLICY_KEYS: Dict[str, Tuple[str, ...]] = {
    "ACM_HealthForecast": ("RunID", "EquipID", "Timestamp"),
    "ACM_FailureForecast": ("RunID", "EquipID", "Timestamp"),
    "ACM_RUL": ("RunID", "EquipID"),
    "ACM_SensorForecast": ("RunID", "EquipID", "SensorName", "Timestamp"),
    "ACM_MultivariateForecast": ("RunID", "EquipID", "Timestamp"),
    "ACM_OMR_Diagnostics": ("RunID", "EquipID"),
    "ACM_Anomaly_Events": ("RunID", "EquipID"),
    "ACM_Regime_Episodes": ("RunID", "EquipID"),
    "ACM_PCA_Models": ("RunID", "EquipID"),
    "ACM_DetectorCorrelation": ("RunID", "EquipID"),
    "ACM_DriftSeries": ("RunID", "EquipID"),
    "ACM_DriftController": ("RunID", "EquipID"),
    "ACM_DataContractValidation": ("RunID", "EquipID"),
    "ACM_SeasonalPatterns": ("RunID", "EquipID"),
    "ACM_FeatureDropLog": ("RunID", "EquipID"),
    "ACM_CalibrationSummary": ("RunID", "EquipID"),
    "ACM_RegimeOccupancy": ("RunID", "EquipID"),
    "ACM_RegimeTransitions": ("RunID", "EquipID"),
    "ACM_ContributionTimeline": ("RunID", "EquipID"),
    "ACM_DataQuality": ("RunID", "EquipID", "CheckName", "sensor"),
    "ACM_PCA_Metrics": ("RunID", "EquipID"),
    "ACM_ActiveModels": ("EquipID",),
    "ACM_AdaptiveConfig": ("EquipID", "ConfigKey"),
    "ACM_RepresentationStatus": ("RunID", "EquipID", "Timestamp"),
    "ACM_SignalProfiles": ("RunID", "EquipID", "Timestamp", "SignalName"),
    "ACM_RepresentationSchemas": ("RunID", "EquipID", "Timestamp"),
    "ACM_BaselineGovernance": ("RunID", "EquipID", "Timestamp"),
}


@dataclass(frozen=True)
class TableWriteContract:
    """Canonical write behavior for a SQL output table."""
    table_name: str
    mode: Literal["insert", "replace"] = "insert"
    key_columns: Tuple[str, ...] = ()
    required: bool = False


def _build_table_write_contracts() -> Dict[str, TableWriteContract]:
    contracts: Dict[str, TableWriteContract] = {
        t: TableWriteContract(table_name=t, mode="insert", key_columns=(), required=False)
        for t in ALLOWED_TABLES
    }
    for table_name, key_columns in REPLACE_POLICY_KEYS.items():
        contracts[table_name] = TableWriteContract(
            table_name=table_name,
            mode="replace",
            key_columns=tuple(key_columns),
            required=False,
        )

    # Core pipeline artifacts should be treated as required writes.
    contracts["ACM_Scores_Wide"] = TableWriteContract(
        table_name="ACM_Scores_Wide",
        mode=contracts["ACM_Scores_Wide"].mode,
        key_columns=contracts["ACM_Scores_Wide"].key_columns,
        required=True,
    )
    contracts["ACM_EpisodeDiagnostics"] = TableWriteContract(
        table_name="ACM_EpisodeDiagnostics",
        mode=contracts["ACM_EpisodeDiagnostics"].mode,
        key_columns=contracts["ACM_EpisodeDiagnostics"].key_columns,
        required=True,
    )
    return contracts


TABLE_WRITE_CONTRACTS: Dict[str, TableWriteContract] = _build_table_write_contracts()


def get_table_write_contract(table_name: str) -> Optional[TableWriteContract]:
    """Return canonical write contract for a table, or None if unknown."""
    return TABLE_WRITE_CONTRACTS.get(table_name)


def audit_replace_policy_contract() -> Dict[str, Any]:
    """Validate centralized replace-key contract shape and table references."""
    configured_tables = set(REPLACE_POLICY_KEYS)
    invalid_tables = sorted(configured_tables - set(ALLOWED_TABLES))
    empty_key_tables = sorted([t for t, keys in REPLACE_POLICY_KEYS.items() if not keys])
    return {
        "configured_count": len(REPLACE_POLICY_KEYS),
        "invalid_tables": invalid_tables,
        "empty_key_tables": empty_key_tables,
        "is_valid": not invalid_tables and not empty_key_tables,
    }


def audit_table_write_contracts() -> Dict[str, Any]:
    """Validate canonical write contracts against allowed table set."""
    configured_tables = set(TABLE_WRITE_CONTRACTS)
    allowed_tables = set(ALLOWED_TABLES)
    missing_contracts = sorted(allowed_tables - configured_tables)
    invalid_contracts = sorted(configured_tables - allowed_tables)
    bad_replace = sorted(
        [
            t for t, c in TABLE_WRITE_CONTRACTS.items()
            if c.mode == "replace" and not c.key_columns
        ]
    )
    return {
        "allowed_count": len(allowed_tables),
        "contract_count": len(TABLE_WRITE_CONTRACTS),
        "missing_contracts": missing_contracts,
        "invalid_contracts": invalid_contracts,
        "replace_without_keys": bad_replace,
        "is_valid": not missing_contracts and not invalid_contracts and not bad_replace,
    }
