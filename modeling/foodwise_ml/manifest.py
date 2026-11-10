"""食刻有数 · 模型产物契约（Python 侧唯一权威实现）。

契约目标：让 Python 侧产出的模型/校准/成本/指标可以被 Java 侧按同一份 manifest 校验，
并让“未验证”成为合法状态——宁可写 null，也不许填假数字。

约定：
  * manifest 中的路径（model_file / feature_file / calibration.artifact）均相对 classpath 根，
    即仓库内 `src/main/resources/`。
  * `model_sha256`、`feature_sha256` 为 Java 启动校验使用，键名不得改动。
  * 任何被标为 calibrated 的产物必须同时给出覆盖率指标，否则视为违约。
"""

from __future__ import annotations

import hashlib
import json
import re
from datetime import datetime, timezone
from pathlib import Path

SCHEMA_VERSION = 2
MODEL_KINDS = ("point", "quantile", "calibrated-quantile")
CALIBRATION_STATUS = ("uncalibrated", "calibrated", "failed")

_SHA256 = re.compile(r"^[0-9a-f]{64}$")
_METRIC_KEYS = ("mae", "mase", "picp90", "pinaw90", "winkler90", "regret")
_COST_KEYS = ("price", "unit_cost", "discount_price", "shortage_penalty_lambda")
_REQUIRED = (
    "schema_version",
    "bundle_version",
    "model_version",
    "model_kind",
    "source_kind",
    "created_at",
    "model_file",
    "model_sha256",
    "feature_file",
    "feature_sha256",
    "quantiles",
    "calibration",
    "cost_model",
    "metrics",
    "data",
    "limits",
)


class ManifestError(ValueError):
    """Raised when a manifest violates the artifact contract."""


def sha256_bytes(payload: bytes) -> str:
    return hashlib.sha256(payload).hexdigest()


def sha256_file(path: Path) -> str:
    return sha256_bytes(Path(path).read_bytes())


def _is_number(value) -> bool:
    return isinstance(value, (int, float)) and not isinstance(value, bool)


def _unit_interval(value) -> bool:
    return _is_number(value) and 0.0 <= float(value) <= 1.0


def _iso_datetime(value) -> bool:
    if not isinstance(value, str) or not value:
        return False
    try:
        datetime.fromisoformat(value.replace("Z", "+00:00"))
        return True
    except ValueError:
        return False


