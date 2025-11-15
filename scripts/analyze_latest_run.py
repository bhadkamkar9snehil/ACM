import sys
import pandas as pd
from pathlib import Path

# Add project root to path for imports
project_root = Path(__file__).resolve().parents[1]
if str(project_root) not in sys.path:
    sys.path.insert(0, str(project_root))

from utils.logger import Console

run_dir = Path(r"artifacts/FD_FAN_COLDSTART").glob("run_*")
run_dir = max(run_dir, key=lambda p: p.name)  # latest by name timestamp
ht_path = run_dir / "tables/health_timeline.csv"
raw_path = Path(r"data/FD FAN TEST DATA.csv")

raw = pd.read_csv(raw_path)
# detect timestamp column
try:
    ts_col = next((c for c in raw.columns if any(k in c.lower() for k in ['time','ts','date'])))
except StopIteration:
    ts_col = raw.columns[0]
raw[ts_col] = pd.to_datetime(raw[ts_col], errors='coerce')
raw = raw.dropna(subset=[ts_col]).set_index(ts_col).sort_index()

# numeric sensors
scols = raw.select_dtypes(include='number').columns.tolist()

ht = pd.read_csv(ht_path)
ht['timestamp'] = pd.to_datetime(ht['timestamp'])
ht = ht.set_index('timestamp').sort_index()

# Align
merged = raw.join(ht[['zone']], how='inner')

# Compute per-sensor medians by zone
rows = []
for c in scols:
    g = merged.groupby('zone')[c].median()
    m_good = g.get('GOOD')
    m_watch = g.get('WATCH')
    m_alert = g.get('ALERT')
    if pd.notna(m_good) and pd.notna(m_alert):
        delta = float(m_alert - m_good)
        rows.append({
            'sensor': c,
            'median_good': float(m_good),
            'median_alert': float(m_alert),
            'delta_alert_minus_good': delta
        })

out = pd.DataFrame(rows).sort_values('delta_alert_minus_good', key=lambda s: s.abs(), ascending=False)
Console.info("Top 5 sensors by median change (ALERT - GOOD):")
for _, r in out.head(5).iterrows():
    Console.info(f"- {r['sensor']}: good={r['median_good']:.2f}, alert={r['median_alert']:.2f}, delta={r['delta_alert_minus_good']:+.2f}", 
                 sensor=r['sensor'], median_good=r['median_good'], median_alert=r['median_alert'], delta=r['delta_alert_minus_good'])

