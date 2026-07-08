# core/outliers.py
"""
Outlier detection module.
Implements density-based anomaly detectors like Isolation Forest and GMM.

v11.1.1: Uses RobustScaler (median/IQR) instead of StandardScaler (mean/std)
to handle training data that may contain faults.
"""
from __future__ import annotations

import numpy as np
import pandas as pd
from sklearn.ensemble import IsolationForest
from sklearn.mixture import GaussianMixture
from sklearn.decomposition import PCA
from sklearn.preprocessing import RobustScaler  # ROBUST: Use RobustScaler instead of StandardScaler
from core.observability import Console, Span
from typing import Any, Dict, Optional, List


def _finite_impute(df: pd.DataFrame) -> pd.DataFrame:
    if not isinstance(df, pd.DataFrame):
        return df
    # Vectorized median imputation for non-finites
    out = df.astype(float)
    # Replace inf/-inf with NaN, then fill with column medians
    out = out.replace([np.inf, -np.inf], np.nan)
    medians = out.median()
    medians = medians.fillna(0.0)  # For all-NaN columns
    out = out.fillna(medians)
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
        with Span("fit.iforest", n_samples=len(X), n_features=X.shape[1] if len(X) > 0 else 0):
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
        with Span("score.iforest", n_samples=len(X), n_features=X.shape[1] if len(X) > 0 else 0):
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
        # ROBUST: Use RobustScaler (median/IQR) instead of StandardScaler (mean/std)
        # This makes GMM robust to training data containing faults
        self.scaler = RobustScaler(with_centering=True, with_scaling=True)
        self._is_fitted = False
        self._fitted_params = {}
        self._var_mask = None
        self._columns_: Optional[List[str]] = None
        self._score_mu_: Optional[float] = None
        self._score_sd_: Optional[float] = None
        self._pca_: Optional[PCA] = None

    def fit(self, X: pd.DataFrame) -> "GMMDetector":
        """Fits the GMM on the training data."""
        with Span("fit.gmm", n_samples=len(X), n_features=X.shape[1] if len(X) > 0 else 0):
            if X.empty:
                return self
            Xc = _finite_impute(X)
            self._columns_ = list(Xc.columns)
            Xn = Xc.to_numpy(dtype=np.float64, copy=False)

            # Drop constant features
            var = Xn.var(axis=0)
            self._var_mask = (var > 0)
            if not np.any(self._var_mask):
                Console.warn("All features constant — disabling GMM.", component="GMM")
                self._is_fitted = False
                return self
            Xn = Xn[:, self._var_mask]

            n_samples, n_features = Xn.shape
            if n_features < 1 or n_samples < 2:
                Console.warn("Not enough data after preprocessing — disabling GMM.", component="GMM")
                self._is_fitted = False
                return self

            Xs = self.scaler.fit_transform(Xn).astype(np.float64, copy=False)

            # Bound per-feature scaled magnitude before PCA. RobustScaler's
            # IQR can collapse to near-zero for columns with heavy point-mass
            # at the median (e.g. engineered slope/skew features during flat
            # regimes), which explodes ordinary variation into z-magnitudes
            # of 1e8+ and lets a handful of such columns dominate PCA's
            # variance-based component selection. Clipping (not flooring the
            # scale itself) preserves RobustScaler's outlier-robust semantics
            # for well-behaved columns while bounding worst-case influence —
            # same convention as AR1's z_cap and ScoreCalibrator's clip_z.
            feat_z_clip = float(self.gmm_cfg.get("feature_z_clip", 8.0))
            np.clip(Xs, -feat_z_clip, feat_z_clip, out=Xs)

            # Components: cap by samples; keep a small heuristic limit
            heuristic = int(max(2, np.sqrt(n_samples) / 2))
            safe_k = max(2, min(self._user_k, heuristic, n_samples - 1, 32))

            # Use config for trial parameters
            cov_type = self.gmm_cfg.get("covariance_type", "diag")
            reg_covar = float(self.gmm_cfg.get("reg_covar", 1e-2)) # Increased default for stability (1e-2)

            # PCA pre-reduction: a diagonal-covariance GMM estimates 2 params
            # (mean, variance) per feature per component. Engineered feature
            # counts scale with raw sensor count (~7-8 derived cols/channel),
            # so wide-sensor assets can starve variance estimates of data
            # (e.g. <1 sample/feature/component) producing unreliable
            # likelihoods, while narrow assets are comfortably over-determined.
            # Reducing to orthogonal PCA components caps the parameter count
            # independent of raw feature count, and also better satisfies the
            # per-feature independence assumption diag-covariance relies on
            # (cf. Tipping & Bishop 1999, Mixtures of Probabilistic PCA).
            self._pca_ = None
            k_max_cfg = max(2, int(self.gmm_cfg.get("k_max", 3)))
            k_for_budget = max(2, min(safe_k, k_max_cfg))
            samples_per_param = float(self.gmm_cfg.get("min_samples_per_param", 10.0))
            d_budget = max(2, int(n_samples / max(1.0, samples_per_param * k_for_budget * 2)))
            max_components_cfg = int(self.gmm_cfg.get("max_pca_components", 25))
            pca_dim = min(n_features, max_components_cfg, d_budget)
            if pca_dim < n_features:
                try:
                    # whiten=True rescales each component to unit variance.
                    # Without it, low-variance trailing components leave the
                    # diag-covariance GMM with near-zero variance estimates on
                    # some axes, which sklearn rejects as "ill-defined
                    # empirical covariance" regardless of reg_covar.
                    pca = PCA(
                        n_components=pca_dim,
                        whiten=True,
                        svd_solver="auto",
                        random_state=int(self.gmm_cfg.get("random_state", 42)),
                    )
                    Xs = pca.fit_transform(Xs).astype(np.float64, copy=False)
                    self._pca_ = pca
                    Console.info(
                        f"PCA pre-reduction: {n_features} -> {pca_dim} components "
                        f"(n_samples={n_samples}, k_budget={k_for_budget})",
                        component="GMM",
                    )
                except Exception as e:
                    Console.warn(f"PCA pre-reduction failed: {str(e)[:100]}", component="GMM")
                    self._pca_ = None

            # If BIC search is enabled, find best k
            if self.gmm_cfg.get("enable_bic_search", True) and safe_k > 2:
                bics = []
                k_range = range(max(2, self.gmm_cfg.get("k_min", 2)), min(safe_k, self.gmm_cfg.get("k_max", 5)) + 1)
                bic_failed = False
                for k_test in k_range:
                    try:
                        gm_test = GaussianMixture(n_components=k_test, covariance_type=cov_type, reg_covar=reg_covar, random_state=17)
                        gm_test.fit(Xs)
                        bics.append(gm_test.bic(Xs))
                    except ValueError as e:
                        Console.warn(f"BIC search k={k_test} failed: {str(e)[:100]}", component="GMM")
                        bics.append(float('inf'))  # Mark as worst option
                        bic_failed = True
                if bics and min(bics) < float('inf'):
                    safe_k = k_range[np.argmin(bics)]
                    Console.info(f"BIC search selected k={safe_k}", component="GMM")
                elif bic_failed:
                    Console.warn("All BIC search attempts failed; using k=2 with fallback", component="GMM")
                    safe_k = 2

            # Simplified trial with configured parameters
            trials = [dict(covariance_type=cov_type, reg_covar=reg_covar)]

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
                        Console.info(f"Fitted k={k}, cov={params['covariance_type']}, reg={params['reg_covar']}", component="GMM")
                        # ROBUST: Calibrate scores using median/MAD instead of mean/std
                        # This makes z-score normalization robust to training outliers
                        tr_scores = -gm.score_samples(Xs)
                        self._score_mu_ = float(np.median(tr_scores))  # Use median
                        score_mad = float(np.median(np.abs(tr_scores - self._score_mu_)))
                        self._score_sd_ = float(score_mad * 1.4826 + 1e-9)  # MAD to std scale
                        return self
                    except Exception as e:
                        last_err = e
                        k -= 1
                        continue

            Console.warn(f"Disabled after retries: {last_err}", component="GMM")
            self._is_fitted = False
            return self

    def score(self, X: pd.DataFrame) -> np.ndarray:
        """
        Calculates the negative log-likelihood for each sample.
        Higher scores indicate a higher likelihood of being an anomaly.
        
        Memory-optimized v11.0.3: Explicit cleanup of intermediate arrays.
        """
        import gc
        with Span("score.gmm", n_samples=len(X), n_features=X.shape[1] if len(X) > 0 else 0):
            n_samples = len(X)
            if not self._is_fitted or self.model is None or self._var_mask is None:
                return np.zeros(n_samples, dtype=np.float32)
            
            Xc = _finite_impute(X)
            del X  # Free original DataFrame early
            
            if self._columns_ is not None:
                Xc = Xc.reindex(self._columns_, axis=1)
            
            # Extract numpy array and immediately delete DataFrame
            Xn = Xc.to_numpy(dtype=np.float64, copy=False)
            del Xc
            
            # Apply variance mask
            Xn = Xn[:, self._var_mask]
            
            # Scale in place (sklearn returns a new array anyway)
            Xs = self.scaler.transform(Xn).astype(np.float64, copy=False)
            del Xn

            # Same bound applied at fit time — must match exactly for
            # fit/score consistency (see comment in fit()).
            feat_z_clip = float(self.gmm_cfg.get("feature_z_clip", 8.0))
            np.clip(Xs, -feat_z_clip, feat_z_clip, out=Xs)

            # Apply the same PCA pre-reduction used at fit time, if any
            if self._pca_ is not None:
                Xs = self._pca_.transform(Xs).astype(np.float64, copy=False)

            # Score samples (this is where sklearn allocates memory internally)
            scores = -self.model.score_samples(Xs)
            del Xs
            
            # Convert to float32 for memory efficiency
            result = scores.astype(np.float32, copy=False)
            del scores
            
            # Force GC for large datasets
            if n_samples > 50000:
                gc.collect()
            
            return result

    def decision_function(self, X: pd.DataFrame) -> np.ndarray:
        raw = self.score(X).astype(np.float64, copy=False)
        if self._score_mu_ is None or self._score_sd_ is None:
            return raw.astype(np.float32, copy=False)
        z = (raw - self._score_mu_) / self._score_sd_
        return z.astype(np.float32, copy=False)