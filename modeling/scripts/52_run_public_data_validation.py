"""重跑公开数据分析，使用唯一目录并保存可追溯元数据。"""

from __future__ import annotations

import hashlib
import importlib.util
import json
import platform
import re
import sys
import uuid
from datetime import datetime, timezone
from pathlib import Path
from urllib.error import URLError
from urllib.request import Request, urlopen

import argparse

ROOT = Path(__file__).resolve().parents[2]
OUTPUT_ROOT = ROOT / "modeling" / "data" / "03_output" / "competition-public-data"
ZENODO_RECORDS = {
    "external_zurich": "3890931",
    "external_finland": "20825233",
}


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def load_script(number: int, name: str):
    path = Path(__file__).with_name(f"{number}_{name}.py")
    spec = importlib.util.spec_from_file_location(f"foodwise_{name}", path)
    if spec is None or spec.loader is None:
        raise ImportError(f"无法加载分析脚本: {path}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def zenodo_metadata(record_id: str) -> dict:
    """Read the record-level license from Zenodo; retain failure as explicit evidence."""
    url = f"https://zenodo.org/api/records/{record_id}"
    request = Request(url, headers={"User-Agent": "FOODWISE-competition-validation/1.0"})
    try:
        with urlopen(request, timeout=15) as response:
            payload = json.loads(response.read().decode("utf-8"))
        metadata = payload.get("metadata", {})
        license_info = metadata.get("license") or {}
        return {
            "status": "verified",
            "api_url": url,
            "retrieved_at_utc": datetime.now(timezone.utc).isoformat(),
            "record_id": str(payload.get("id", record_id)),
            "doi": payload.get("doi"),
            "title": metadata.get("title"),
            "license_id": license_info.get("id"),
            "license_title": license_info.get("title"),
            "record_modified": payload.get("updated"),
        }
    except (URLError, TimeoutError, ValueError, OSError) as error:
        return {
            "status": "unavailable",
            "api_url": url,
            "retrieved_at_utc": datetime.now(timezone.utc).isoformat(),
            "error": f"{type(error).__name__}: {error}",
            "license_id": None,
        }


def _sha256(path: Path) -> str:
    return sha256(path)


def _new_output_dir(output_root: Path, run_id: str | None = None) -> tuple[str, Path]:
    if run_id is None:
        stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
        run_id = f"{stamp}-{uuid.uuid4().hex[:8]}"
    if not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9._-]{0,79}", run_id):
        raise ValueError("run_id 仅允许字母、数字、点、下划线和短横线")
    target = output_root / run_id
    target.mkdir(parents=True, exist_ok=False)
    return run_id, target


def run(output_root: Path = OUTPUT_ROOT, run_id: str | None = None) -> dict:
    started_at = datetime.now(timezone.utc).isoformat()
    run_id, output = _new_output_dir(Path(output_root), run_id)
    runs = [
        (47, "external_zurich", ROOT.parent / "数据来源" / "ZHAW_canteen_menu_sales_2017"
         / "2017_ZHAW_aggregated_menu_sales_NOVANIMAL.csv"),
        (49, "external_finland", ROOT.parent / "数据来源" / "Finland_school_food_waste_2024_2025"
         / "Food waste data school Finland 2024-2025.xlsx"),
        (50, "external_germany", ROOT.parent / "数据来源" / "Reduce-Foodwaste-Dataset" / "train.csv"),
    ]
    results = {}
    for number, name, source in runs:
        if not source.is_file():
            raise FileNotFoundError(f"缺少公开数据原件: {source}")
        module = load_script(number, name)
        module.OUT = output / f"{name}.json"
        payload = module.run()
        results[name] = {
            "source_file": str(source.relative_to(ROOT.parent)),
            "source_sha256": sha256(source),
            "source_size_bytes": source.stat().st_size,
            "result_file": module.OUT.name,
            "result_sha256": sha256(module.OUT),
            "result": payload,
        }
        if name in ZENODO_RECORDS:
            results[name]["record_metadata"] = zenodo_metadata(ZENODO_RECORDS[name])
    report = {
        "run_id": run_id,
        "run_started_at_utc": started_at,
        "run_finished_at_utc": datetime.now(timezone.utc).isoformat(),
        "python_version": platform.python_version(),
        "command": [sys.executable, *sys.argv],
        "evidence_type": "public_dataset_reanalysis",
        "synthetic": False,
        "warning": "公开数据为真实外部数据，但均非中国高校食堂的项目现场效果。",
        "scripts": {
            **{f"{number}_{name}.py": _sha256(Path(__file__).with_name(f"{number}_{name}.py"))
               for number, name, _ in runs},
            Path(__file__).name: _sha256(Path(__file__)),
        },
        "runs": results,
    }
    target = output / "summary.json"
    target.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    return {"run_id": run_id, "output": str(target), "datasets": list(results), "sha256": {
        name: value["source_sha256"] for name, value in results.items()
    }}


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output-root", type=Path, default=OUTPUT_ROOT)
    parser.add_argument("--run-id", help="可选的可复现运行目录名；已存在时拒绝覆盖")
    arguments = parser.parse_args()
    print(json.dumps(run(arguments.output_root, arguments.run_id), ensure_ascii=False, indent=2))
