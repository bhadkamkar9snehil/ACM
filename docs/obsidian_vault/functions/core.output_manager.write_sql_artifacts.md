---
type: function
id: core.output_manager.write_sql_artifacts
module: core.output_manager
source: core/output_manager.py
line_start: 3585
line_end: 3723
---

# core.output_manager.write_sql_artifacts

Defined in: [[modules/core.output_manager]]

Source: `core/output_manager.py:3585`

Kind: `function`

Signature: `write_sql_artifacts(output_manager: 'OutputManager', frame: pd.DataFrame, episodes: pd.DataFrame, train: pd.DataFrame, pca_detector: Optional[Any], sql_client: Optional[Any], run_id: Optional[str], equip_id: int, equip: str, cfg: Dict[str, Any], meta: Any, win_start: Optional[pd.Timestamp], win_end: Optional[pd.Timestamp], rows_read: int, spe_p95_train: float, t2_p95_train: float, anomaly_count: int, T: Any, culprit_writer_func: Optional[Callable]=None)`

Summary: Write SQL-specific artifacts: DriftTS, AnomalyEvents, RegimeEpisodes, PCA, RunStats, Culprits.
