"""刷新 classpath 模型清单（manifest v2），哈希全部由文件计算，不手写。"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "modeling"))

from foodwise_ml.manifest import ManifestError, build_manifest, write_manifest  # noqa: E402

DEFAULT_BASE = ROOT / "src" / "main" / "resources"
MANIFEST_RELATIVE = Path("modeling") / "model_manifest.json"


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--model-version", required=True, help="例如 2026.10.27-campus-point-v1")
    parser.add_argument("--model-kind", default="point", choices=("point", "quantile", "calibrated-quantile"))
    parser.add_argument("--dataset", default="finetune_uwaste")
    parser.add_argument("--data", type=Path, default=ROOT / "modeling" / "data" / "02_processed" / "finetune_uwaste.parquet")
    parser.add_argument("--base", type=Path, default=DEFAULT_BASE)
    parser.add_argument("--force", action="store_true", help="覆盖已存在的清单")
    args = parser.parse_args()

    target = args.base / MANIFEST_RELATIVE
    if target.exists() and not args.force:
        print(f"REFUSE_OVERWRITE:{target}（如需刷新请加 --force）", file=sys.stderr)
        return 2

    try:
        manifest = build_manifest(
            base_dir=args.base,
            model_file="modeling/lgbm_campus_model.txt",
            feature_file="modeling/campus_feature_cols.json",
            data_file=args.data,
            dataset=args.dataset,
            model_version=args.model_version,
            model_kind=args.model_kind,
        )
    except ManifestError as error:
        print(f"MANIFEST_BUILD_FAILED:{error}", file=sys.stderr)
        return 1

    write_manifest(target, manifest)
    print(json.dumps({"written": str(target), "model_sha256": manifest["model_sha256"], "schema_version": manifest["schema_version"]}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())