def validate_manifest(doc) -> list[str]:
    """Return a list of contract violations; empty list means valid."""
    if not isinstance(doc, dict):
        return ["MANIFEST_MUST_BE_OBJECT"]

    errors: list[str] = []
    missing = [key for key in _REQUIRED if key not in doc]
    if missing:
        errors.append("MISSING_KEYS:" + ",".join(missing))
        return errors  # 后续校验依赖这些键

    if doc["schema_version"] != SCHEMA_VERSION:
        errors.append(f"SCHEMA_VERSION_UNSUPPORTED:{doc['schema_version']}")
    if not isinstance(doc["bundle_version"], str) or not doc["bundle_version"]:
        errors.append("BUNDLE_VERSION_INVALID")
    if not isinstance(doc["model_version"], str) or not doc["model_version"]:
        errors.append("MODEL_VERSION_INVALID")
    if doc["model_kind"] not in MODEL_KINDS:
        errors.append(f"MODEL_KIND_INVALID:{doc['model_kind']}")
    if not isinstance(doc["source_kind"], str) or not doc["source_kind"]:
        errors.append("SOURCE_KIND_INVALID")
    if not _iso_datetime(doc["created_at"]):
        errors.append("CREATED_AT_NOT_ISO8601")

    for key in ("model_file", "feature_file"):
        value = doc[key]
        if not isinstance(value, str) or not value or value.startswith("/") or ".." in value:
            errors.append(f"ARTIFACT_PATH_INVALID:{key}")
    for key in ("model_sha256", "feature_sha256"):
        value = doc[key]
        if not isinstance(value, str) or not _SHA256.match(value):
            errors.append(f"SHA256_INVALID:{key}")

    quantiles = doc["quantiles"]
    if not isinstance(quantiles, list):
        errors.append("QUANTILES_NOT_LIST")
    else:
        numeric = [q for q in quantiles if _is_number(q) and 0.0 < float(q) < 1.0]
        if len(numeric) != len(quantiles):
            errors.append("QUANTILES_OUT_OF_RANGE")
        elif numeric != sorted(numeric):
            errors.append("QUANTILES_NOT_ASCENDING")
        if numeric and doc["model_kind"] == "point":
            errors.append("POINT_MODEL_WITH_QUANTILES")

    quantile_models = doc.get("quantile_models")
    if quantile_models is not None:
        if not isinstance(quantile_models, dict) or not quantile_models:
            errors.append("QUANTILE_MODELS_INVALID")
        else:
            levels: list[float] = []
            for level, entry in quantile_models.items():
                try:
                    parsed = float(level)
                except (TypeError, ValueError):
                    errors.append(f"QUANTILE_LEVEL_INVALID:{level}")
                    continue
                if not 0.0 < parsed < 1.0:
                    errors.append(f"QUANTILE_LEVEL_OUT_OF_RANGE:{level}")
                levels.append(parsed)
                if not isinstance(entry, dict):
                    errors.append(f"QUANTILE_ENTRY_INVALID:{level}")
                    continue
                path = entry.get("file")
                if not isinstance(path, str) or not path or path.startswith("/") or ".." in path:
                    errors.append(f"QUANTILE_FILE_INVALID:{level}")
                digest = entry.get("sha256")
                if not isinstance(digest, str) or not _SHA256.match(digest):
                    errors.append(f"QUANTILE_SHA256_INVALID:{level}")
            if levels and isinstance(quantiles, list):
                if sorted(levels) != sorted(float(q) for q in quantiles if _is_number(q)):
                    errors.append("QUANTILE_LEVELS_MISMATCH")
    elif doc["model_kind"] != "point":
        errors.append("QUANTILE_MODELS_MISSING")

    calibration = doc["calibration"]
    if not isinstance(calibration, dict):
        errors.append("CALIBRATION_NOT_OBJECT")
    else:
        status = calibration.get("status")
        if status not in CALIBRATION_STATUS:
            errors.append(f"CALIBRATION_STATUS_INVALID:{status}")
        for key in ("method", "artifact", "artifact_sha256", "alpha", "picp90"):
            if key not in calibration:
                errors.append(f"CALIBRATION_KEY_MISSING:{key}")
        if status == "calibrated":
            if not isinstance(calibration.get("method"), str) or not calibration["method"]:
                errors.append("CALIBRATED_WITHOUT_METHOD")
            alpha = calibration.get("alpha")
            if not (_is_number(alpha) and 0.0 < float(alpha) < 1.0):
                errors.append("CALIBRATED_ALPHA_INVALID")
            artifact = calibration.get("artifact")
            if not isinstance(artifact, str) or not artifact:
                errors.append("CALIBRATED_WITHOUT_ARTIFACT")
            digest = calibration.get("artifact_sha256")
            if not isinstance(digest, str) or not _SHA256.match(digest):
                errors.append("CALIBRATED_ARTIFACT_SHA256_INVALID")
            if not _unit_interval(calibration.get("picp90")):
                errors.append("CALIBRATED_WITHOUT_COVERAGE")
        else:
            if calibration.get("picp90") is not None and not _unit_interval(calibration.get("picp90")):
                errors.append("CALIBRATION_PICP_OUT_OF_RANGE")

    cost_model = doc["cost_model"]
    if not isinstance(cost_model, dict):
        errors.append("COST_MODEL_NOT_OBJECT")
    else:
        if "defaults" not in cost_model or not isinstance(cost_model["defaults"], dict):
            errors.append("COST_DEFAULTS_MISSING")
        else:
            defaults = cost_model["defaults"]
            for key in _COST_KEYS:
                if key not in defaults:
                    errors.append(f"COST_KEY_MISSING:{key}")
                    continue
                value = defaults[key]
                if value is None:
                    continue
                if not _is_number(value):
                    errors.append(f"COST_VALUE_NOT_NUMBER:{key}")
                elif key == "shortage_penalty_lambda":
                    if float(value) < 0:
                        errors.append("COST_LAMBDA_NEGATIVE")
                elif float(value) <= 0:
                    errors.append(f"COST_VALUE_NOT_POSITIVE:{key}")
        if not isinstance(cost_model.get("source"), str) or not cost_model["source"]:
            errors.append("COST_SOURCE_INVALID")

    metrics = doc["metrics"]
    if not isinstance(metrics, dict):
        errors.append("METRICS_NOT_OBJECT")
    else:
        for key in _METRIC_KEYS:
            if key not in metrics:
                errors.append(f"METRIC_KEY_MISSING:{key}")
                continue
            value = metrics[key]
            if value is not None and not _is_number(value):
                errors.append(f"METRIC_NOT_NUMBER:{key}")
        for key in ("picp90", "pinaw90"):
            value = metrics.get(key)
            if value is not None and not _unit_interval(value):
                errors.append(f"METRIC_OUT_OF_RANGE:{key}")
        if "evaluated_on" not in metrics:
            errors.append("METRIC_KEY_MISSING:evaluated_on")
        if doc["model_kind"] == "calibrated-quantile" and metrics.get("picp90") is None:
            errors.append("CALIBRATED_MODEL_WITHOUT_EVALUATION")

    data = doc["data"]
    if not isinstance(data, dict):
        errors.append("DATA_NOT_OBJECT")
    else:
        if not isinstance(data.get("dataset"), str) or not data["dataset"]:
            errors.append("DATA_DATASET_INVALID")
        rows = data.get("rows")
        if not isinstance(rows, int) or isinstance(rows, bool) or rows <= 0:
            errors.append("DATA_ROWS_INVALID")
        digest = data.get("sha256")
        if digest is not None and (not isinstance(digest, str) or not _SHA256.match(digest)):
            errors.append("DATA_SHA256_INVALID")

    limits = doc["limits"]
    if not isinstance(limits, list) or not limits:
        errors.append("LIMITS_MISSING")
    elif not all(isinstance(item, str) and len(item) >= 8 for item in limits):
        errors.append("LIMITS_ENTRY_TOO_SHORT")

    return errors


