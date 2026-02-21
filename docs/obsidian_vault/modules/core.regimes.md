---
type: module
module: core.regimes
source: core/regimes.py
---

# core.regimes

Source file: `core/regimes.py`

Summary: no module docstring summary

## Imports from core
- [[modules/core.observability]]

## Top-level symbols
- [[functions/core.regimes.ModelVersionMismatch]] (line 115, class)
- [[functions/core.regimes._parse_semver]] (line 119, function)
- [[functions/core.regimes._is_version_compatible]] (line 132, function)
- [[functions/core.regimes._cfg_get]] (line 189, function)
- [[functions/core.regimes._as_f32]] (line 213, function)
- [[functions/core.regimes._IdentityScaler]] (line 220, class)
- [[functions/core.regimes._IdentityScaler.__init__]] (line 226, method)
- [[functions/core.regimes._IdentityScaler.fit]] (line 230, method)
- [[functions/core.regimes._IdentityScaler.transform]] (line 233, method)
- [[functions/core.regimes._IdentityScaler.fit_transform]] (line 236, method)
- [[functions/core.regimes._regime_metadata_dict]] (line 240, function)
- [[functions/core.regimes._stable_int_hash]] (line 255, function)
- [[functions/core.regimes._finite_impute_inplace]] (line 270, function)
- [[functions/core.regimes._robust_scale_clip]] (line 284, function)
- [[functions/core.regimes._compute_sample_durations]] (line 303, function)
- [[functions/core.regimes._validate_regime_inputs]] (line 344, function)
- [[functions/core.regimes._validate_regime_config]] (line 368, function)
- [[functions/core.regimes.RegimeModel]] (line 386, class)
- [[functions/core.regimes.RegimeModel.cluster_centers_]] (line 427, method)
- [[functions/core.regimes.RegimeModel.n_clusters]] (line 440, method)
- [[functions/core.regimes.RegimeModel.is_gmm]] (line 452, method)
- [[functions/core.regimes.RegimeModel.is_hdbscan]] (line 457, method)
- [[functions/core.regimes.RegimeModel.set_cluster_centers_]] (line 463, method)
- [[functions/core.regimes.RegimeModel.model]] (line 477, method)
- [[functions/core.regimes.RegimeModel.apply_label_map]] (line 484, method)
- [[functions/core.regimes._compute_training_distances]] (line 508, function)
- [[functions/core.regimes._classify_tag]] (line 580, function)
- [[functions/core.regimes._compute_basis_signature]] (line 625, function)
- [[functions/core.regimes.build_feature_basis]] (line 648, function)
- [[functions/core.regimes._fit_gmm_scaled]] (line 840, function)
- [[functions/core.regimes._compute_hdbscan_centroids]] (line 978, function)
- [[functions/core.regimes._fit_hdbscan_scaled]] (line 1002, function)
- [[functions/core.regimes.fit_regime_model]] (line 1260, function)
- [[functions/core.regimes.predict_regime]] (line 1583, function)
- [[functions/core.regimes.predict_regime_with_confidence]] (line 1686, function)
- [[functions/core.regimes.update_health_labels]] (line 1845, function)
- [[functions/core.regimes.identify_normal_regime]] (line 1974, function)
- [[functions/core.regimes._generate_regime_semantic_labels]] (line 2039, function)
- [[functions/core.regimes._persist_regime_error]] (line 2107, function)
- [[functions/core.regimes.build_summary_dataframe]] (line 2115, function)
- [[functions/core.regimes.smooth_labels]] (line 2226, function)
- [[functions/core.regimes.smooth_transitions]] (line 2397, function)
- [[functions/core.regimes._to_datetime_mixed]] (line 2513, function)
- [[functions/core.regimes._read_episodes_csv]] (line 2519, function)
- [[functions/core.regimes._read_scores_csv]] (line 2622, function)
- [[functions/core.regimes._fit_auto_k]] (line 2721, function)
- [[functions/core.regimes.regime_model_to_state]] (line 2815, function)
- [[functions/core.regimes.regime_state_to_model]] (line 2890, function)
- [[functions/core.regimes.align_regime_labels]] (line 2971, function)
- [[functions/core.regimes.label]] (line 3098, function)
- [[functions/core.regimes._legacy_label]] (line 3243, function)
- [[functions/core.regimes.run]] (line 3340, function)
- [[functions/core.regimes.save_regime_model]] (line 3562, function)
- [[functions/core.regimes.load_regime_model]] (line 3612, function)
- [[functions/core.regimes.detect_transient_states]] (line 3694, function)
- [[functions/core.regimes.apply_regime_health_labels]] (line 3855, function)
- [[functions/core.regimes.apply_transient_state_labels]] (line 3901, function)
- [[functions/core.regimes.write_regime_occupancy_and_transitions]] (line 3930, function)
- [[functions/core.regimes.write_regime_definitions_for_audit]] (line 4001, function)
