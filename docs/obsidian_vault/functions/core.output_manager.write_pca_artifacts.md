---
type: function
id: core.output_manager.write_pca_artifacts
module: core.output_manager
source: core/output_manager.py
line_start: 3424
line_end: 3556
generated_at: 2026-02-21T03:35:55+00:00
tags:
  - acm
  - function
---

# core.output_manager.write_pca_artifacts

Defined in: [[modules/core.output_manager|core.output_manager]]

Source: `core/output_manager.py:3424`

Kind: `function`

Signature: `write_pca_artifacts(output_manager: 'OutputManager', pca_detector: Any, frame: pd.DataFrame, train: pd.DataFrame, run_id: Optional[str], equip_id: int, equip: str, spe_p95_train: float, t2_p95_train: float, cfg: Dict[str, Any])`

Summary: Write PCA model, loadings, and metrics to SQL tables.
