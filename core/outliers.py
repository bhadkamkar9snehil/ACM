# core/outliers.py
"""
Outlier detection module.
Implements density-based anomaly detectors like Isolation Forest and GMM.
"""
from __future__ import annotations

import numpy as np
import pandas as pd
from sklearn.ensemble import IsolationForest
from sklearn.mixture import GaussianMixture
from sklearn.preprocessing import StandardScaler
from utils.logger import Console
from typing import Any, Dict, Optional, List


def _finite_impute(df: pd.DataFrame) -> pd.DataFrame:
    if not isinstance(df, pd.DataFrame):
        return df
    # Per-column median imputation for non-finites
    out = df.copy()
    for c in out.columns:
        s = out[c]
        mask = ~np.isfinite(s.to_numpy(dtype=float, copy=False))
        if mask.any():
            med = np.nanmedian(s.astype(float))
            if not np.isfinite(med):
                med = 0.0
            s = s.astype(float)
            s[mask] = med
            out[c] = s
    return out

class IsolationForestDetector:
    """
    Detects outliers using the Isolation Forest algorithm.

    This model is effective at identifying anomalies by isolating observations.
    It works well on high-dimensional data and is computationally efficient.
    """
    def __init__(self, if_cfg: Dict[str, Any]):
        """
        Initializes the detector with Isolation Forest configuration.

        Args:
            if_cfg (Dict[str, Any]): Configuration for the Isolation Forest model,
                                     e.g., {'n_estimators': 100, 'contamination': 'auto'}.
        """
        self.model = IsolationForest(
            n_estimators=int(if_cfg.get("n_estimators", 100)),
            contamination=if_cfg.get("contamination", "auto"),
            random_state=int(if_cfg.get("random_state", 17)),
            n_jobs=-1,
            bootstrap=bool(if_cfg.get("bootstrap", False)),
            max_samples=if_cfg.get("max_samples", "auto"),
            warm_start=bool(if_cfg.get("warm_start", False)),
        )
        self._columns_: Optional[List[str]] = None
        self._threshold_: Optional[float] = None
        self._fitted_: bool = False

    def fit(self, X: pd.DataFrame) -> "IsolationForestDetector":
        """
        Fits the Isolation Forest model on the training data.

        Args:
            X (pd.DataFrame): The training feature matrix.
        """
        if not X.empty:
            Xc = _finite_impute(X)
            self._columns_ = list(Xc.columns)
            Xn = Xc.to_numpy(dtype=np.float32, copy=False)
            self.model.fit(Xn)
            self._fitted_ = True
            # Optional: set threshold if contamination is numeric
            cont = self.model.contamination
            if isinstance(cont, (int, float)) and 0 < cont < 0.5:
                train_scores = -self.model.score_samples(Xn)
                self._threshold_ = float(np.quantile(train_scores, 1.0 - cont))
        return self

    def score(self, X: pd.DataFrame) -> np.ndarray:
        """
        Calculates the anomaly score for each row in the input data.
        The score is inverted so that higher values indicate a higher likelihood of being an anomaly.

        Args:
            X (pd.DataFrame): The scoring feature matrix.

        Returns:
            np.ndarray: An array of anomaly scores.
        """
        # Guard: do not score if model hasn't been fitted.
        if not self._fitted_ or not hasattr(self.model, "estimators_"):
            return np.zeros(len(X), dtype=np.float32)
        Xc = _finite_impute(X)
        if self._columns_ is not None:
            Xc = Xc.reindex(self._columns_, axis=1)
        Xn = Xc.to_numpy(dtype=np.float32, copy=False)
        # score_samples returns the opposite of the anomaly score. We invert it.
        scores = -self.model.score_samples(Xn)
        return scores.astype(np.float32, copy=False)

    def decision_function(self, X: pd.DataFrame) -> np.ndarray:
        # Same as score(), provided for API parity
        return self.score(X)

    def predict(self, X: pd.DataFrame) -> np.ndarray:
        if self._threshold_ is None:
            # fallback: no threshold calibrated
            return np.zeros(len(X), dtype=np.int8)
        return (self.score(X) >= self._threshold_).astype(np.int8)

