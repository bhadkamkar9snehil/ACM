"""
Regime Identification Diagnostic Toolkit

This module provides comprehensive diagnostics for regime identification quality,
stability, and predictability. Use these tools to investigate regime detection
issues and validate improvements.

Usage:
    from core.regime_diagnostics import RegimeDiagnostics
    
    diagnostics = RegimeDiagnostics(regime_model, regime_labels, basis_df)
    report = diagnostics.generate_report()
    diagnostics.plot_stability_analysis(output_path)
"""

from __future__ import annotations
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Tuple
import numpy as np
import pandas as pd
from collections import Counter, defaultdict
from pathlib import Path

try:
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    MATPLOTLIB_AVAILABLE = True
except ImportError:
    plt = None  # type: ignore
    MATPLOTLIB_AVAILABLE = False

from core.observability import Console


@dataclass
class RegimeStabilityMetrics:
    """Metrics for assessing regime stability and quality."""
    
    # Regime count and distribution
    n_regimes: int = 0
    n_samples: int = 0
    n_transitions: int = 0
    
    # Stability metrics
    avg_dwell_time: float = 0.0
    median_dwell_time: float = 0.0
    min_dwell_time: float = 0.0
    max_dwell_time: float = 0.0
    dwell_time_std: float = 0.0
    
    # Label consistency
    label_entropy: float = 0.0  # Shannon entropy of regime distribution
    transition_rate: float = 0.0  # Transitions per sample
    
    # Rare regime detection
    rare_regime_count: int = 0  # Regimes with < 1% occupancy
    rare_regime_labels: List[int] = field(default_factory=list)
    
    # Fragmentation metrics
    avg_segment_length: float = 0.0
    fragmentation_score: float = 0.0  # High = many short segments
    
    # Confidence metrics
    avg_confidence: float = 0.0
    min_confidence: float = 0.0
    low_confidence_ratio: float = 0.0  # Fraction with confidence < 0.5
    
    # Novelty metrics (v11.3.1+)
    novel_point_ratio: float = 0.0
    novel_cluster_count: int = 0
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for JSON serialization."""
        return {
            'n_regimes': self.n_regimes,
            'n_samples': self.n_samples,
            'n_transitions': self.n_transitions,
            'avg_dwell_time': self.avg_dwell_time,
            'median_dwell_time': self.median_dwell_time,
            'min_dwell_time': self.min_dwell_time,
            'max_dwell_time': self.max_dwell_time,
            'dwell_time_std': self.dwell_time_std,
            'label_entropy': self.label_entropy,
            'transition_rate': self.transition_rate,
            'rare_regime_count': self.rare_regime_count,
            'rare_regime_labels': self.rare_regime_labels,
            'avg_segment_length': self.avg_segment_length,
            'fragmentation_score': self.fragmentation_score,
            'avg_confidence': self.avg_confidence,
            'min_confidence': self.min_confidence,
            'low_confidence_ratio': self.low_confidence_ratio,
            'novel_point_ratio': self.novel_point_ratio,
            'novel_cluster_count': self.novel_cluster_count,
        }


@dataclass
class RegimeCategorization:
    """Analysis of how new data is categorized into regimes."""
    
    # Assignment method
    assignment_method: str = "unknown"  # hdbscan, gmm, kmeans
    
    # Distance statistics
    avg_distance_to_center: float = 0.0
    max_distance_to_center: float = 0.0
    distance_threshold: Optional[float] = None
    
    # Confidence distribution
    confidence_by_regime: Dict[int, float] = field(default_factory=dict)
    
    # Novelty detection
    novel_points: int = 0
    novel_regimes: List[int] = field(default_factory=list)
    
    # Boundary analysis
    boundary_points: int = 0  # Points near regime boundaries
    uncertain_assignments: int = 0  # Assignments with low confidence
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for JSON serialization."""
        return {
            'assignment_method': self.assignment_method,
            'avg_distance_to_center': self.avg_distance_to_center,
            'max_distance_to_center': self.max_distance_to_center,
            'distance_threshold': self.distance_threshold,
            'confidence_by_regime': self.confidence_by_regime,
            'novel_points': self.novel_points,
            'novel_regimes': self.novel_regimes,
            'boundary_points': self.boundary_points,
            'uncertain_assignments': self.uncertain_assignments,
        }