def assert_valid(doc) -> None:
    errors = validate_manifest(doc)
    if errors:
        raise ManifestError("; ".join(errors))


def verify_artifact_hashes(doc, base_dir: Path) -> list[str]:
    """Verify every hash the manifest claims against files under base_dir."""
    base = Path(base_dir)
    errors: list[str] = []
    for path_key, hash_key in (
        ("model_file", "model_sha256"),
        ("feature_file", "feature_sha256"),
    ):
        target = base / str(doc.get(path_key, ""))
        if not target.is_file():
            errors.append(f"ARTIFACT_MISSING:{path_key}:{target}")
            continue
        if sha256_file(target) != str(doc.get(hash_key, "")).lower():
            errors.append(f"ARTIFACT_HASH_MISMATCH:{path_key}")

    calibration = doc.get("calibration") or {}
    if calibration.get("status") == "calibrated":
        artifact = calibration.get("artifact")
        target = base / str(artifact or "")
        if not target.is_file():
            errors.append(f"ARTIFACT_MISSING:calibration:{target}")
        elif sha256_file(target) != str(calibration.get("artifact_sha256", "")).lower():
            errors.append("ARTIFACT_HASH_MISMATCH:calibration")

    for level, entry in (doc.get("quantile_models") or {}).items():
        target = base / str(entry.get("file", ""))
        if not target.is_file():
            errors.append(f"ARTIFACT_MISSING:quantile:{level}:{target}")
        elif sha256_file(target) != str(entry.get("sha256", "")).lower():
            errors.append(f"ARTIFACT_HASH_MISMATCH:quantile:{level}")
    return errors


