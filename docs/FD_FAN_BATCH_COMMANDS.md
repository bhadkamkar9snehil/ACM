# FD_FAN Batch Processing Commands

This document contains static commands for running ACM batches on the FD_FAN equipment. Each command processes a non-overlapping time window.

**Equipment**: FD_FAN (Forced Draft Fan)  
**Data Range**: 2023-10-15 to 2025-09-14 (time-shifted sample data)  
**Total Duration**: ~23 months

## Instructions

1. Copy each command below one at a time
2. Run in PowerShell from the ACM project root directory
3. Wait for each command to complete before running the next
4. Commands are ordered chronologically with no overlap

---

## Batch Commands

### Batch 1: 2023-10-15 to 2023-11-15 (1 month)
```powershell
python -m core.acm_main --equip FD_FAN --start-time "2023-10-15T00:00:00" --end-time "2023-11-15T00:00:00"
```

### Batch 2: 2023-11-15 to 2023-12-15 (1 month)
```powershell
python -m core.acm_main --equip FD_FAN --start-time "2023-11-15T00:00:00" --end-time "2023-12-15T00:00:00"
```

### Batch 3: 2023-12-15 to 2024-01-15 (1 month)
```powershell
python -m core.acm_main --equip FD_FAN --start-time "2023-12-15T00:00:00" --end-time "2024-01-15T00:00:00"
```

### Batch 4: 2024-01-15 to 2024-02-15 (1 month)
```powershell
python -m core.acm_main --equip FD_FAN --start-time "2024-01-15T00:00:00" --end-time "2024-02-15T00:00:00"
```

### Batch 5: 2024-02-15 to 2024-03-15 (1 month)
```powershell
python -m core.acm_main --equip FD_FAN --start-time "2024-02-15T00:00:00" --end-time "2024-03-15T00:00:00"
```

### Batch 6: 2024-03-15 to 2024-04-15 (1 month)
```powershell
python -m core.acm_main --equip FD_FAN --start-time "2024-03-15T00:00:00" --end-time "2024-04-15T00:00:00"
```

### Batch 7: 2024-04-15 to 2024-05-15 (1 month)
```powershell
python -m core.acm_main --equip FD_FAN --start-time "2024-04-15T00:00:00" --end-time "2024-05-15T00:00:00"
```

### Batch 8: 2024-05-15 to 2024-06-15 (1 month)
```powershell
python -m core.acm_main --equip FD_FAN --start-time "2024-05-15T00:00:00" --end-time "2024-06-15T00:00:00"
```

### Batch 9: 2024-06-15 to 2024-07-15 (1 month)
```powershell
python -m core.acm_main --equip FD_FAN --start-time "2024-06-15T00:00:00" --end-time "2024-07-15T00:00:00"
```

### Batch 10: 2024-07-15 to 2024-08-15 (1 month)
```powershell
python -m core.acm_main --equip FD_FAN --start-time "2024-07-15T00:00:00" --end-time "2024-08-15T00:00:00"
```

### Batch 11: 2024-08-15 to 2024-09-15 (1 month)
```powershell
python -m core.acm_main --equip FD_FAN --start-time "2024-08-15T00:00:00" --end-time "2024-09-15T00:00:00"
```

### Batch 12: 2024-09-15 to 2024-10-15 (1 month)
```powershell
python -m core.acm_main --equip FD_FAN --start-time "2024-09-15T00:00:00" --end-time "2024-10-15T00:00:00"
```

### Batch 13: 2024-10-15 to 2024-11-15 (1 month)
```powershell
python -m core.acm_main --equip FD_FAN --start-time "2024-10-15T00:00:00" --end-time "2024-11-15T00:00:00"
```

### Batch 14: 2024-11-15 to 2024-12-15 (1 month)
```powershell
python -m core.acm_main --equip FD_FAN --start-time "2024-11-15T00:00:00" --end-time "2024-12-15T00:00:00"
```

### Batch 15: 2024-12-15 to 2025-01-15 (1 month)
```powershell
python -m core.acm_main --equip FD_FAN --start-time "2024-12-15T00:00:00" --end-time "2025-01-15T00:00:00"
```

### Batch 16: 2025-01-15 to 2025-02-15 (1 month)
```powershell
python -m core.acm_main --equip FD_FAN --start-time "2025-01-15T00:00:00" --end-time "2025-02-15T00:00:00"
```

### Batch 17: 2025-02-15 to 2025-03-15 (1 month)
```powershell
python -m core.acm_main --equip FD_FAN --start-time "2025-02-15T00:00:00" --end-time "2025-03-15T00:00:00"
```

### Batch 18: 2025-03-15 to 2025-04-15 (1 month)
```powershell
python -m core.acm_main --equip FD_FAN --start-time "2025-03-15T00:00:00" --end-time "2025-04-15T00:00:00"
```

### Batch 19: 2025-04-15 to 2025-05-15 (1 month)
```powershell
python -m core.acm_main --equip FD_FAN --start-time "2025-04-15T00:00:00" --end-time "2025-05-15T00:00:00"
```

### Batch 20: 2025-05-15 to 2025-06-15 (1 month)
```powershell
python -m core.acm_main --equip FD_FAN --start-time "2025-05-15T00:00:00" --end-time "2025-06-15T00:00:00"
```

### Batch 21: 2025-06-15 to 2025-07-15 (1 month)
```powershell
python -m core.acm_main --equip FD_FAN --start-time "2025-06-15T00:00:00" --end-time "2025-07-15T00:00:00"
```

### Batch 22: 2025-07-15 to 2025-08-15 (1 month)
```powershell
python -m core.acm_main --equip FD_FAN --start-time "2025-07-15T00:00:00" --end-time "2025-08-15T00:00:00"
```

### Batch 23: 2025-08-15 to 2025-09-14 (Final batch - 30 days)
```powershell
python -m core.acm_main --equip FD_FAN --start-time "2025-08-15T00:00:00" --end-time "2025-09-14T23:59:59"
```

---

## Notes

- **Total Batches**: 23 commands covering the complete FD_FAN dataset
- **Batch Size**: Each batch processes approximately 1 month of data
- **Non-Overlapping**: Each batch starts exactly where the previous batch ended
- **Format**: ISO 8601 datetime format (YYYY-MM-DDTHH:MM:SS)
- **Prerequisites**: 
  - SQL Server connection configured in `configs/sql_connection.ini`
  - ACM environment set up (Python 3.11+, dependencies installed)
  - Observability stack optional but recommended

## Alternative: Automated Batch Processing

If you prefer automated sequential processing instead of manual commands, use the batch runner:

```powershell
python scripts/sql_batch_runner.py --equip FD_FAN --tick-minutes 44640 --max-batches 23 --start-from-beginning
```

This will automatically process all 23 batches with approximately 1-month windows (44640 minutes = 31 days).
