"""盘点 数据来源/ 下每个数据集的结构、时间跨度与许可，产出可直接写进方案的事实表。"""

import json
from pathlib import Path

import pyarrow.parquet as pq

ROOT = Path(r"E:\食刻有数\数据来源")
OUT = Path(r"E:\食刻有数\项目代码\modeling\data\03_output\dataset_inventory.json")


def csv_head(path: Path, n: int = 200000):
    import pandas as pd

    return pd.read_csv(path, nrows=n)


def describe_csv(path: Path) -> dict:
    try:
        frame = csv_head(path)
        return {
            "rows_sampled": int(len(frame)),
            "columns": list(frame.columns),
            "sample": frame.head(2).to_dict("records"),
        }
    except Exception as error:  # noqa: BLE001
        return {"error": str(error)}


def describe_parquet(path: Path) -> dict:
    handle = pq.ParquetFile(path)
    schema = handle.schema_arrow
    info = {
        "rows": handle.metadata.num_rows,
        "row_groups": handle.metadata.num_row_groups,
        "columns": schema.names,
        "dtypes": [str(field.type) for field in schema],
    }
    try:
        first = next(handle.iter_batches(batch_size=2)).to_pydict()
        info["sample"] = {key: [str(value) for value in values] for key, values in first.items()}
    except Exception:  # noqa: BLE001
        pass
    return info


def main() -> int:
    report = {}
    for path in sorted(ROOT.rglob("*")):
        if not path.is_file():
            continue
        suffix = path.suffix.lower()
        entry = {"size_bytes": path.stat().st_size}
        if suffix in (".csv", ".txt"):
            entry.update(describe_csv(path))
        elif suffix == ".parquet":
            entry.update(describe_parquet(path))
        elif suffix in (".md", ".txt") and "README" in path.name.upper():
            entry["text"] = path.read_text(encoding="utf-8", errors="replace")[:1200]
        elif path.name.upper() == "LICENSE":
            entry["text"] = path.read_text(encoding="utf-8", errors="replace")[:800]
        report[str(path.relative_to(ROOT))] = entry

    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    for name, entry in report.items():
        if "columns" in entry:
            rows = entry.get("rows") or entry.get("rows_sampled")
            print(f"{name}: rows={rows} cols={len(entry['columns'])}")
            print("   ", ", ".join(entry["columns"][:14]))
        else:
            print(f"{name}: {entry['size_bytes']} bytes")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())