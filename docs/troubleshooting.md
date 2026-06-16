# Troubleshooting

## Asset stuck in MATURING state

**Symptom:** Asset shows `MATURING` in the Operator matrix and never scores.

**Cause:** The asset's data span is less than 14 days (default minimum training window).

**Fix options:**
1. **Wait** — as more data accumulates, it will transition to READY automatically.
2. **fast_track** — when registering via the Files tab → ACM button, `fast_track=true` is set automatically, bypassing the 14-day gate. The asset scores on the first tick.
3. **Backdate** — use the Simulate tab to generate data with `backdate=true` (45-day offset), giving ACM immediate history.

---

## Asset shows ERROR state — "degenerate split"

**Symptom:** Diagnosis column shows `degenerate split (train=0, score=N)` or similar.

**Cause:** The data span is extremely short (e.g. a 2-hour CSV file), and the adaptive scoring window calculation placed the split before the dataset begins.

**Fix:** This was resolved in commit `fab2e25` (2026-06-16). The score window is now proportional to the dataset span (1/3 of total history, minimum 5% of total history). Update ACM: click **Update ACM** in the header or run `git pull && restart service`.

---

## Asset shows ERROR state — other errors

**Symptom:** Asset in ERROR state; Diagnosis column shows error text.

**How to see the full error:**
- In the Operator matrix: hover or expand the Diagnosis column
- In the service terminal: look for `[error] {asset_key}: {message}` lines after each tick

**Common causes:**
- Not enough numeric sensor columns (< 2 after dropping non-numeric)
- All-NaN sensor columns
- Timestamp column not found or not parseable
- CSV file moved/deleted after registration

---

## OPC UA data not arriving

**Symptom:** `simulator/opc_ua` asset is STALE or never ingests data.

**Check:**
1. Is the Simulator running? (`~/Simulator` → `RUN_SIMULATOR.bat` or `python suite_runtime.py`)
2. Check `data_cache/opcua_buffer.db` — does it have recent rows?
   ```bash
   python -c "import sqlite3; db=sqlite3.connect('data_cache/opcua_buffer.db'); print(db.execute('SELECT ts FROM opcua_buffer ORDER BY ts DESC LIMIT 3').fetchall())"
   ```
3. Check the service terminal for OPC UA bridge error messages

---

## Double-prefix asset keys (sim/sim/...)

**Symptom:** Admin tab shows assets with `sim/sim/fault_rotary_bearing` (two `sim/` prefixes).

**Cause:** Stale entries from an older onboarding flow. See [GitHub Issue #50](https://github.com/bhadkamkar9snehil/ACM/issues/50).

**Fix:** Delete the stale entries from the Admin tab (once the delete action UI is added — see [Issue #53](https://github.com/bhadkamkar9snehil/ACM/issues/53)). Until then, use SQLite directly:
```bash
python -c "import sqlite3; db=sqlite3.connect('acm_results.db'); db.execute(\"DELETE FROM monitored_assets WHERE asset_key LIKE 'sim/sim/%'\"); db.commit(); print('Done')"
```

---

## Service starts PAUSED / Score All does nothing

**Symptom:** Operator tab shows all assets as NEW/MATURING; no scoring happens automatically.

**This is by design.** ACM starts in a paused state on every restart so it doesn't auto-score on service startup. To begin scoring:
- Click **Score All** in the header (scores all eligible assets immediately)
- Or click **▶ Score** on individual asset rows in the Operator matrix
- Or un-pause via Admin → Service Controls

---

## Engineer tab shows blank chart

**Symptom:** Clicking an asset in the Operator matrix opens Engineer tab but the chart area is empty or shows "No score data yet".

**Cause:** The asset has never been scored (state is NEW, MATURING, or ERROR).

**Fix:**
- If ERROR: check Diagnosis column for the error message, fix the root cause, re-score
- If MATURING: wait for more data, or use fast_track (see above)
- If state shows OK/ALARM but chart is blank: click the ▶ Score button for that asset to force a fresh run

---

## Tests failing

```bash
python -m pytest tests/ -v --tb=short
```

CI results are visible at: https://github.com/bhadkamkar9snehil/ACM/actions

Test failures do not break ACM's runtime — they indicate a regression in ML correctness or API behavior. Check the Actions tab for which tests are failing and their error output.
