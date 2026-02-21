---
type: function
id: core.regimes._read_scores_csv
module: core.regimes
source: core/regimes.py
line_start: 2622
line_end: 2714
generated_at: 2026-02-21T06:37:09+00:00
---

# core.regimes._read_scores_csv

Defined in: [[modules/core.regimes|core.regimes]]

Source: `core/regimes.py:2622`

Kind: `function`

Signature: `_read_scores_csv(p: Path, sql_client=None, equip_id: Optional[int]=None, run_id: Optional[str]=None, start_ts: Optional[pd.Timestamp]=None, end_ts: Optional[pd.Timestamp]=None)`

Summary: Read scores from SQL (preferred) or CSV fallback.
