---
type: module
module: core.pipeline_types
source: core/pipeline_types.py
generated_at: 2026-02-21T06:33:21+00:00
tags:
  - acm
  - module
---

# core.pipeline_types

Source file: `core/pipeline_types.py`

Summary: ACM Pipeline Types - v11.8.0

## Imports from core
- none

## Top-level symbols
- [[functions/core.pipeline_types.SensorMeta|core.pipeline_types.SensorMeta]] (line 30, class)
- [[functions/core.pipeline_types.DataContract|core.pipeline_types.DataContract]] (line 40, class)
- [[functions/core.pipeline_types.DataContract.validate|core.pipeline_types.DataContract.validate]] (line 85, method)
- [[functions/core.pipeline_types.DataContract.get_available_sensors|core.pipeline_types.DataContract.get_available_sensors]] (line 156, method)
- [[functions/core.pipeline_types.DataContract.to_dict|core.pipeline_types.DataContract.to_dict]] (line 161, method)
- [[functions/core.pipeline_types.DataContract.from_dict|core.pipeline_types.DataContract.from_dict]] (line 176, method)
- [[functions/core.pipeline_types.DataContract.signature|core.pipeline_types.DataContract.signature]] (line 190, method)
- [[functions/core.pipeline_types.ValidationResult|core.pipeline_types.ValidationResult]] (line 197, class)
- [[functions/core.pipeline_types.ValidationResult.__bool__|core.pipeline_types.ValidationResult.__bool__]] (line 205, method)
- [[functions/core.pipeline_types.ValidationResult.summary|core.pipeline_types.ValidationResult.summary]] (line 208, method)
- [[functions/core.pipeline_types.SensorValidator|core.pipeline_types.SensorValidator]] (line 223, class)
- [[functions/core.pipeline_types.SensorValidator.__init__|core.pipeline_types.SensorValidator.__init__]] (line 236, method)
- [[functions/core.pipeline_types.SensorValidator.validate|core.pipeline_types.SensorValidator.validate]] (line 260, method)
- [[functions/core.pipeline_types.SensorValidator._infer_sensor_type|core.pipeline_types.SensorValidator._infer_sensor_type]] (line 321, method)
- [[functions/core.pipeline_types.SensorValidator.filter_valid_sensors|core.pipeline_types.SensorValidator.filter_valid_sensors]] (line 344, method)
- [[functions/core.pipeline_types.FeatureMatrix|core.pipeline_types.FeatureMatrix]] (line 397, class)
- [[functions/core.pipeline_types.FeatureMatrix.get_regime_inputs|core.pipeline_types.FeatureMatrix.get_regime_inputs]] (line 429, method)
- [[functions/core.pipeline_types.FeatureMatrix.get_detector_inputs|core.pipeline_types.FeatureMatrix.get_detector_inputs]] (line 451, method)
- [[functions/core.pipeline_types.FeatureMatrix.signature|core.pipeline_types.FeatureMatrix.signature]] (line 455, method)
- [[functions/core.pipeline_types.GuardrailResult|core.pipeline_types.GuardrailResult]] (line 471, class)
- [[functions/core.pipeline_types.run_data_guardrails|core.pipeline_types.run_data_guardrails]] (line 481, function)
- [[functions/core.pipeline_types.run_data_guardrails_safe|core.pipeline_types.run_data_guardrails_safe]] (line 602, function)
- [[functions/core.pipeline_types.validate_data_contract_at_entry|core.pipeline_types.validate_data_contract_at_entry]] (line 640, function)
