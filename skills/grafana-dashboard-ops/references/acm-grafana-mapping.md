# ACM Grafana Mapping

## Active Provisioning Inputs

1. `install/observability/provisioning/dashboards/dashboards.yaml`
2. `install/observability/provisioning/datasources/datasources.yaml`
3. `install/observability/dashboards` (runtime mount target)

## Repository Mirror

1. `grafana_dashboards` must mirror active dashboard JSON changes.

## Grafana Runtime

1. Container: `acm-grafana`
2. URL: `http://localhost:3000`
3. Default auth: `admin/admin`

## Known Datasource UIDs

1. `mssql-ds`
2. `prometheus-ds`
3. `loki-ds`
4. `tempo-ds`
5. `pyroscope-ds`

## SQL Rules

1. Use `dbo.` schema prefix for ACM tables.
2. Validate against current columns from `INFORMATION_SCHEMA.COLUMNS`.
3. Replace historical column names with current names before release.

## Provisioning Rules

1. Do not include archive JSON files in active dashboard provider path.
2. Ensure dashboard UIDs are unique across all provisioned files.
