"""校验模型产物契约：manifest 结构 + 文件哈希 + 校准绑定，失败即退出非零。

用于 CI 与 `modeling/scripts/verify_current.py`，是“包打好了”与“包可信”之间的卡口。
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "modeling"))

from foodwise_ml.manifest import (  # noqa: E402
    load_manifest,
    validate_manifest,
    verify_artifact_hashes,
)

DEFAULT_BASE = ROOT / "src" / "main" / "resources"
DEFAULT_MANIFEST = DEFAULT_BASE / "modeling" / "model_manifest.json"


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--manifest", type=Path, default=DEFAULT_MANIFEST)
    parser.add_argument("--base", type=Path, default=DEFAULT_BASE)
    parser.add_argument("--json", action="store_true", help="以 JSON 输出结果")
    args = parser.parse_args()

    if not args.manifest.is_file():
        print(f"MANIFEST_MISSING:{args.manifest}", file=sys.stderr)
        return 1

    try:
        doc = load_manifest(args.manifest)
    except json.JSONDecodeError as error:
        print(f"MANIFEST_NOT_JSON:{error}", file=sys.stderr)
        return 1

    errors = validate_manifest(doc)
    if not errors:
        errors = verify_artifact_hashes(doc, args.base)

    result = {
        "manifest": str(args.manifest),
        "model_version": doc.get("model_version"),
        "model_kind": doc.get("model_kind"),
        "calibration_status": (doc.get("calibration") or {}).get("status"),
        "errors": errors,
        "ok": not errors,
    }
    if args.json:
        print(json.dumps(result, ensure_ascii=False, indent=2))
    elif errors:
        print("MANIFEST_CONTRACT_FAILED", file=sys.stderr)
        for error in errors:
            print(f"  - {error}", file=sys.stderr)
    else:
        print(
            "Manifest contract OK: "
            f"{result['model_version']} / {result['model_kind']} / calibration={result['calibration_status']}"
        )
    return 0 if not errors else 1


if __name__ == "__main__":
    raise SystemExit(main())