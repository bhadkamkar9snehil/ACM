# core/river_models.py
"""
Online machine learning models using the River library.
"""
from __future__ import annotations

import numpy as np
import pandas as pd
from typing import Any, Dict, Optional

try:
    from river import anomaly, compose, feature_extraction, preprocessing
    HAS_RIVER = True
except ImportError:
    anomaly = compose = feature_extraction = preprocessing = None  # type: ignore
    HAS_RIVER = False

from utils.logger import Console


class StreamingAR:
    """Placeholder for future streaming AR baseline."""
    pass


class RiverTAD:
    """
    Streaming anomaly detector using River's Half-Space Trees.
    Processes data one sample at a time, updating the model online.
    """

    def __init__(self, cfg: Dict[str, Any] | None = None):
        if not HAS_RIVER:
            raise ImportError("River is not installed. Please run 'pip install river'.")

        self.cfg = cfg or {}
        self.window_size = int(self.cfg.get("window_size", 10))
        self.grace_period = int(self.cfg.get("grace_period", 100))
        self.pipeline: Optional["compose.Pipeline"] = None

    def _init_pipeline(self, features: list[str]) -> None:
        """Build the River pipeline based on the numeric feature names."""
        if not features:
            raise ValueError("RiverTAD requires at least one numeric feature column.")

        feature_union: Dict[str, "compose.Transformer"] = {}
        for col in features:
            feature_union[f"{col}_mean"] = compose.Select(col) | feature_extraction.RollingMean(self.window_size)
            feature_union[f"{col}_std"] = compose.Select(col) | feature_extraction.RollingSTD(self.window_size)
            feature_union[f"{col}_min"] = compose.Select(col) | feature_extraction.RollingMin(self.window_size)
            feature_union[f"{col}_max"] = compose.Select(col) | feature_extraction.RollingMax(self.window_size)

        feature_extractors = compose.TransformerUnion(feature_union)

        self.pipeline = compose.Pipeline(
            ("features", feature_extractors),
            ("scale", preprocessing.StandardScaler()),
            ("anomaly", anomaly.HalfSpaceTrees(
                n_trees=int(self.cfg.get("n_trees", 10)),
                height=int(self.cfg.get("height", 8)),
                window_size=self.window_size,
                seed=int(self.cfg.get("seed", 42))
            ))
        )
        Console.info(f"[RIVER] Initialized HalfSpaceTrees pipeline for {len(features)} features.")

    def score(self, X: pd.DataFrame) -> np.ndarray:
        """
        Process the data stream one sample at a time, learning and predicting.
        Returns an array of anomaly scores.
        """
        if X.empty:
            return np.array([], dtype=np.float32)

        if self.pipeline is None:
            numeric_cols = X.select_dtypes(include=[np.number]).columns.tolist()
            if not numeric_cols:
                Console.warn("[RIVER] No numeric columns available for streaming detector.")
                return np.zeros(len(X), dtype=np.float32)
            self._init_pipeline(numeric_cols)

        assert self.pipeline is not None  # for type checkers

        scores = []
        for _, row in X.iterrows():
            sample = row.to_dict()
            score = self.pipeline.score_one(sample)
            self.pipeline.learn_one(sample)
            scores.append(score)

        return np.array(scores, dtype=np.float32)