class GMMDetector:
    """
    Detects outliers using a Gaussian Mixture Model (GMM).

    This model assumes the data is generated from a mixture of a finite number of
    Gaussian distributions. Points with low probability density under the fitted
    model are considered outliers.
    """
    def __init__(self, gmm_cfg: Dict[str, Any]):
        """
        Initializes the detector with GMM configuration.

        Args:
            gmm_cfg (Dict[str, Any]): Configuration for the GMM, e.g.,
                                     {'n_components': 5, 'covariance_type': 'full'}.
        """
        self.gmm_cfg = gmm_cfg or {}
        def _coerce_int(val, default):
            try:
                v = int(float(val))
                return v if v > 1 else default
            except Exception:
                return default

        self._user_k = _coerce_int(self.gmm_cfg.get("n_components", 5), 5)
        self.model = None
        self.scaler = StandardScaler(with_mean=True, with_std=True)
        self._is_fitted = False
        self._fitted_params = {}
        self._var_mask = None
        self._columns_: Optional[List[str]] = None
        self._score_mu_: Optional[float] = None
        self._score_sd_: Optional[float] = None

    def fit(self, X: pd.DataFrame) -> "GMMDetector":
        """Fits the GMM on the training data."""
        if X.empty:
            return self
        Xc = _finite_impute(X)
        self._columns_ = list(Xc.columns)
        Xn = Xc.to_numpy(dtype=np.float64, copy=False)

        # Drop constant features
        var = Xn.var(axis=0)
        self._var_mask = (var > 0)
        if not np.any(self._var_mask):
            Console.warn("[GMM] All features constant — disabling GMM.")
            self._is_fitted = False
            return self
        Xn = Xn[:, self._var_mask]

        n_samples, n_features = Xn.shape
        if n_features < 1 or n_samples < 2:
            Console.warn("[GMM] Not enough data after preprocessing — disabling GMM.")
            self._is_fitted = False
            return self

        Xs = self.scaler.fit_transform(Xn).astype(np.float64, copy=False)

        # Components: cap by samples; keep a small heuristic limit
        heuristic = int(max(2, np.sqrt(n_samples) / 2))
        safe_k = max(2, min(self._user_k, heuristic, n_samples - 1, 32))

        # Use config for trial parameters
        cov_type = self.gmm_cfg.get("covariance_type", "diag")
        reg_covar = float(self.gmm_cfg.get("reg_covar", 1e-3)) # Increased default for stability
        
        # If BIC search is enabled, find best k
        if self.gmm_cfg.get("enable_bic_search", True) and safe_k > 2:
            bics = []
            k_range = range(max(2, self.gmm_cfg.get("k_min", 2)), min(safe_k, self.gmm_cfg.get("k_max", 5)) + 1)
            for k_test in k_range:
                gm_test = GaussianMixture(n_components=k_test, covariance_type=cov_type, reg_covar=reg_covar, random_state=17)
                gm_test.fit(Xs)
                bics.append(gm_test.bic(Xs))
            safe_k = k_range[np.argmin(bics)]
            Console.info(f"[GMM] BIC search selected k={safe_k}")

        # Simplified trial with configured parameters
        trials = [dict(covariance_type=cov_type, reg_covar=reg_covar)]

        last_err = None
        last_err = None
        for params in trials:
            k = safe_k
            while k >= 2:
                try:
                    gm = GaussianMixture(
                        n_components=k,
                        covariance_type=params["covariance_type"],
                        reg_covar=params["reg_covar"], # Use the resolved reg_covar
                        n_init=int(self.gmm_cfg.get("n_init", 3)), # Increased n_init for better convergence
                        max_iter=int(self.gmm_cfg.get("max_iter", 100)),
                        init_params=str(self.gmm_cfg.get("init_params", "kmeans")),
                        random_state=int(self.gmm_cfg.get("random_state", 42)),
                    )
                    gm.fit(Xs)
                    self.model = gm
                    self._is_fitted = True
                    self._fitted_params = dict(k=k, **params)
                    Console.info(f"[GMM] Fitted k={k}, cov={params['covariance_type']}, reg={params['reg_covar']}")
                    # Calibrate scores on training set for z-score decision_function
                    tr_scores = -gm.score_samples(Xs)
                    self._score_mu_ = float(np.mean(tr_scores))
                    self._score_sd_ = float(np.std(tr_scores) + 1e-9)
                    return self
                except Exception as e:
                    last_err = e
                    k -= 1
                    continue

        Console.warn(f"[GMM] Disabled after retries: {last_err}")
        self._is_fitted = False
        return self

    def score(self, X: pd.DataFrame) -> np.ndarray:
        """
        Calculates the negative log-likelihood for each sample.
        Higher scores indicate a higher likelihood of being an anomaly.
        """
        if not self._is_fitted or self.model is None or self._var_mask is None:
            return np.zeros(len(X), dtype=np.float32)
        Xc = _finite_impute(X)
        if self._columns_ is not None:
            Xc = Xc.reindex(self._columns_, axis=1)
        Xn = Xc.to_numpy(dtype=np.float64, copy=False)
        Xn = Xn[:, self._var_mask]
        Xs = self.scaler.transform(Xn).astype(np.float64, copy=False)
        scores = -self.model.score_samples(Xs)
        return scores.astype(np.float32, copy=False)

    def decision_function(self, X: pd.DataFrame) -> np.ndarray:
        raw = self.score(X).astype(np.float64, copy=False)
        if self._score_mu_ is None or self._score_sd_ is None:
            return raw.astype(np.float32, copy=False)
        z = (raw - self._score_mu_) / self._score_sd_
        return z.astype(np.float32, copy=False)