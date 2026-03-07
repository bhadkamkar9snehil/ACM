---
name: grafana-dashboard-ops
description: Repair and validate ACM Grafana dashboards that are provisioned from JSON files and backed by SQL Server. Use when dashboard panels fail, datasource linkages break, schema or column names drift, provisioning logs show UID conflicts, or dashboard files under install/observability and grafana_dashboards need synchronized fixes.
---

# Grafana Dashboard Ops

## Workflow

1. Audit Grafana runtime first.
2. Identify active provisioned files and duplicate UIDs.
3. Validate panel SQL against ACM schema.
4. Patch dashboard JSON in both paths:
   - `install/observability/dashboards`
   - `grafana_dashboards`
5. Re-run validation and confirm no panel query errors.
6. Keep archive dashboards non-active unless explicitly requested.

## Runtime Audit Commands

Use Grafana API from PowerShell:

```powershell
$h=@{Authorization='Basic '+[Convert]::ToBase64String([Text.Encoding]::ASCII.GetBytes('admin:admin'))}
Invoke-RestMethod -Uri 'http://localhost:3000/api/search?type=dash-db' -Headers $h
Invoke-RestMethod -Uri 'http://localhost:3000/api/datasources' -Headers $h
docker logs --tail 300 acm-grafana
```

## Dashboard Validation

Run:

```powershell
python skills/grafana-dashboard-ops/scripts/validate_grafana_palette_modes.py
python skills/grafana-dashboard-ops/scripts/validate_acm_dashboards.py
python skills/grafana-dashboard-ops/scripts/validate_grafana_api_queries.py
```

This script checks:
- duplicate dashboard UIDs
- invalid Grafana palette mode IDs (for example, reject `continuous-RdYlGn`)
- datasource UID consistency in panel targets
- SQL query execution against ACM SQL Server with macro substitutions
- runtime execution through Grafana `/api/ds/query` for active dashboards

## Repair Rules

1. Keep datasource UID as `mssql-ds` for SQL panels.
2. Use `dbo.` schema prefix for ACM SQL tables.
3. Match current table columns; do not assume historical columns.
4. Do not provision archive dashboards in the active provider path.
5. Keep dashboard files synchronized between both dashboard directories.
6. Use only Grafana-supported color modes. For red-yellow-green gradients use `continuous-RdYlGr`, never `continuous-RdYlGn`.

## References

- ACM mapping and paths: `skills/grafana-dashboard-ops/references/acm-grafana-mapping.md`
