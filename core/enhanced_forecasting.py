"""
Enhanced Forecasting and RUL Analytics Module
==============================================

Provides analytically rigorous forecasting with:
- Multi-model ensemble health trajectory prediction
- Probabilistic failure prediction with confidence
- Detector-based causation analysis
- Intelligent maintenance recommendations

This module integrates with existing ACM pipeline to deliver
actionable insights for equipment maintenance.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Dict, Any, Optional, List, Tuple
import warnings

import numpy as np
import pandas as pd
from scipy import stats
from scipy.optimize import curve_fit

try:
    from utils.logger import Console
except ImportError:
    class Console:
        @staticmethod
        def info(msg: str): print(f"[INFO] {msg}")
        @staticmethod
        def warn(msg: str): print(f"[WARN] {msg}")
        @staticmethod
        def error(msg: str): print(f"[ERROR] {msg}")


@dataclass
class ForecastConfig:
    """Configuration for enhanced forecasting"""
    enabled: bool = True
    failure_threshold: float = 70.0
    forecast_horizons: List[int] = None  # [24, 72, 168] hours
    models: List[str] = None  # ['ar1', 'exponential', 'polynomial', 'ensemble']
    confidence_min: float = 0.6
    min_history_hours: float = 24.0
    max_forecast_hours: float = 168.0
    
    def __post_init__(self):
        if self.forecast_horizons is None:
            self.forecast_horizons = [24, 72, 168]
        if self.models is None:
            self.models = ['ar1', 'exponential', 'polynomial', 'ensemble']


@dataclass
class MaintenanceConfig:
    """Configuration for maintenance recommendations"""
    urgency_threshold: float = 50.0
    buffer_hours: int = 24
    risk_thresholds: Dict[str, float] = None
    
    def __post_init__(self):
        if self.risk_thresholds is None:
            self.risk_thresholds = {
                'low': 0.1,
                'medium': 0.3,
                'high': 0.5,
                'very_high': 0.7
            }


@dataclass
class CausationConfig:
    """Configuration for causation analysis"""
    min_detector_contribution: float = 10.0
    top_sensors_count: int = 10
    detector_criticality: Dict[str, float] = None
    
    def __post_init__(self):
        if self.detector_criticality is None:
            # Higher values indicate more critical failure modes
            self.detector_criticality = {
                'ar1': 0.9,  # Sensor failures are critical
                'pca_spe': 0.9,  # Correlation breaks are critical
                'pca_t2': 0.7,
                'iforest': 0.6,
                'gmm': 0.5,
                'mahl': 0.6,
                'omr': 0.8  # Model degradation is important
            }


class HealthForecaster:
    """Multi-model ensemble for health trajectory forecasting"""
    
    def __init__(self, config: ForecastConfig):
        self.config = config
    
    def forecast(
        self, 
        health_history: pd.Series,
        horizons: List[int]
    ) -> Dict[str, Any]:
        """
        Generate multi-model health forecasts
        
        Returns:
            Dictionary with forecasts, uncertainties, and model metadata
        """
        if len(health_history) < 20:
            Console.warn(f"[FORECAST] Insufficient history ({len(health_history)} points)")
            return self._empty_forecast()
        
        results = {}
        
        # Try each model
        if 'ar1' in self.config.models:
            results['ar1'] = self._forecast_ar1(health_history, horizons)
        
        if 'exponential' in self.config.models:
            results['exponential'] = self._forecast_exponential(health_history, horizons)
        
        if 'polynomial' in self.config.models:
            results['polynomial'] = self._forecast_polynomial(health_history, horizons)
        
        # Select best model or create ensemble
        if 'ensemble' in self.config.models and len(results) > 1:
            results['ensemble'] = self._create_ensemble(results, health_history)
        
        # Select final forecast
        best_model = self._select_best_model(results, health_history)
        final_forecast = results[best_model]
        final_forecast['selected_model'] = best_model
        
        return final_forecast
    
    def _forecast_ar1(
        self, 
        health_history: pd.Series, 
        horizons: List[int]
    ) -> Dict[str, Any]:
        """AR(1) with drift compensation"""
        y = health_history.values
        n = len(y)
        
        # Estimate AR(1) parameters
        mu = np.mean(y)
        y_centered = y - mu
        
        # Estimate phi
        if len(y_centered) > 1:
            phi = np.dot(y_centered[1:], y_centered[:-1]) / (np.dot(y_centered[:-1], y_centered[:-1]) + 1e-9)
            phi = np.clip(phi, -0.999, 0.999)  # Stability
        else:
            phi = 0.0
        
        # Estimate linear drift
        t = np.arange(n)
        alpha = np.polyfit(t, y, 1)[0]
        
        # Residual std
        pred_train = mu + phi * (np.roll(y, 1) - mu)
        pred_train[0] = mu
        residuals = y - pred_train
        sigma = np.std(residuals[1:]) if len(residuals) > 1 else 1.0
        
        # Forecast
        forecasts = []
        uncertainties = []
        last_val = y[-1]
        
        for h in horizons:
            # AR(1) forecast with drift
            forecast_h = mu + (phi ** h) * (last_val - mu) + alpha * h
            
            # Growing uncertainty
            if abs(phi) < 0.999:
                var_h = sigma**2 * (1 - phi**(2*h)) / (1 - phi**2 + 1e-9)
            else:
                var_h = sigma**2 * h
            sigma_h = np.sqrt(var_h)
            
            forecasts.append(forecast_h)
            uncertainties.append(sigma_h)
        
        # Fit quality
        ss_res = np.sum(residuals[1:]**2)
        ss_tot = np.sum((y - np.mean(y))**2)
        r_squared = 1 - (ss_res / (ss_tot + 1e-9))
        
        return {
            'forecasts': np.array(forecasts),
            'uncertainties': np.array(uncertainties),
            'horizons': horizons,
            'model': 'ar1',
            'params': {'phi': phi, 'mu': mu, 'alpha': alpha, 'sigma': sigma},
            'fit_quality': r_squared,
            'residual_std': sigma
        }
    
    def _forecast_exponential(
        self, 
        health_history: pd.Series, 
        horizons: List[int]
    ) -> Dict[str, Any]:
        """Exponential decay model for degradation"""
        y = health_history.values
        n = len(y)
        t = np.arange(n)
        
        # Estimate decay rate from recent slope
        recent_window = min(n, 50)
        y_recent = y[-recent_window:]
        t_recent = np.arange(recent_window)
        
        # Fit log-linear model: log(y) = -lambda*t + c
        with warnings.catch_warnings():
            warnings.simplefilter("ignore")
            y_positive = np.maximum(y_recent, 0.1)  # Avoid log(0)
            if np.all(y_positive > 0):
                log_y = np.log(y_positive)
                slope, _ = np.polyfit(t_recent, log_y, 1)
                lambda_decay = -slope
            else:
                lambda_decay = 0.01  # Default small decay
        
        # Clamp lambda to reasonable range
        lambda_decay = np.clip(lambda_decay, 0.001, 0.1)
        
        # Forecast
        last_val = y[-1]
        forecasts = []
        uncertainties = []
        
        # Estimate uncertainty in lambda
        residuals = y_recent - last_val * np.exp(-lambda_decay * t_recent)
        sigma_residual = np.std(residuals)
        sigma_lambda = sigma_residual / (np.mean(y_recent) + 1e-9)
        
        for h in horizons:
            forecast_h = last_val * np.exp(-lambda_decay * h)
            forecast_h = max(forecast_h, 0.0)  # Non-negative
            
            # Uncertainty grows with horizon
            sigma_h = sigma_lambda * last_val * h * np.exp(-lambda_decay * h)
            sigma_h = max(sigma_h, sigma_residual)
            
            forecasts.append(forecast_h)
            uncertainties.append(sigma_h)
        
        # Fit quality
        pred_train = y[0] * np.exp(-lambda_decay * t)
        ss_res = np.sum((y - pred_train)**2)
        ss_tot = np.sum((y - np.mean(y))**2)
        r_squared = 1 - (ss_res / (ss_tot + 1e-9))
        
        return {
            'forecasts': np.array(forecasts),
            'uncertainties': np.array(uncertainties),
            'horizons': horizons,
            'model': 'exponential',
            'params': {'lambda': lambda_decay, 'initial': last_val},
            'fit_quality': r_squared,
            'residual_std': sigma_residual
        }
    
    def _forecast_polynomial(
        self, 
        health_history: pd.Series, 
        horizons: List[int]
    ) -> Dict[str, Any]:
        """Polynomial regression (degree 2) for non-linear trends"""
        y = health_history.values
        n = len(y)
        t = np.arange(n)
        
        # Fit polynomial (degree 2)
        degree = 2
        coeffs = np.polyfit(t, y, degree)
        poly_model = np.poly1d(coeffs)
        
        # Predict on training data
        y_pred = poly_model(t)
        residuals = y - y_pred
        sigma = np.std(residuals)
        
        # Forecast
        forecasts = []
        uncertainties = []
        
        for h in horizons:
            t_future = n + h - 1
            forecast_h = poly_model(t_future)
            
            # Uncertainty grows with distance from training data
            sigma_h = sigma * np.sqrt(1 + (h**2 / n))
            
            forecasts.append(forecast_h)
            uncertainties.append(sigma_h)
        
        # Fit quality
        ss_res = np.sum(residuals**2)
        ss_tot = np.sum((y - np.mean(y))**2)
        r_squared = 1 - (ss_res / (ss_tot + 1e-9))
        
        return {
            'forecasts': np.array(forecasts),
            'uncertainties': np.array(uncertainties),
            'horizons': horizons,
            'model': 'polynomial',
            'params': {'coefficients': coeffs.tolist(), 'degree': degree},
            'fit_quality': r_squared,
            'residual_std': sigma
        }
    
    def _create_ensemble(
        self, 
        model_results: Dict[str, Dict], 
        health_history: pd.Series
    ) -> Dict[str, Any]:
        """Create ensemble forecast from multiple models"""
        # Weight models by fit quality
        weights = {}
        total_quality = 0.0
        
        for model_name, result in model_results.items():
            if model_name == 'ensemble':
                continue
            quality = max(result['fit_quality'], 0.0)
            weights[model_name] = quality
            total_quality += quality
        
        # Normalize weights
        if total_quality > 0:
            weights = {k: v/total_quality for k, v in weights.items()}
        else:
            # Equal weights if all poor
            weights = {k: 1.0/len(weights) for k in weights}
        
        # Get common horizons
        horizons = model_results[next(iter(model_results))]['horizons']
        n_horizons = len(horizons)
        
        # Ensemble forecasts
        ensemble_forecasts = np.zeros(n_horizons)
        ensemble_uncertainties = np.zeros(n_horizons)
        
        for model_name, weight in weights.items():
            result = model_results[model_name]
            ensemble_forecasts += weight * result['forecasts']
            # Variance components
            ensemble_uncertainties += weight * (result['uncertainties']**2)
        
        # Add between-model variance
        for i in range(n_horizons):
            model_forecasts = [model_results[m]['forecasts'][i] for m in weights]
            between_var = np.var(model_forecasts)
            ensemble_uncertainties[i] += between_var
        
        ensemble_uncertainties = np.sqrt(ensemble_uncertainties)
        
        return {
            'forecasts': ensemble_forecasts,
            'uncertainties': ensemble_uncertainties,
            'horizons': horizons,
            'model': 'ensemble',
            'params': {'weights': weights},
            'fit_quality': np.mean([model_results[m]['fit_quality'] for m in weights]),
            'residual_std': np.mean([model_results[m]['residual_std'] for m in weights])
        }
    
    def _select_best_model(
        self, 
        model_results: Dict[str, Dict], 
        health_history: pd.Series
    ) -> str:
        """Select best model based on fit quality and data characteristics"""
        if 'ensemble' in model_results and len(model_results) > 2:
            # Prefer ensemble if we have multiple models
            return 'ensemble'
        
        # Otherwise select by fit quality
        best_model = None
        best_quality = -np.inf
        
        for model_name, result in model_results.items():
            if result['fit_quality'] > best_quality:
                best_quality = result['fit_quality']
                best_model = model_name
        
        return best_model or 'ar1'  # Fallback to AR1
    
    def _empty_forecast(self) -> Dict[str, Any]:
        """Return empty forecast structure"""
        return {
            'forecasts': np.array([]),
            'uncertainties': np.array([]),
            'horizons': [],
            'model': 'none',
            'params': {},
            'fit_quality': 0.0,
            'residual_std': 0.0,
            'selected_model': 'none'
        }


class FailureProbabilityCalculator:
    """Calculate probabilistic failure predictions"""
    
    def __init__(self, config: ForecastConfig):
        self.config = config
    
    def compute_probabilities(
        self,
        forecast_result: Dict[str, Any],
        failure_threshold: float
    ) -> pd.DataFrame:
        """
        Compute failure probabilities at each horizon
        
        Returns DataFrame with columns:
        - ForecastHorizon_Hours
        - FailureProbability
        - RiskLevel
        - Confidence
        """
        forecasts = forecast_result['forecasts']
        uncertainties = forecast_result['uncertainties']
        horizons = forecast_result['horizons']
        
        if len(forecasts) == 0:
            return pd.DataFrame()
        
        probs = []
        for forecast_h, sigma_h in zip(forecasts, uncertainties):
            # P(Health <= threshold) using normal CDF
            z_score = (failure_threshold - forecast_h) / (sigma_h + 1e-9)
            prob = stats.norm.cdf(z_score)
            
            # Clamp to [0, 1]
            prob = np.clip(prob, 0.0, 1.0)
            probs.append(prob)
        
        probs = np.array(probs)
        
        # Confidence adjustment
        confidence = forecast_result.get('fit_quality', 0.5)
        confidence = np.clip(confidence, 0.0, 1.0)
        
        # Adjust probabilities by confidence
        confidence_factor = min(confidence / self.config.confidence_min, 1.0)
        adjusted_probs = probs * confidence_factor
        
        # Assign risk levels
        risk_levels = []
        for prob in adjusted_probs:
            if prob < 0.1:
                risk_levels.append('Low')
            elif prob < 0.3:
                risk_levels.append('Medium')
            elif prob < 0.5:
                risk_levels.append('High')
            elif prob < 0.7:
                risk_levels.append('Very High')
            else:
                risk_levels.append('Critical')
        
        df = pd.DataFrame({
            'ForecastHorizon_Hours': horizons,
            'ForecastHealth': forecasts,
            'ForecastUncertainty': uncertainties,
            'FailureProbability': adjusted_probs,
            'RiskLevel': risk_levels,
            'Confidence': confidence,
            'Model': forecast_result.get('selected_model', 'unknown')
        })
        
        return df


class DetectorCausationAnalyzer:
    """Analyze detector contributions to predicted failure"""
    
    def __init__(self, config: CausationConfig):
        self.config = config
    
    def analyze_causation(
        self,
        detector_scores: pd.DataFrame,
        predicted_failure_time: pd.Timestamp,
        window_hours: float = 6.0
    ) -> Tuple[pd.DataFrame, List[str]]:
        """
        Analyze detector contributions around predicted failure time
        
        Returns:
            (detector_contributions_df, failure_patterns)
        """
        # Define analysis window
        window_start = predicted_failure_time - pd.Timedelta(hours=window_hours)
        window_end = predicted_failure_time + pd.Timedelta(hours=window_hours)
        
        # Extract detector scores in window
        mask = (detector_scores.index >= window_start) & (detector_scores.index <= window_end)
        window_scores = detector_scores.loc[mask]
        
        if window_scores.empty:
            Console.warn("[CAUSATION] No detector scores in failure window")
            return pd.DataFrame(), []
        
        # Analyze each detector
        detector_names = [c.replace('_z', '') for c in window_scores.columns if c.endswith('_z')]
        contributions = []
        
        for det in detector_names:
            col = f'{det}_z'
            if col not in window_scores.columns:
                continue
            
            scores = window_scores[col].dropna()
            if scores.empty:
                continue
            
            # Compute metrics
            mean_z = float(scores.mean())
            max_z = float(scores.max())
            spike_count = int((scores > 3.0).sum())
            
            # Trend slope
            if len(scores) > 2:
                t = np.arange(len(scores))
                slope, _ = np.polyfit(t, scores.values, 1)
            else:
                slope = 0.0
            
            # Contribution weight (higher for higher z-scores and criticality)
            criticality = self.config.detector_criticality.get(det, 0.5)
            contribution_weight = (max_z * 0.5 + mean_z * 0.3 + spike_count * 0.2) * criticality
            
            contributions.append({
                'Detector': det,
                'MeanZ': mean_z,
                'MaxZ': max_z,
                'SpikeCount': spike_count,
                'TrendSlope': slope,
                'ContributionWeight': contribution_weight
            })
        
        if not contributions:
            return pd.DataFrame(), []
        
        contrib_df = pd.DataFrame(contributions)
        
        # Normalize to percentages
        total_weight = contrib_df['ContributionWeight'].sum()
        if total_weight > 0:
            contrib_df['ContributionPct'] = contrib_df['ContributionWeight'] / total_weight * 100
        else:
            contrib_df['ContributionPct'] = 0.0
        
        # Sort by contribution
        contrib_df = contrib_df.sort_values('ContributionPct', ascending=False)
        
        # Identify failure patterns
        patterns = self._identify_patterns(contrib_df, window_scores)
        
        return contrib_df, patterns
    
    def _identify_patterns(
        self,
        contrib_df: pd.DataFrame,
        window_scores: pd.DataFrame
    ) -> List[str]:
        """Identify failure patterns from detector signatures"""
        patterns = []
        
        # Check for sudden spike
        max_spike_rate = 0.0
        for det_row in contrib_df.itertuples():
            det = det_row.Detector
            col = f'{det}_z'
            if col in window_scores.columns:
                scores = window_scores[col].dropna()
                if len(scores) > 1:
                    diffs = scores.diff().abs()
                    max_diff = diffs.max()
                    if max_diff > 5.0:
                        max_spike_rate = max(max_spike_rate, max_diff)
        
        if max_spike_rate > 5.0:
            patterns.append('sudden_spike')
        
        # Check for drift (OMR or AR1 trending up)
        omr_row = contrib_df[contrib_df['Detector'] == 'omr']
        if not omr_row.empty and omr_row.iloc[0]['TrendSlope'] > 0.1:
            patterns.append('drift')
        
        # Check for correlation break (high PCA-SPE)
        pca_spe_row = contrib_df[contrib_df['Detector'] == 'pca_spe']
        if not pca_spe_row.empty and pca_spe_row.iloc[0]['ContributionPct'] > 40:
            patterns.append('correlation_break')
        
        # Check for gradual decay (all detectors rising)
        if len(contrib_df) >= 3:
            rising_count = (contrib_df['TrendSlope'] > 0).sum()
            if rising_count >= len(contrib_df) * 0.7:
                patterns.append('gradual_decay')
        
        return patterns if patterns else ['unknown']


class MaintenanceRecommender:
    """Generate intelligent maintenance recommendations"""
    
    def __init__(self, config: MaintenanceConfig):
        self.config = config
    
    def generate_recommendation(
        self,
        failure_probs_df: pd.DataFrame,
        causation_df: pd.DataFrame,
        failure_patterns: List[str],
        rul_hours: float
    ) -> Dict[str, Any]:
        """
        Generate comprehensive maintenance recommendation
        
        Returns dictionary with:
        - urgency_score
        - maintenance_required
        - window (earliest, preferred_start, preferred_end, latest)
        - recommended_actions
        - confidence
        """
        if failure_probs_df.empty:
            return self._default_recommendation()
        
        # Compute urgency score
        urgency_score = self._compute_urgency(
            failure_probs_df,
            causation_df,
            rul_hours
        )
        
        # Determine if maintenance required
        maintenance_required = urgency_score >= self.config.urgency_threshold
        
        # Calculate maintenance window
        window = self._calculate_window(failure_probs_df, rul_hours)
        
        # Generate recommended actions
        actions = self._generate_actions(failure_patterns, causation_df)
        
        # Overall confidence
        confidence = failure_probs_df['Confidence'].mean() if not failure_probs_df.empty else 0.0
        
        return {
            'urgency_score': float(urgency_score),
            'maintenance_required': bool(maintenance_required),
            'window': window,
            'recommended_actions': actions,
            'confidence': float(confidence),
            'failure_patterns': failure_patterns
        }
    
    def _compute_urgency(
        self,
        failure_probs_df: pd.DataFrame,
        causation_df: pd.DataFrame,
        rul_hours: float
    ) -> float:
        """Compute maintenance urgency score (0-100)"""
        # Base score from failure probability
        max_prob = failure_probs_df['FailureProbability'].max()
        prob_score = max_prob * 50  # 0-50 points
        
        # RUL component
        if rul_hours < 24:
            rul_score = 40
        elif rul_hours < 72:
            rul_score = 30
        elif rul_hours < 168:
            rul_score = 20
        else:
            rul_score = 10
        
        # Criticality from detectors
        if not causation_df.empty:
            critical_detectors = ['ar1', 'pca_spe', 'omr']
            critical_contribution = causation_df[
                causation_df['Detector'].isin(critical_detectors)
            ]['ContributionPct'].sum()
            criticality_score = min(critical_contribution / 10, 10)
        else:
            criticality_score = 0
        
        # Confidence adjustment
        confidence = failure_probs_df['Confidence'].mean()
        urgency = (prob_score + rul_score + criticality_score) * confidence
        
        return min(urgency, 100.0)
    
    def _calculate_window(
        self,
        failure_probs_df: pd.DataFrame,
        rul_hours: float
    ) -> Dict[str, Any]:
        """Calculate optimal maintenance window"""
        # Find when failure prob exceeds thresholds
        df = failure_probs_df.sort_values('ForecastHorizon_Hours')
        
        earliest_mask = df['FailureProbability'] >= self.config.risk_thresholds['low']
        latest_mask = df['FailureProbability'] >= self.config.risk_thresholds['high']
        
        if earliest_mask.any():
            earliest = float(df[earliest_mask].iloc[0]['ForecastHorizon_Hours'])
        else:
            earliest = rul_hours
        
        if latest_mask.any():
            latest = float(df[latest_mask].iloc[0]['ForecastHorizon_Hours'])
        else:
            latest = rul_hours
        
        # Preferred window with buffer
        confidence = df['Confidence'].mean()
        buffer = self.config.buffer_hours if confidence > 0.7 else self.config.buffer_hours * 2
        
        preferred_start = earliest
        preferred_end = max(latest - buffer, earliest)
        
        # Failure prob at window end
        prob_at_end = float(df[df['ForecastHorizon_Hours'] <= latest]['FailureProbability'].max())
        
        return {
            'earliest_maintenance': earliest,
            'preferred_window_start': preferred_start,
            'preferred_window_end': preferred_end,
            'latest_safe_time': latest,
            'failure_prob_at_latest': prob_at_end
        }
    
    def _generate_actions(
        self,
        failure_patterns: List[str],
        causation_df: pd.DataFrame
    ) -> List[Dict[str, Any]]:
        """Generate specific maintenance actions"""
        actions = []
        
        # Pattern-based actions
        if 'sudden_spike' in failure_patterns:
            actions.append({
                'action': 'Inspect sensors for failure or wiring issues',
                'priority': 'High',
                'estimated_duration_hours': 2
            })
        
        if 'drift' in failure_patterns:
            actions.append({
                'action': 'Recalibrate instruments and verify process parameters',
                'priority': 'Medium',
                'estimated_duration_hours': 4
            })
        
        if 'correlation_break' in failure_patterns:
            actions.append({
                'action': 'Check mechanical linkages and coupling integrity',
                'priority': 'High',
                'estimated_duration_hours': 6
            })
        
        if 'gradual_decay' in failure_patterns:
            actions.append({
                'action': 'Schedule preventive maintenance for progressive wear',
                'priority': 'Medium',
                'estimated_duration_hours': 8
            })
        
        # Detector-specific actions
        if not causation_df.empty:
            top_detector = causation_df.iloc[0]
            if top_detector['Detector'] == 'ar1' and top_detector['ContributionPct'] > 30:
                actions.append({
                    'action': 'Verify sensor readings and replace if needed',
                    'priority': 'High',
                    'estimated_duration_hours': 3
                })
        
        if not actions:
            actions.append({
                'action': 'General equipment inspection and diagnostics',
                'priority': 'Medium',
                'estimated_duration_hours': 4
            })
        
        return actions
    
    def _default_recommendation(self) -> Dict[str, Any]:
        """Default recommendation when insufficient data"""
        return {
            'urgency_score': 0.0,
            'maintenance_required': False,
            'window': {
                'earliest_maintenance': None,
                'preferred_window_start': None,
                'preferred_window_end': None,
                'latest_safe_time': None,
                'failure_prob_at_latest': 0.0
            },
            'recommended_actions': [],
            'confidence': 0.0,
            'failure_patterns': []
        }


class EnhancedForecastingEngine:
    """Main engine coordinating all enhanced forecasting components"""
    
    def __init__(self, config: Dict[str, Any]):
        self.forecast_config = self._parse_forecast_config(config)
        self.maintenance_config = self._parse_maintenance_config(config)
        self.causation_config = self._parse_causation_config(config)
        
        self.forecaster = HealthForecaster(self.forecast_config)
        self.prob_calculator = FailureProbabilityCalculator(self.forecast_config)
        self.causation_analyzer = DetectorCausationAnalyzer(self.causation_config)
        self.maintenance_recommender = MaintenanceRecommender(self.maintenance_config)
    
    def _parse_forecast_config(self, config: Dict[str, Any]) -> ForecastConfig:
        """Parse forecast configuration from config dict"""
        fc = config.get('forecasting', {})
        return ForecastConfig(
            enabled=fc.get('enabled', True),
            failure_threshold=fc.get('failure_threshold', 70.0),
            forecast_horizons=fc.get('forecast_horizons', [24, 72, 168]),
            models=fc.get('models', ['ar1', 'exponential', 'polynomial', 'ensemble']),
            confidence_min=fc.get('confidence_min', 0.6),
            max_forecast_hours=fc.get('max_forecast_hours', 168.0)
        )
    
    def _parse_maintenance_config(self, config: Dict[str, Any]) -> MaintenanceConfig:
        """Parse maintenance configuration"""
        mc = config.get('maintenance', {})
        return MaintenanceConfig(
            urgency_threshold=mc.get('urgency_threshold', 50.0),
            buffer_hours=mc.get('buffer_hours', 24)
        )
    
    def _parse_causation_config(self, config: Dict[str, Any]) -> CausationConfig:
        """Parse causation configuration"""
        cc = config.get('causation', {})
        return CausationConfig(
            min_detector_contribution=cc.get('min_detector_contribution', 10.0),
            top_sensors_count=cc.get('top_sensors_count', 10)
        )
    
    def run(self, ctx: Dict[str, Any]) -> Dict[str, Any]:
        """
        Main entry point for enhanced forecasting
        
        Expected ctx keys:
        - run_dir: Path to run directory
        - tables_dir: Path to tables directory
        - plots_dir: Path to plots directory
        - config: Configuration dictionary
        - run_id: Run identifier
        - equip_id: Equipment identifier
        
        Returns:
            Dictionary with tables and plots metadata
        """
        if not self.forecast_config.enabled:
            Console.info("[ENHANCED_FORECAST] Module disabled")
            return {'tables': [], 'plots': [], 'metrics': {}}
        
        Console.info("[ENHANCED_FORECAST] Starting enhanced forecasting analysis")
        
        run_dir = ctx.get('run_dir', Path('.'))
        tables_dir = ctx.get('tables_dir', run_dir / 'tables')
        run_id = ctx.get('run_id')
        equip_id = ctx.get('equip_id')
        
        # Load required data
        health_timeline = self._load_health_timeline(tables_dir)
        detector_scores = self._load_detector_scores(run_dir)
        
        if health_timeline is None or detector_scores is None:
            Console.warn("[ENHANCED_FORECAST] Required data not available")
            return {'tables': [], 'plots': [], 'metrics': {}}
        
        # Step 1: Forecast health trajectory
        forecast_result = self.forecaster.forecast(
            health_timeline,
            self.forecast_config.forecast_horizons
        )
        
        # Step 2: Compute failure probabilities
        failure_probs_df = self.prob_calculator.compute_probabilities(
            forecast_result,
            self.forecast_config.failure_threshold
        )
        
        # Step 3: Estimate RUL
        rul_hours = self._estimate_rul(forecast_result, self.forecast_config.failure_threshold)
        
        # Step 4: Determine predicted failure time
        predicted_failure_time = self._get_failure_time(
            health_timeline.index[-1],
            rul_hours
        )
        
        # Step 5: Analyze causation
        causation_df, failure_patterns = self.causation_analyzer.analyze_causation(
            detector_scores,
            predicted_failure_time
        )
        
        # Step 6: Generate maintenance recommendation
        maintenance_rec = self.maintenance_recommender.generate_recommendation(
            failure_probs_df,
            causation_df,
            failure_patterns,
            rul_hours
        )
        
        # Step 7: Write outputs
        tables = self._write_outputs(
            tables_dir,
            run_id,
            equip_id,
            health_timeline.index[-1],
            predicted_failure_time,
            failure_probs_df,
            causation_df,
            maintenance_rec,
            forecast_result
        )
        
        Console.info(f"[ENHANCED_FORECAST] Generated {len(tables)} enhanced tables")
        
        return {
            'tables': tables,
            'plots': [],
            'metrics': {
                'rul_hours': rul_hours,
                'max_failure_probability': float(failure_probs_df['FailureProbability'].max()) if not failure_probs_df.empty else 0.0,
                'maintenance_required': maintenance_rec['maintenance_required'],
                'urgency_score': maintenance_rec['urgency_score'],
                'confidence': maintenance_rec['confidence']
            }
        }
    
    def _load_health_timeline(self, tables_dir: Path) -> Optional[pd.Series]:
        """Load health timeline from tables"""
        health_file = tables_dir / 'health_timeline.csv'
        if not health_file.exists():
            Console.warn(f"[ENHANCED_FORECAST] health_timeline.csv not found")
            return None
        
        df = pd.read_csv(health_file)
        if 'Timestamp' in df.columns:
            ts_col = 'Timestamp'
        elif 'timestamp' in df.columns:
            ts_col = 'timestamp'
        else:
            ts_col = df.columns[0]
        
        df[ts_col] = pd.to_datetime(df[ts_col], errors='coerce')
        df = df.sort_values(ts_col).dropna(subset=[ts_col])
        df = df.set_index(ts_col)
        
        if 'HealthIndex' not in df.columns:
            Console.warn("[ENHANCED_FORECAST] HealthIndex column not found")
            return None
        
        return df['HealthIndex']
    
    def _load_detector_scores(self, run_dir: Path) -> Optional[pd.DataFrame]:
        """Load detector scores from run directory"""
        scores_file = run_dir / 'scores.csv'
        if not scores_file.exists():
            Console.warn(f"[ENHANCED_FORECAST] scores.csv not found")
            return None
        
        df = pd.read_csv(scores_file)
        if 'timestamp' in df.columns:
            df['timestamp'] = pd.to_datetime(df['timestamp'], errors='coerce')
            df = df.set_index('timestamp')
        
        return df
    
    def _estimate_rul(self, forecast_result: Dict[str, Any], threshold: float) -> float:
        """Estimate RUL from forecast"""
        forecasts = forecast_result['forecasts']
        horizons = forecast_result['horizons']
        
        # Find first crossing
        below_threshold = forecasts <= threshold
        if below_threshold.any():
            idx = np.argmax(below_threshold)
            return float(horizons[idx])
        else:
            # No crossing in forecast window
            return float(horizons[-1]) if len(horizons) > 0 else 168.0
    
    def _get_failure_time(self, current_time: pd.Timestamp, rul_hours: float) -> pd.Timestamp:
        """Calculate predicted failure time"""
        return current_time + pd.Timedelta(hours=rul_hours)
    
    def _write_outputs(
        self,
        tables_dir: Path,
        run_id: Optional[str],
        equip_id: Optional[int],
        current_time: pd.Timestamp,
        failure_time: pd.Timestamp,
        failure_probs_df: pd.DataFrame,
        causation_df: pd.DataFrame,
        maintenance_rec: Dict[str, Any],
        forecast_result: Dict[str, Any]
    ) -> List[Dict[str, str]]:
        """Write all output tables"""
        tables = []
        
        # Add IDs to dataframes
        def add_ids(df: pd.DataFrame) -> pd.DataFrame:
            if run_id:
                df.insert(0, 'RunID', run_id)
            if equip_id is not None:
                df.insert(1 if run_id else 0, 'EquipID', int(equip_id))
            return df
        
        # Table 1: Failure Probability Time Series
        if not failure_probs_df.empty:
            fp_df = failure_probs_df.copy()
            fp_df.insert(0, 'Timestamp', current_time)
            fp_df = add_ids(fp_df)
            fp_path = tables_dir / 'failure_probability_ts.csv'
            fp_df.to_csv(fp_path, index=False)
            tables.append({'name': 'failure_probability_ts', 'path': str(fp_path)})
        
        # Table 2: Failure Causation
        if not causation_df.empty:
            fc_df = causation_df.copy()
            fc_df.insert(0, 'PredictedFailureTime', failure_time)
            fc_df.insert(1, 'FailurePattern', ','.join(maintenance_rec['failure_patterns']))
            fc_df = add_ids(fc_df)
            fc_path = tables_dir / 'failure_causation.csv'
            fc_df.to_csv(fc_path, index=False)
            tables.append({'name': 'failure_causation', 'path': str(fc_path)})
        
        # Table 3: Enhanced Maintenance Recommendation
        maint_df = pd.DataFrame([{
            'UrgencyScore': maintenance_rec['urgency_score'],
            'MaintenanceRequired': maintenance_rec['maintenance_required'],
            'EarliestMaintenance': maintenance_rec['window']['earliest_maintenance'],
            'PreferredWindowStart': maintenance_rec['window']['preferred_window_start'],
            'PreferredWindowEnd': maintenance_rec['window']['preferred_window_end'],
            'LatestSafeTime': maintenance_rec['window']['latest_safe_time'],
            'FailureProbAtLatest': maintenance_rec['window']['failure_prob_at_latest'],
            'FailurePattern': ','.join(maintenance_rec['failure_patterns']),
            'Confidence': maintenance_rec['confidence'],
            'EstimatedDuration_Hours': sum(a['estimated_duration_hours'] for a in maintenance_rec['recommended_actions'])
        }])
        maint_df = add_ids(maint_df)
        maint_path = tables_dir / 'enhanced_maintenance_recommendation.csv'
        maint_df.to_csv(maint_path, index=False)
        tables.append({'name': 'enhanced_maintenance_recommendation', 'path': str(maint_path)})
        
        # Table 4: Recommended Actions
        if maintenance_rec['recommended_actions']:
            actions_df = pd.DataFrame(maintenance_rec['recommended_actions'])
            actions_df = add_ids(actions_df)
            actions_path = tables_dir / 'recommended_actions.csv'
            actions_df.to_csv(actions_path, index=False)
            tables.append({'name': 'recommended_actions', 'path': str(actions_path)})
        
        return tables


# Backwards compatibility with existing RUL estimator interface
def estimate_enhanced_rul(
    tables_dir: Path,
    equip_id: Optional[int],
    run_id: Optional[str],
    config: Dict[str, Any]
) -> Dict[str, pd.DataFrame]:
    """
    Enhanced RUL estimation compatible with existing interface
    
    This can be called from acm_main.py as a drop-in replacement
    for the existing rul_estimator.estimate_rul_and_failure()
    """
    engine = EnhancedForecastingEngine(config)
    
    ctx = {
        'run_dir': tables_dir.parent,
        'tables_dir': tables_dir,
        'plots_dir': tables_dir.parent / 'plots',
        'config': config,
        'run_id': run_id,
        'equip_id': equip_id
    }
    
    result = engine.run(ctx)
    
    # Convert to expected format (dict of dataframes)
    output = {}
    for table_info in result.get('tables', []):
        table_name = table_info['name']
        table_path = Path(table_info['path'])
        if table_path.exists():
            output[table_name] = pd.read_csv(table_path)
    
    return output
