import sys
import numpy as np
import pandas as pd
import pytest

from core import fast_features as ff


def make_series(n=50, freq=1.0):
    t = pd.date_range("2020-01-01", periods=n, freq="s")
    s = pd.Series(np.sin(np.linspace(0, 6.28, n)) + 0.1 * np.random.randn(n), index=t)
    return s


def test_rolling_median_and_mad_pandas():
    s = make_series(100)
    df = pd.DataFrame({'x': s})
    med = ff.rolling_median(df, window=5, cols=['x'], min_periods=1)
    mad = ff.rolling_mad(df, window=5, cols=['x'], min_periods=1)
    assert 'x_med' in med.columns
    assert 'x_mad' in mad.columns
    assert len(med) == len(df)
    assert len(mad) == len(df)


def test_rolling_spectral_energy_pandas():
    s = make_series(128)
    df = pd.DataFrame({'x': s})
    se = ff.rolling_spectral_energy(df, window=32, cols=['x'], bands=[(0.0, 0.1), (0.1, 0.3)], fs=1.0, min_periods=1)
    # Expect two columns for two bands
    assert 'x_energy_0' in se.columns
    assert 'x_energy_1' in se.columns
    assert len(se) == len(df)


@pytest.mark.skipif(not ff.HAS_POLARS, reason="Polars not installed")
def test_polars_paths():
    import polars as pl
    s = make_series(80)
    pdf = pd.DataFrame({'x': s})
    # Convert to polars
    pl_df = pl.from_pandas(pdf)
    med = ff.rolling_median(pl_df, window=5, cols=['x'])
    assert isinstance(med, pd.DataFrame)
    se = ff.rolling_spectral_energy(pl_df, window=32, cols=['x'], bands=[(0.0, 0.1), (0.1, 0.3)], fs=1.0, min_periods=1)
    assert isinstance(se, pd.DataFrame)


if __name__ == '__main__':
    pytest.main([__file__])
