---
type: module
module: core.fast_features
source: core/fast_features.py
generated_at: 2026-02-21T03:35:55+00:00
tags:
  - acm
  - module
---

# core.fast_features

Source file: `core/fast_features.py`

Summary: Fast feature builder (Polars-only API).

## Imports from core
- [[modules/core.observability|core.observability]]

## Top-level symbols
- [[functions/core.fast_features._rolling_kwargs|core.fast_features._rolling_kwargs]] (line 26, function)
- [[functions/core.fast_features._apply_fill|core.fast_features._apply_fill]] (line 33, function)
- [[functions/core.fast_features.ensure_local_index|core.fast_features.ensure_local_index]] (line 80, function)
- [[functions/core.fast_features.deduplicate_index|core.fast_features.deduplicate_index]] (line 106, function)
- [[functions/core.fast_features.rolling_median|core.fast_features.rolling_median]] (line 147, function)
- [[functions/core.fast_features.rolling_mad|core.fast_features.rolling_mad]] (line 159, function)
- [[functions/core.fast_features.rolling_mean_std|core.fast_features.rolling_mean_std]] (line 174, function)
- [[functions/core.fast_features.rolling_skew_kurt|core.fast_features.rolling_skew_kurt]] (line 187, function)
- [[functions/core.fast_features.rolling_ols_slope|core.fast_features.rolling_ols_slope]] (line 205, function)
- [[functions/core.fast_features.ols_slope|core.fast_features.ols_slope]] (line 225, function)
- [[functions/core.fast_features.rolling_spectral_energy|core.fast_features.rolling_spectral_energy]] (line 241, function)
- [[functions/core.fast_features.rolling_xcorr|core.fast_features.rolling_xcorr]] (line 300, function)
- [[functions/core.fast_features.rolling_pairwise_lag|core.fast_features.rolling_pairwise_lag]] (line 322, function)
- [[functions/core.fast_features.batched_pairwise_lag|core.fast_features.batched_pairwise_lag]] (line 389, function)
- [[functions/core.fast_features.compute_basic_features_pl|core.fast_features.compute_basic_features_pl]] (line 501, function)
- [[functions/core.fast_features.spectral_energy|core.fast_features.spectral_energy]] (line 619, function)
- [[functions/core.fast_features.goertzel_energy|core.fast_features.goertzel_energy]] (line 641, function)
- [[functions/core.fast_features.RegimeNormStats|core.fast_features.RegimeNormStats]] (line 701, class)
- [[functions/core.fast_features.RegimeNormStats.to_dict|core.fast_features.RegimeNormStats.to_dict]] (line 710, method)
- [[functions/core.fast_features.RegimeNormStats.from_dict|core.fast_features.RegimeNormStats.from_dict]] (line 722, method)
- [[functions/core.fast_features.NormalizationResult|core.fast_features.NormalizationResult]] (line 735, class)
- [[functions/core.fast_features.ConfidenceGatedNormalizer|core.fast_features.ConfidenceGatedNormalizer]] (line 743, class)
- [[functions/core.fast_features.ConfidenceGatedNormalizer.__init__|core.fast_features.ConfidenceGatedNormalizer.__init__]] (line 774, method)
- [[functions/core.fast_features.ConfidenceGatedNormalizer.fit_global|core.fast_features.ConfidenceGatedNormalizer.fit_global]] (line 790, method)
- [[functions/core.fast_features.ConfidenceGatedNormalizer.fit_regime|core.fast_features.ConfidenceGatedNormalizer.fit_regime]] (line 840, method)
- [[functions/core.fast_features.ConfidenceGatedNormalizer.has_regime_stats|core.fast_features.ConfidenceGatedNormalizer.has_regime_stats]] (line 899, method)
- [[functions/core.fast_features.ConfidenceGatedNormalizer.normalize|core.fast_features.ConfidenceGatedNormalizer.normalize]] (line 903, method)
- [[functions/core.fast_features.ConfidenceGatedNormalizer.get_stats_summary|core.fast_features.ConfidenceGatedNormalizer.get_stats_summary]] (line 999, method)
- [[functions/core.fast_features.ConfidenceGatedNormalizer.to_dict|core.fast_features.ConfidenceGatedNormalizer.to_dict]] (line 1014, method)
- [[functions/core.fast_features.ConfidenceGatedNormalizer.from_dict|core.fast_features.ConfidenceGatedNormalizer.from_dict]] (line 1027, method)
- [[functions/core.fast_features.normalize_with_confidence_gating|core.fast_features.normalize_with_confidence_gating]] (line 1048, function)
- [[functions/core.fast_features.build_features_for_pipeline|core.fast_features.build_features_for_pipeline]] (line 1165, function)
- [[functions/core.fast_features.impute_features|core.fast_features.impute_features]] (line 1224, function)
