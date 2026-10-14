"""Audit original CSV labels without treating reconstructed quantities as observations."""
from pathlib import Path
import csv
import hashlib
import json

ROOT = Path(__file__).resolve().parents[2]
RAW = ROOT / 'modeling/data/01_raw'


def audit():
    reports = []
    for path in sorted(RAW.rglob('*.csv')):
        # Do not read personal transaction/customer files during an aggregate audit.
        if path.parent.name == 'gylaf_campus':
            continue
        with path.open(encoding='utf-8-sig', newline='') as handle:
            reader = csv.DictReader(handle)
            columns = reader.fieldnames or []
            rows = sum(1 for _ in reader)
        targets = [c for c in ('sales', 'num_orders', 'sold_qty', 'Units Sold') if c in columns]
        template = path.name == 'sample_submission.csv'
        has_time = any(c in columns for c in ('date', 'Date', 'week', 'business_date'))
        reports.append({
            'file': path.relative_to(ROOT).as_posix(), 'rows': rows, 'columns': columns,
            'sha256': hashlib.sha256(path.read_bytes()).hexdigest(),
            'observed_sales_columns': targets,
            'sales_validation_eligible': bool(targets) and not template and has_time,
            'requires_label_join': bool(targets) and not has_time and not template,
            'submission_template_not_labels': template,
            'sampling_origin_status': 'supplier_provenance_review_required',
            'limitations': (
                ['No sales label. Metadata or waste measurements cannot establish observed sales.']
                if not targets else
                (['Submission placeholder; never evaluate as observed labels.'] if template else
                 ['Supplier label; time/entity alignment, stock censoring and license review required.'])
            ),
        })
    return {'schema_version': 'source-audit-v1', 'files': reports,
            'simulation_ledger': 'src/main/resources/data/foodwise_operations_14d.csv',
            'simulation_is_field_evidence': False,
            'gylaf': 'Aggregate files require date/unit alignment; personal files excluded.',
            'reduce_foodwaste_unit': 'Scaled sales, not directly local servings or currency.'}


if __name__ == '__main__':
    output = ROOT / 'modeling/data/03_output/source_audit_v1.json'
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(audit(), ensure_ascii=False, indent=2), encoding='utf-8')
    print(output)
