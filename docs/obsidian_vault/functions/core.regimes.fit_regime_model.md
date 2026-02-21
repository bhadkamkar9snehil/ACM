---
type: function
id: core.regimes.fit_regime_model
module: core.regimes
source: core/regimes.py
line_start: 1260
line_end: 1580
generated_at: 2026-02-21T06:37:09+00:00
---

# core.regimes.fit_regime_model

Defined in: [[modules/core.regimes|core.regimes]]

Source: `core/regimes.py:1260`

Kind: `function`

Signature: `fit_regime_model(train_basis: pd.DataFrame, basis_meta: Dict[str, Any], cfg: Dict[str, Any], train_hash: Optional[int])`

Summary: Fit regime clustering model using HDBSCAN (primary) or GMM (fallback).
