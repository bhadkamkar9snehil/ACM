"""Canonical ML defaults for ACM.

These are the validated machine-learning parameters of the product — promoted
from configuration into code. ML behaviour must be deterministic and
identical on every deployment; configuration (configs/config_table.csv) is
reserved for things a HUMAN should change: data sources, SQL connection,
runtime scheduling, reporting. Nothing in this file is meant to be edited per
site; changing detector behaviour is a product change, made here, in code,
under version control.

Auto-tuned parameters (fusion weights, calibration clip, alarm thresholds)
still adapt at runtime per asset — these are their starting points.
"""

ML_DEFAULTS = {
    "continuous_learning": {
        "enabled": True,
        "model_update_interval": 1,
        "threshold_update_interval": 1
    },
    "drift": {
        "cusum": {
            "drift": 0.1,
            "smoothing_alpha": 0.3,
            "threshold": 2.0
        },
        "multi_feature": {
            "enabled": True,
            "fused_drift_max": 5.0,
            "fused_drift_min": 2.0,
            "hysteresis_off": 1.5,
            "hysteresis_on": 3.0,
            "regime_volatility_max": 0.3,
            "trend_threshold": 0.05,
            "trend_window": 20
        },
        "p95_threshold": 2.0
    },
    "episodes": {
        "cpd": {
            "auto_tune": {
                "enabled": True,
                "h_factor": 1.2,
                "k_factor": 0.8
            },
            "h_sigma": 12.0,
            "k_sigma": 2.0
        },
        "gap_merge": 5,
        "min_len": 3
    },
    "features": {
        "fft_bands": [
            0.0,
            0.1,
            0.3,
            0.5
        ],
        "fs_hz": 1.0,
        "polars_threshold": 10,
        "top_k_tags": 5,
        "window": 16
    },
    "fusion": {
        "auto_tune": {
            "enabled": True,
            "fallback_method": "statistical_diversity",
            "learning_rate": 0.3,
            "method": "episode_separability",
            "min_weight": 0.05,
            "require_external_labels": False,
            "temperature": 1.5,
            "warm_start_lr": 0.7
        },
        "cooldown": 10,
        "min_silent_gap": 10,
        "omr_correlation_disable_threshold": 0.95,
        "per_regime": True,
        "robust_q_hi": 0.95,
        "robust_q_lo": 0.05,
        "weights": {
            "ar1_z": 0.2,
            "gmm_z": 0.05,
            "iforest_z": 0.15,
            "omr_z": 0.1,
            "pca_spe_z": 0.3,
            "pca_t2_z": 0.2
        }
    },
    "health": {
        "extreme_z_threshold": 10.0,
        "max_change_per_period": 20.0,
        "smoothing_alpha": 0.3,
        "steepness": 1.5,
        "z_threshold": 5.0
    },
    "lifecycle": {
        "promotion": {
            "min_consecutive_runs": 3,
            "min_silhouette_score": 0.15,
            "min_stability_ratio": 0.6,
            "min_training_days": 7,
            "min_training_rows": 200
        }
    },
    "models": {
        "ar1": {
            "alpha": 0.05,
            "enabled": True,
            "smoothing": 1,
            "window": 256,
            "z_cap": 8.0
        },
        "auto_retrain": {
            "enabled": True,
            "max_anomaly_rate": 0.25,
            "max_drift_score": 2.0,
            "max_model_age_hours": 720,
            "min_regime_quality": 0.3,
            "on_tuning_change": False
        },
        "gmm": {
            "covariance_type": "diag",
            "enable_bic_search": True,
            "enabled": True,
            "eps_jitter": 1e-06,
            "k_max": 3,
            "k_min": 2,
            "max_iter": 100,
            "n_init": 3,
            "random_state": 42,
            "reg_covar": 0.001,
            "tol": 0.001,
            "use_bayesian_if_slow": False
        },
        "iforest": {
            "bootstrap": True,
            "contamination": 0.01,
            "enabled": True,
            "max_samples": 2048,
            "n_estimators": 100,
            "random_state": 17,
            "warm_start": True
        },
        "max_model_age_days": 30,
        "max_train_samples": 10000,
        "omr": {
            "min_samples": 100,
            "model_type": "auto",
            "n_components": 5
        },
        "pca": {
            "batch_size": 4096,
            "incremental": False,
            "n_components": 5,
            "random_state": 17,
            "svd_solver": "randomized"
        },
        "use_cache": True
    },
    "regimes": {
        "auto_k": {
            "k_max": 6,
            "k_min": 2,
            "max_eval_samples": 5000,
            "max_models": 10,
            "pca_dim": 20,
            "random_state": 17,
            "sil_sample": 4000
        },
        "clip_pct": 99.9,
        "clustering": {
            "fallback_method": "gmm",
            "method": "hdbscan"
        },
        "feature_basis": {
            "n_pca_components": 3,
            "operational_keywords": [
                "temp",
                "load",
                "speed",
                "flow",
                "pressure",
                "rpm",
                "power",
                "current",
                "voltage",
                "ambient",
                "inlet",
                "outlet",
                "bearing",
                "winding"
            ],
            "raw_tags": [],
            "use_raw_sensors": True
        },
        "hdbscan": {
            "cluster_selection_method": "eom",
            "dbcv_min": 0.1,
            "max_noise_ratio": 0.3,
            "metric": "euclidean",
            "min_cluster_size": 10,
            "min_samples": 3
        },
        "health": {
            "fused_alert_z": 4.0,
            "fused_warn_z": 2.5
        },
        "normal_identification": {
            "enabled": True,
            "max_median_fused": 2.0,
            "min_dwell_fraction": 0.15
        },
        "quality": {
            "calinski_min": 50.0,
            "silhouette_min": 0.3
        },
        "smoothing": {
            "min_dwell_samples": 10,
            "min_dwell_seconds": 900,
            "passes": 3,
            "window": 7
        },
        "transient_detection": {
            "roc_threshold_high": 0.15,
            "roc_threshold_trip": 0.3,
            "roc_window": 10
        },
        "unknown": {
            "distance_percentile": 99.0,
            "distance_threshold_floor_ratio": 1.5,
            "enabled": True
        }
    },
    "thresholds": {
        "adaptive": {
            "confidence": 0.997,
            "enabled": True,
            "fallback_threshold": 3.0,
            "method": "quantile",
            "min_samples": 100,
            "per_regime": True
        },
        "alert": 3.0,
        "contamination_filter": {
            "enabled": True,
            "max_iterations": 10,
            "method": "iterative_mad",
            "min_retained_ratio": 0.7,
            "z_threshold": 4.0
        },
        "q": 0.98,
        "self_tune": {
            "enabled": True,
            "max_clip_z": 100.0,
            "target_fp_rate": 0.001
        },
        "warn": 1.5
    }
}
