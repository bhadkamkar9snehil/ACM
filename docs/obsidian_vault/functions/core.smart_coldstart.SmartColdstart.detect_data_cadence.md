---
type: method
id: core.smart_coldstart.SmartColdstart.detect_data_cadence
module: core.smart_coldstart
source: core/smart_coldstart.py
line_start: 161
line_end: 237
generated_at: 2026-02-21T03:35:55+00:00
tags:
  - acm
  - method
---

# core.smart_coldstart.SmartColdstart.detect_data_cadence

Defined in: [[modules/core.smart_coldstart|core.smart_coldstart]]

Source: `core/smart_coldstart.py:161`

Kind: `method`

Signature: `detect_data_cadence(self, table_name: str, sample_hours: int=24)`

Summary: Detect cadence using RECENT data (not earliest). Uses last `sample_hours` of data
