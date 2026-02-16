import pandas as pd
import numpy as np

def test_regime_alignment_logic(use_fix=True):
    print(f"\nTesting with fix={use_fix}...")
    
    # Simulate health_df with duplicate Timestamp columns
    dates = pd.date_range(start='2022-01-01', periods=10, freq='h')
    health_data = {'HealthIndex': np.random.rand(10)}
    # Create DataFrame with duplicate 'Timestamp' columns
    df1 = pd.DataFrame({'Timestamp': dates, 'HealthIndex': health_data['HealthIndex']})
    df2 = pd.DataFrame({'Timestamp': dates})
    health_df = pd.concat([df1, df2['Timestamp']], axis=1)
    
    print(f"health_df columns: {health_df.columns.tolist()}")
    
    # Simulate regime_df (from SQL)
    regime_rows = []
    for i, date in enumerate(dates):
        regime_rows.append((date, float(i % 3)))
    regime_df = pd.DataFrame(regime_rows, columns=['Timestamp', 'RegimeLabel'])
    regime_df['Timestamp'] = pd.to_datetime(regime_df['Timestamp'])
    
    dt_hours = 1.0
    forecast_config = {}
    
    try:
        # LOGIC FROM ForecastEngine._load_regime_series_for_health
        
        # Build clean DataFrames with reset indices for merge_asof
        
        if use_fix:
            # FIXED LOGIC
            ts_values = health_df['Timestamp']
            if isinstance(ts_values, pd.DataFrame):
                ts_values = ts_values.iloc[:, 0]
            
            health_times = pd.DataFrame({
                'Timestamp': pd.to_datetime(ts_values.values)
            })
        else:
            # BROKEN LOGIC
            health_times = pd.DataFrame({
                'Timestamp': pd.to_datetime(health_df['Timestamp'].values)
            })
            
        health_times = (health_times
            .drop_duplicates(subset=['Timestamp'], keep='last')
            .sort_values('Timestamp')
            .reset_index(drop=True))
        regime_df = regime_df.reset_index(drop=True)

        max_regime_gap = float(forecast_config.get('forecast.regime_conditioned.max_regime_gap_hours', 0.0))
        tolerance_hours = max(2.0 * float(dt_hours), 0.0)
        tolerance = pd.Timedelta(hours=tolerance_hours)

        aligned = pd.merge_asof(
            health_times,
            regime_df,
            on='Timestamp',
            direction='backward',
            tolerance=tolerance
        )

        regime_series = aligned['RegimeLabel']
        
        if use_fix:
            if isinstance(regime_series, pd.DataFrame):
                regime_series = regime_series.iloc[:, 0]
        
        print(f"Result type: {type(regime_series)}")
        print("Success!")
        
    except Exception as e:
        print(f"Caught expected exception: {e}")

if __name__ == "__main__":
    print("reproducing failure case:")
    test_regime_alignment_logic(use_fix=False)
    
    print("verifying fix case:")
    test_regime_alignment_logic(use_fix=True)
