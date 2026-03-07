import ast
from pathlib import Path
from typing import Any, Dict, List


def _load_validate_regime_config():
    source_path = Path(__file__).resolve().parents[1] / "core" / "regimes.py"
    source = source_path.read_text(encoding="utf-8-sig")
    module = ast.parse(source, filename=str(source_path))

    selected_nodes = []
    for node in module.body:
        if isinstance(node, ast.Assign):
            for target in node.targets:
                if isinstance(target, ast.Name) and target.id == "_REGIME_CONFIG_SCHEMA":
                    selected_nodes.append(node)
                    break
        elif isinstance(node, ast.FunctionDef) and node.name == "_validate_regime_config":
            selected_nodes.append(node)

    def _cfg_get(cfg: Dict[str, Any], path: str, default: Any) -> Any:
        current: Any = cfg
        for part in path.split("."):
            if not isinstance(current, dict) or part not in current:
                return default
            current = current[part]
        return current

    namespace = {
        "Any": Any,
        "Dict": Dict,
        "List": List,
        "_cfg_get": _cfg_get,
    }
    exec(compile(ast.Module(body=selected_nodes, type_ignores=[]), str(source_path), "exec"), namespace)
    return namespace["_validate_regime_config"]


def _valid_regime_cfg(enabled: bool) -> dict:
    return {
        "regimes": {
            "auto_k": {
                "k_min": 2,
                "k_max": 6,
                "max_models": 10,
                "max_eval_samples": 5000,
            },
            "quality": {
                "silhouette_min": 0.3,
            },
            "smoothing": {
                "passes": 3,
                "window": 7,
            },
            "transient_detection": {
                "roc_window": 10,
                "roc_threshold_high": 0.15,
                "roc_threshold_trip": 0.3,
            },
            "health": {
                "fused_warn_z": 2.5,
                "fused_alert_z": 4.0,
            },
            "unknown": {
                "enabled": enabled,
                "distance_percentile": 99.0,
            },
        }
    }


def test_validate_regime_config_accepts_unknown_enabled_false():
    validate_regime_config = _load_validate_regime_config()

    issues = validate_regime_config(_valid_regime_cfg(enabled=False))

    assert not any("regimes.unknown.enabled" in issue for issue in issues)
