---
type: function
id: core.fast_features.impute_features
module: core.fast_features
source: core/fast_features.py
line_start: 1224
line_end: 1373
---

# core.fast_features.impute_features

Defined in: [[modules/core.fast_features|core.fast_features]]

Source: `core/fast_features.py:1224`

Kind: `function`

Signature: `impute_features(train: pd.DataFrame, score: pd.DataFrame, low_var_threshold: float, output_manager: Optional[Any]=None, run_id: Optional[str]=None, equip_id: int=0, equip: str='', protected_columns: Optional[List[str]]=None)`

Summary: Impute missing values and drop unusable columns from feature DataFrames.