def load_manifest(path: Path) -> dict:
    return json.loads(Path(path).read_text(encoding="utf-8"))


def write_manifest(path: Path, doc: dict) -> None:
    assert_valid(doc)
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(doc, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def build_manifest(
    *,
    base_dir: Path,
    model_file: str,
    feature_file: str,
    data_file: Path,
    dataset: str,
    model_version: str,
    model_kind: str = "point",
    source_kind: str = "derived-target-demonstration",
    bundle_version: str = "campus-local-v1",
    limits: list[str] | None = None,
    cost_defaults: dict | None = None,
    quantiles: list[float] | None = None,
    calibration: dict | None = None,
    metrics: dict | None = None,
    quantile_models: dict[str, str] | None = None,
) -> dict:
    """Build a manifest from real files on disk; hashes are computed, never hand-written."""
    base = Path(base_dir)
    model_path = base / model_file
    feature_path = base / feature_file
    if not model_path.is_file():
        raise ManifestError(f"MODEL_FILE_MISSING:{model_path}")
    if not feature_path.is_file():
        raise ManifestError(f"FEATURE_FILE_MISSING:{feature_path}")
    if not Path(data_file).is_file():
        raise ManifestError(f"DATA_FILE_MISSING:{data_file}")

    defaults = {
        "price": None,
        "unit_cost": None,
        "discount_price": None,
        "shortage_penalty_lambda": 0.3,
    }
    if cost_defaults:
        defaults.update(cost_defaults)

    built_quantiles: dict[str, dict] = {}
    for level, relative in (quantile_models or {}).items():
        path = base / str(relative)
        if not path.is_file():
            raise ManifestError(f"QUANTILE_FILE_MISSING:{path}")
        built_quantiles[str(level)] = {"file": str(relative), "sha256": sha256_file(path)}

    manifest = {
        "schema_version": SCHEMA_VERSION,
        "bundle_version": bundle_version,
        "model_version": model_version,
        "model_kind": model_kind,
        "source_kind": source_kind,
        "created_at": datetime.now(timezone.utc).astimezone().isoformat(timespec="seconds"),
        "model_file": model_file,
        "model_sha256": sha256_file(model_path),
        "feature_file": feature_file,
        "feature_sha256": sha256_file(feature_path),
        "quantiles": list(quantiles or []),
        "calibration": calibration
        or {
            "method": None,
            "status": "uncalibrated",
            "alpha": None,
            "artifact": None,
            "artifact_sha256": None,
            "picp90": None,
        },
        "cost_model": {"source": "unset" if not cost_defaults else "declared", "defaults": defaults},
        "metrics": {
            "mae": None,
            "mase": None,
            "picp90": None,
            "pinaw90": None,
            "winkler90": None,
            "regret": None,
            "evaluated_on": None,
            **(metrics or {}),
        },
        "data": {
            "dataset": dataset,
            "rows": int(_row_count(data_file)),
            "sha256": sha256_file(data_file),
        },
        "limits": limits
        or [
            "公开来源标签为派生目标，不能当作观测销量或现场精度结论。",
            "区间覆盖率与决策成本指标未评估前，不得在页面或答辩中引用具体数值。",
            "Java 特征值与推理一致性需单独验收，打包本身不构成验证。",
        ],
    }
    if built_quantiles:
        manifest["quantile_models"] = built_quantiles
    assert_valid(manifest)
    return manifest


def _row_count(data_file: Path) -> int:
    suffix = Path(data_file).suffix.lower()
    if suffix == ".parquet":
        import pandas as pd  # 仅在此处按需导入，避免契约模块强依赖 pandas

        return int(len(pd.read_parquet(data_file)))
    if suffix in {".csv", ".tsv"}:
        with open(data_file, encoding="utf-8") as handle:
            return max(0, sum(1 for _ in handle) - 1)
    raise ManifestError(f"DATA_FORMAT_UNSUPPORTED:{suffix}")