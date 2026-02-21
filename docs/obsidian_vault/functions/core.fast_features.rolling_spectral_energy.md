---
type: function
id: core.fast_features.rolling_spectral_energy
module: core.fast_features
source: core/fast_features.py
line_start: 241
line_end: 297
---

# core.fast_features.rolling_spectral_energy

Defined in: [[modules/core.fast_features]]

Source: `core/fast_features.py:241`

Kind: `function`

Signature: `rolling_spectral_energy(df: pl.DataFrame, window: int, cols: Optional[List[str]]=None, bands: Optional[List[Tuple[float, float]]]=None, fs: float=1.0, min_periods: int=1)`

Summary: Rolling spectral energy in frequency bands. Requires Polars DataFrame input.
