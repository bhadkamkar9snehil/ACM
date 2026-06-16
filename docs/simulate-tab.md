# Simulate Tab Guide

The Simulate tab is ACM's built-in industrial data generator and replay engine. It has three sub-tabs: **Generate**, **Files**, and **Replay**.

---

## Generate

Produce synthetic time-series CSV files with realistic fault signatures.

1. Select a **Domain** (e.g. Rotary Equipment, Petroleum Pipeline, Power Plant)
2. Select a **Scenario** (e.g. bearing_fault, small_leak, condenser_fouling)
3. Adjust parameters (duration, fault severity, sample rate)
4. Click **Generate** — the CSV appears in the Files sub-tab

### Pre-generated fault datasets

10 fault CSVs are pre-loaded in `sim_data/sample/` (committed to git):

| File | Domain | Fault |
|---|---|---|
| `fault_rotary_bearing.csv` | Rotary Equipment | Bearing fault |
| `fault_rotary_imbalance.csv` | Rotary Equipment | Rotor imbalance |
| `fault_pipeline_small_leak.csv` | Petroleum Pipeline | Small leak |
| `fault_pipeline_large_leak.csv` | Petroleum Pipeline | Large leak |
| `fault_pipeline_pump_trip.csv` | Petroleum Pipeline | Pump trip |
| `fault_pipeline_sensor_drift.csv` | Petroleum Pipeline | Sensor drift |
| `fault_power_tube_leak.csv` | Power Plant | Tube leak |
| `fault_power_condenser_fouling.csv` | Power Plant | Condenser fouling |
| `fault_gas_compressor_trip.csv` | Gas Pipeline | Compressor trip |
| `fault_gas_leak.csv` | Gas Pipeline | Gas leak |

All files: first 40% of rows = `state=NORMAL` (ACM trains on this), remaining 60% = labeled fault state.

Regenerate: `python scripts/generate_fault_dataset.py`

---

## Files

Shows all CSV/XLSX files in `sim_data/` (generated, sample, and uploaded).

**Actions per file:**

| Button | What it does |
|---|---|
| Preview | Show column info and first few rows |
| → Replay | Load this file into the Replay sub-tab |
| → ACM | Register file as an ACM monitored asset and score it immediately |
| Delete | Remove the file from disk |

### → ACM flow

Clicking **→ ACM** on a file:
1. Registers the file as an ACM asset with key `sim/{filename_stem}` (e.g. `sim/fault_rotary_bearing`)
2. Triggers an immediate score run
3. Navigates to the Operator tab
4. On completion, opens the Engineer tab with the scored results

If the asset is already registered (e.g. you clicked → ACM before), it skips registration and scores again.

---

## Replay

Stream a CSV file as a live OPC UA feed — ACM ingests it as if it were a real-time sensor.

1. Select a file from the dropdown (or use **→ Replay** from Files tab)
2. Choose **Publisher Mode**:
   - `opcua` — publishes to OPC UA at `opc.tcp://localhost:4840/simulator` (default)
   - `mqtt` — publishes to MQTT broker
   - `both` — publishes to both
3. Click **Configure** then **▶ Replay**

When OPC UA mode is active, ACM automatically registers `simulator/opc_ua` as a monitored asset.

### Live tag values

While replay is running, the Replay sub-tab shows live tag values updating every second.

---

## Uploading your own data

Drag and drop or use the upload button to add your own CSV/XLSX files. They appear in the Files tab under the `uploaded` source.

Requirements:
- Must have a timestamp column (named `timestamp`, `time_stamp`, or `ts` — auto-detected)
- Timestamp column must be parseable as ISO 8601 or standard date format
- All other columns are treated as sensor readings
