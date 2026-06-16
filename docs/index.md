# ACM — Asset Condition Monitor

ACM is a self-tuning anomaly detection service for industrial assets. It ingests time-series data from historians, OPC UA servers, MQTT brokers, or CSV files; fits a multi-model ML pipeline on each asset; and surfaces anomaly scores in a real-time operator dashboard.

---

## Guides

| Guide | What it covers |
|---|---|
| [Installation](installation.md) | One-command install on Windows and Linux/macOS |
| [Architecture](architecture.md) | How data flows from source → cache → pipeline → UI |
| [Simulate Tab](simulate-tab.md) | Generate synthetic data, replay it, and onboard it into ACM |
| [Troubleshooting](troubleshooting.md) | Common errors and how to fix them |

---

## Quick start

```bash
# Linux / macOS
bash <(curl -fsSL https://raw.githubusercontent.com/bhadkamkar9snehil/ACM/main/setup.sh)

# Windows (PowerShell)
irm https://raw.githubusercontent.com/bhadkamkar9snehil/ACM/main/setup_acm.ps1 | iex
```

Once installed:

```bash
cd ~/ACM
python scripts/acm_service.py
# Open http://localhost:8765
```

Click **Score All** in the header to begin scoring your registered assets.
