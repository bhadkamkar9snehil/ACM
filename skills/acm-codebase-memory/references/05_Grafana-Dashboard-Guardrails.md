# Grafana Dashboard Guardrails

## Scope

Use this note when editing ACM dashboard JSON files.

## Color Mode Rule

1. Grafana color palette IDs are exact strings.
2. For red-yellow-green continuous palette use `continuous-RdYlGr`.
3. Never use `continuous-RdYlGn` because Grafana rejects it.

## Paths

1. `install/observability/dashboards/active`
2. `grafana_dashboards/active`
3. Keep both locations synchronized.

## Validation

1. `python skills/grafana-dashboard-ops/scripts/validate_grafana_palette_modes.py`
