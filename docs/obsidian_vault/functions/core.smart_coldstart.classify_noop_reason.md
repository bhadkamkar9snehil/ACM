---
type: function
id: core.smart_coldstart.classify_noop_reason
module: core.smart_coldstart
source: core/smart_coldstart.py
line_start: 21
line_end: 53
generated_at: 2026-02-21T03:35:55+00:00
tags:
  - acm
  - function
---

# core.smart_coldstart.classify_noop_reason

Defined in: [[modules/core.smart_coldstart|core.smart_coldstart]]

Source: `core/smart_coldstart.py:21`

Kind: `function`

Signature: `classify_noop_reason(train: Optional[pd.DataFrame], score: Optional[pd.DataFrame], meta: Optional[Any]=None, coldstart_complete: Optional[bool]=None)`

Summary: Deterministic NOOP classification used by the ACM pipeline.