class RegimeDiagnostics:
    """
    Comprehensive diagnostic tool for regime identification.
    
    Analyzes:
    1. Regime stability (dwell times, transitions, fragmentation)
    2. Data categorization (assignment confidence, distances)
    3. Label predictability (consistency across batches)
    4. Quality issues (rare regimes, low confidence, novelty)
    """
    
    def __init__(
        self,
        regime_model: Any,
        regime_labels: np.ndarray,
        basis_df: pd.DataFrame,
        regime_confidence: Optional[np.ndarray] = None,
        regime_is_novel: Optional[np.ndarray] = None,
    ):
        """
        Initialize diagnostics with regime data.
        
        Args:
            regime_model: Fitted RegimeModel object
            regime_labels: Array of regime labels (length = n_samples)
            basis_df: DataFrame with regime clustering features
            regime_confidence: Optional confidence scores (length = n_samples)
            regime_is_novel: Optional novelty flags (length = n_samples)
        """
        self.regime_model = regime_model
        self.regime_labels = np.asarray(regime_labels, dtype=int)
        self.basis_df = basis_df
        self.regime_confidence = np.asarray(regime_confidence) if regime_confidence is not None else None
        self.regime_is_novel = np.asarray(regime_is_novel) if regime_is_novel is not None else None
        
        # Validate inputs
        if len(self.regime_labels) != len(basis_df):
            raise ValueError(
                f"regime_labels length ({len(self.regime_labels)}) "
                f"!= basis_df length ({len(basis_df)})"
            )
        
        if self.regime_confidence is not None and len(self.regime_confidence) != len(self.regime_labels):
            raise ValueError(
                f"regime_confidence length ({len(self.regime_confidence)}) "
                f"!= regime_labels length ({len(self.regime_labels)})"
            )
        
        if self.regime_is_novel is not None and len(self.regime_is_novel) != len(self.regime_labels):
            raise ValueError(
                f"regime_is_novel length ({len(self.regime_is_novel)}) "
                f"!= regime_labels length ({len(self.regime_labels)})"
            )
    
    def compute_stability_metrics(self) -> RegimeStabilityMetrics:
        """
        Compute comprehensive regime stability metrics.
        
        Returns:
            RegimeStabilityMetrics with all computed metrics
        """
        metrics = RegimeStabilityMetrics()
        
        labels = self.regime_labels
        n_samples = len(labels)
        metrics.n_samples = n_samples
        
        if n_samples == 0:
            return metrics
        
        # Regime count and distribution
        unique_labels = np.unique(labels)
        metrics.n_regimes = len(unique_labels)
        
        # Count transitions
        if n_samples > 1:
            transitions = np.sum(np.diff(labels) != 0)
            metrics.n_transitions = int(transitions)
            metrics.transition_rate = float(transitions) / n_samples
        
        # Segment analysis (continuous runs of same label)
        segments = self._compute_segments(labels)
        if len(segments) > 0:
            segment_lengths = [seg['length'] for seg in segments]
            metrics.avg_segment_length = float(np.mean(segment_lengths))
            metrics.median_dwell_time = float(np.median(segment_lengths))
            metrics.min_dwell_time = float(np.min(segment_lengths))
            metrics.max_dwell_time = float(np.max(segment_lengths))
            metrics.dwell_time_std = float(np.std(segment_lengths))
            metrics.avg_dwell_time = metrics.avg_segment_length
            
            # Fragmentation score: ratio of segments to regimes
            # High score = many short segments (fragmented)
            metrics.fragmentation_score = float(len(segments)) / max(1, metrics.n_regimes)
        
        # Label entropy (distribution uniformity)
        label_counts = Counter(labels)
        probs = np.array([label_counts[l] / n_samples for l in unique_labels])
        metrics.label_entropy = float(-np.sum(probs * np.log2(probs + 1e-10)))
        
        # Rare regime detection (< 1% occupancy)
        rare_threshold = max(10, n_samples * 0.01)  # At least 10 samples or 1%
        rare_regimes = [
            int(label) for label, count in label_counts.items()
            if count < rare_threshold
        ]
        metrics.rare_regime_count = len(rare_regimes)
        metrics.rare_regime_labels = sorted(rare_regimes)
        
        # Confidence metrics
        if self.regime_confidence is not None:
            valid_conf = self.regime_confidence[np.isfinite(self.regime_confidence)]
            if len(valid_conf) > 0:
                metrics.avg_confidence = float(np.mean(valid_conf))
                metrics.min_confidence = float(np.min(valid_conf))
                metrics.low_confidence_ratio = float(np.mean(valid_conf < 0.5))
        
        # Novelty metrics
        if self.regime_is_novel is not None:
            metrics.novel_point_ratio = float(np.mean(self.regime_is_novel))
            # Count how many regimes have novel points
            novel_regimes = set(labels[self.regime_is_novel])
            metrics.novel_cluster_count = len(novel_regimes)
        
        return metrics
    
    def compute_categorization_analysis(self) -> RegimeCategorization:
        """
        Analyze how new data is categorized into regimes.
        
        Returns:
            RegimeCategorization with assignment analysis
        """
        cat = RegimeCategorization()
        
        # Determine assignment method from model
        if hasattr(self.regime_model, 'is_hdbscan') and self.regime_model.is_hdbscan:
            cat.assignment_method = "hdbscan"
        elif hasattr(self.regime_model, 'is_gmm') and self.regime_model.is_gmm:
            cat.assignment_method = "gmm"
        else:
            cat.assignment_method = "unknown"
        
        # Compute distances to assigned cluster centers
        try:
            # Align and scale basis data
            aligned = self.basis_df.reindex(
                columns=self.regime_model.feature_columns, fill_value=0.0
            )
            aligned_arr = aligned.to_numpy(dtype=np.float64, copy=False, na_value=0.0)
            X_scaled = self.regime_model.scaler.transform(aligned_arr)
            
            centers = self.regime_model.cluster_centers_
            if centers.size > 0:
                # Compute distance to assigned center for each point
                distances = np.array([
                    np.linalg.norm(X_scaled[i] - centers[self.regime_labels[i]])
                    if self.regime_labels[i] >= 0 and self.regime_labels[i] < len(centers)
                    else np.nan
                    for i in range(len(X_scaled))
                ])
                
                valid_distances = distances[np.isfinite(distances)]
                if len(valid_distances) > 0:
                    cat.avg_distance_to_center = float(np.mean(valid_distances))
                    cat.max_distance_to_center = float(np.max(valid_distances))
        except Exception as e:
            Console.warn(
                f"Failed to compute regime distances: {e}",
                component="REGIME_DIAG", error_type=type(e).__name__
            )
        
        # Distance threshold from model
        if hasattr(self.regime_model, 'training_distance_threshold_'):
            cat.distance_threshold = self.regime_model.training_distance_threshold_
        
        # Confidence by regime
        if self.regime_confidence is not None:
            for label in np.unique(self.regime_labels):
                mask = self.regime_labels == label
                regime_conf = self.regime_confidence[mask]
                valid_conf = regime_conf[np.isfinite(regime_conf)]
                if len(valid_conf) > 0:
                    cat.confidence_by_regime[int(label)] = float(np.mean(valid_conf))
            
            # Count uncertain assignments
            cat.uncertain_assignments = int(np.sum(self.regime_confidence < 0.5))
        
        # Novelty detection
        if self.regime_is_novel is not None:
            cat.novel_points = int(np.sum(self.regime_is_novel))
            cat.novel_regimes = sorted(set(self.regime_labels[self.regime_is_novel].tolist()))
        
        # Boundary points (heuristic: points with low confidence)
        if self.regime_confidence is not None:
            cat.boundary_points = int(np.sum(self.regime_confidence < 0.3))
        
        return cat
    
    def _compute_segments(self, labels: np.ndarray) -> List[Dict[str, Any]]:
        """
        Compute continuous segments of same regime label.
        
        Returns:
            List of dicts with keys: label, start_idx, end_idx, length
        """
        if len(labels) == 0:
            return []
        
        segments = []
        current_label = labels[0]
        start_idx = 0
        
        for i in range(1, len(labels)):
            if labels[i] != current_label:
                # End of segment
                segments.append({
                    'label': int(current_label),
                    'start_idx': start_idx,
                    'end_idx': i - 1,
                    'length': i - start_idx,
                })
                current_label = labels[i]
                start_idx = i
        
        # Add final segment
        segments.append({
            'label': int(current_label),
            'start_idx': start_idx,
            'end_idx': len(labels) - 1,
            'length': len(labels) - start_idx,
        })
        
        return segments
    
    def generate_report(self) -> Dict[str, Any]:
        """
        Generate comprehensive diagnostic report.
        
        Returns:
            Dictionary with all diagnostic results
        """
        Console.info("Generating regime diagnostics report...", component="REGIME_DIAG")
        
        # Compute metrics
        stability = self.compute_stability_metrics()
        categorization = self.compute_categorization_analysis()
        
        # Assess overall quality
        quality_issues = []
        
        # Check for fragmentation
        if stability.fragmentation_score > 5.0:
            quality_issues.append(
                f"High fragmentation (score={stability.fragmentation_score:.1f}). "
                "Many short regime segments detected. Consider increasing min_cluster_size."
            )
        
        # Check for rare regimes
        if stability.rare_regime_count > 0:
            quality_issues.append(
                f"Detected {stability.rare_regime_count} rare regimes "
                f"(labels: {stability.rare_regime_labels}). "
                "These may be transient states or noise."
            )
        
        # Check for low confidence
        if stability.low_confidence_ratio > 0.3:
            quality_issues.append(
                f"High uncertainty: {stability.low_confidence_ratio:.1%} of assignments "
                "have confidence < 0.5. Regime model may need retraining."
            )
        
        # Check for high transition rate
        if stability.transition_rate > 0.1:
            quality_issues.append(
                f"High transition rate ({stability.transition_rate:.1%}). "
                "Regimes may be too granular or unstable."
            )
        
        # Check for novelty
        if stability.novel_point_ratio > 0.1:
            quality_issues.append(
                f"High novelty: {stability.novel_point_ratio:.1%} of points flagged as novel. "
                "Operating conditions may be drifting outside training coverage."
            )
        
        report = {
            'stability_metrics': stability.to_dict(),
            'categorization': categorization.to_dict(),
            'quality_issues': quality_issues,
            'quality_score': self._compute_quality_score(stability, categorization),
            'model_meta': {
                'n_clusters': self.regime_model.n_clusters if hasattr(self.regime_model, 'n_clusters') else 0,
                'feature_count': len(self.regime_model.feature_columns) if hasattr(self.regime_model, 'feature_columns') else 0,
                'model_type': categorization.assignment_method,
            }
        }
        
        Console.info(
            f"Diagnostics complete: {stability.n_regimes} regimes, "
            f"quality_score={report['quality_score']:.2f}, "
            f"{len(quality_issues)} issues found",
            component="REGIME_DIAG"
        )
        
        return report
    
    def _compute_quality_score(
        self,
        stability: RegimeStabilityMetrics,
        categorization: RegimeCategorization
    ) -> float:
        """
        Compute overall regime quality score (0-100).
        
        Higher is better. Combines stability, confidence, and fragmentation.
        """
        score = 100.0
        
        # Penalize fragmentation
        if stability.fragmentation_score > 2.0:
            score -= min(20, (stability.fragmentation_score - 2.0) * 5)
        
        # Penalize low confidence
        if stability.avg_confidence < 0.7:
            score -= (0.7 - stability.avg_confidence) * 50
        
        # Penalize high transition rate
        if stability.transition_rate > 0.05:
            score -= (stability.transition_rate - 0.05) * 200
        
        # Penalize rare regimes
        if stability.rare_regime_count > 0:
            score -= stability.rare_regime_count * 5
        
        # Penalize novelty ratio
        if stability.novel_point_ratio > 0.05:
            score -= (stability.novel_point_ratio - 0.05) * 100
        
        return max(0.0, min(100.0, score))
    
    def plot_stability_analysis(self, output_path: Optional[Path] = None) -> Optional[Path]:
        """
        Generate stability analysis plots.
        
        Creates:
        1. Regime timeline (labels over time)
        2. Confidence distribution
        3. Dwell time histogram
        4. Transition matrix heatmap
        
        Args:
            output_path: Path to save plot (optional)
            
        Returns:
            Path to saved plot, or None if matplotlib unavailable
        """
        if not MATPLOTLIB_AVAILABLE:
            Console.warn(
                "Matplotlib not available, skipping stability plots",
                component="REGIME_DIAG"
            )
            return None
        
        fig, axes = plt.subplots(2, 2, figsize=(14, 10))
        
        # 1. Regime timeline
        ax = axes[0, 0]
        ax.plot(self.regime_labels, linewidth=0.5)
        ax.set_title("Regime Timeline")
        ax.set_xlabel("Sample Index")
        ax.set_ylabel("Regime Label")
        ax.grid(True, alpha=0.3)
        
        # 2. Confidence distribution
        ax = axes[0, 1]
        if self.regime_confidence is not None:
            valid_conf = self.regime_confidence[np.isfinite(self.regime_confidence)]
            ax.hist(valid_conf, bins=30, edgecolor='black', alpha=0.7)
            ax.axvline(0.5, color='red', linestyle='--', label='Low Confidence Threshold')
            ax.set_title("Confidence Distribution")
            ax.set_xlabel("Confidence Score")
            ax.set_ylabel("Frequency")
            ax.legend()
        else:
            ax.text(0.5, 0.5, "No confidence data", ha='center', va='center')
            ax.set_title("Confidence Distribution (No Data)")
        
        # 3. Dwell time histogram
        ax = axes[1, 0]
        segments = self._compute_segments(self.regime_labels)
        if len(segments) > 0:
            dwell_times = [seg['length'] for seg in segments]
            ax.hist(dwell_times, bins=30, edgecolor='black', alpha=0.7)
            ax.set_title("Dwell Time Distribution")
            ax.set_xlabel("Segment Length (samples)")
            ax.set_ylabel("Frequency")
            ax.set_yscale('log')
        else:
            ax.text(0.5, 0.5, "No segments", ha='center', va='center')
            ax.set_title("Dwell Time Distribution (No Data)")
        
        # 4. Transition matrix
        ax = axes[1, 1]
        transition_matrix = self._compute_transition_matrix()
        if transition_matrix.size > 0:
            im = ax.imshow(transition_matrix, cmap='Blues', interpolation='nearest')
            ax.set_title("Regime Transition Matrix")
            ax.set_xlabel("To Regime")
            ax.set_ylabel("From Regime")
            plt.colorbar(im, ax=ax, label="Transition Count")
        else:
            ax.text(0.5, 0.5, "No transitions", ha='center', va='center')
            ax.set_title("Regime Transition Matrix (No Data)")
        
        plt.tight_layout()
        
        if output_path is not None:
            output_path = Path(output_path)
            output_path.parent.mkdir(parents=True, exist_ok=True)
            fig.savefig(output_path, dpi=150, bbox_inches='tight')
            Console.info(f"Saved stability plots to {output_path}", component="REGIME_DIAG")
            plt.close(fig)
            return output_path
        else:
            plt.show()
            return None
    
    def _compute_transition_matrix(self) -> np.ndarray:
        """
        Compute regime transition count matrix.
        
        Returns:
            Matrix of shape (n_regimes, n_regimes) with transition counts
        """
        labels = self.regime_labels
        unique_labels = sorted(set(labels))
        n_regimes = len(unique_labels)
        
        if n_regimes == 0 or len(labels) < 2:
            return np.zeros((0, 0))
        
        # Create label to index mapping
        label_to_idx = {label: idx for idx, label in enumerate(unique_labels)}
        
        # Count transitions
        matrix = np.zeros((n_regimes, n_regimes), dtype=int)
        for i in range(len(labels) - 1):
            from_label = labels[i]
            to_label = labels[i + 1]
            from_idx = label_to_idx[from_label]
            to_idx = label_to_idx[to_label]
            matrix[from_idx, to_idx] += 1
        
        return matrix
