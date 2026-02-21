---
type: function
id: core.pipeline_types.validate_data_contract_at_entry
module: core.pipeline_types
source: core/pipeline_types.py
line_start: 640
line_end: 726
---

# core.pipeline_types.validate_data_contract_at_entry

Defined in: [[modules/core.pipeline_types|core.pipeline_types]]

Source: `core/pipeline_types.py:640`

Kind: `function`

Signature: `validate_data_contract_at_entry(train: pd.DataFrame, score: pd.DataFrame, meta: Any, refit_requested: bool, cfg: Dict[str, Any], output_manager: Any, equip_id: int, equip: str, run_id: Optional[str], logger: Any)`

Summary: Validate pipeline entry data against DataContract and persist validation output.
