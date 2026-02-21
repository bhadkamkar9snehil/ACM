---
type: method
id: core.output_manager.OutputManager.release_persist_memory
module: core.output_manager
source: core/output_manager.py
line_start: 3128
line_end: 3151
---

# core.output_manager.OutputManager.release_persist_memory

Defined in: [[modules/core.output_manager]]

Source: `core/output_manager.py:3128`

Kind: `method`

Signature: `release_persist_memory(self, raw_train: Optional[pd.DataFrame], raw_score: Optional[pd.DataFrame], iforest_detector: Optional[Any]=None, omr_detector: Optional[Any]=None)`

Summary: Free large persist-phase objects after SQL writes are complete.
