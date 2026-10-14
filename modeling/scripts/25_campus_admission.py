"""Offline campus CSV admission. Never promotes templates to training evidence."""
import argparse
from collections import Counter, defaultdict
import csv
from datetime import date, datetime, timezone
from decimal import Decimal, InvalidOperation
import hashlib
import json
from pathlib import Path

KEY = ['school_id', 'stall_id', 'dish_id', 'business_date', 'meal_period']
QUANTITIES = ['opening_qty', 'prepared_qty', 'transfer_in_qty', 'transfer_out_qty',
    'sold_regular_qty', 'sold_discount_qty', 'refund_qty', 'returned_to_kitchen_qty',
    'discarded_qty', 'closing_qty']
TARGET = 'net_sales_disjoint_refunds_already_deducted'


def timestamp(value):
    parsed = datetime.fromisoformat(value)
    if parsed.tzinfo is None:
        raise ValueError('timezone required')
    return parsed


def number(value):
    parsed = Decimal(str(value))
    if not parsed.is_finite() or parsed < 0:
        raise ValueError('finite nonnegative required')
    return parsed


def validate_observations(rows, sources, as_of):
    cutoff = timestamp(as_of)
    registry = defaultdict(list)
    for source in sources:
        registry[source.get('source_id', '')].append(source)
    keys = Counter(tuple(r.get(k, '') for k in KEY) for r in rows)
    units = defaultdict(set)
    for row in rows:
        units[tuple(row.get(k, '') for k in KEY[:3])].add(row.get('unit', ''))
    accepted, quarantined = [], []
    for index, row in enumerate(rows, 2):
        reasons = []
        key = tuple(row.get(k, '') for k in KEY)
        if any(not value.strip() for value in key):
            reasons.append('MISSING_PRIMARY_KEY')
        if keys[key] != 1:
            reasons.append('DUPLICATE_PRIMARY_KEY')
        if len(units[key[:3]]) != 1:
            reasons.append('ENTITY_UNIT_CHANGED')
        if row.get('unit') not in {'portion', 'kg'}:
            reasons.append('UNSUPPORTED_UNIT')
        try:
            day = date.fromisoformat(row.get('business_date', ''))
            recorded = timestamp(row.get('recorded_at', ''))
            if day > cutoff.date() or recorded > cutoff or recorded.date() < day:
                reasons.append('OBSERVATION_TIME_INVALID')
        except (ValueError, TypeError):
            reasons.append('OBSERVATION_TIME_INVALID')
        source_matches = registry.get(row.get('source_id', ''), [])
        if len(source_matches) != 1:
            reasons.append('SOURCE_MISSING_OR_AMBIGUOUS')
        else:
            source = source_matches[0]
            if (source.get('provenance_status') != 'verified' or
                not source.get('authorization_reference', '').strip() or
                not source.get('license_reference', '').strip() or
                'model_training' not in source.get('permitted_use', '').split(';')):
                reasons.append('SOURCE_NOT_AUTHORIZED')
            if source.get('label_origin') != 'observed' or row.get('label_origin') != 'observed':
                reasons.append('NON_OBSERVED_LABEL')
            if (source.get('target_definition') != TARGET or
                source.get('unit') != row.get('unit') or
                source.get('time_granularity') != 'meal' or
                source.get('entity_granularity') != 'dish'):
                reasons.append('SOURCE_CONTRACT_MISMATCH')
            digest = source.get('sha256', '')
            if len(digest) != 64 or any(c not in '0123456789abcdef' for c in digest.lower()):
                reasons.append('SOURCE_HASH_INVALID')
            try:
                if timestamp(source.get('acquired_at', '')) > cutoff:
                    reasons.append('SOURCE_NOT_YET_AVAILABLE')
            except (ValueError, TypeError):
                reasons.append('SOURCE_TIME_INVALID')
        values = {}
        for field in QUANTITIES + ['revenue', 'unavailable_minutes', 'actual_plan_qty']:
            try:
                values[field] = number(row.get(field, ''))
                if field in QUANTITIES and row.get('unit') == 'portion' and values[field] % 1:
                    reasons.append('FRACTIONAL_PORTION:' + field)
            except (ValueError, TypeError, InvalidOperation):
                reasons.append('INVALID_NUMBER:' + field)
        if all(field in values for field in QUANTITIES):
            incoming = sum(values[f] for f in ['opening_qty', 'prepared_qty', 'transfer_in_qty'])
            outgoing = sum(values[f] for f in ['sold_regular_qty', 'sold_discount_qty',
                'transfer_out_qty', 'returned_to_kitchen_qty', 'discarded_qty', 'closing_qty'])
            # Exact Decimal balance; kg rounding must be reconciled upstream, never silently filled.
            if incoming != outgoing:
                reasons.append('INVENTORY_IMBALANCE')
        if row.get('business_status') not in {'open', 'closed'}:
            reasons.append('UNKNOWN_BUSINESS_STATUS')
        elif row.get('business_status') == 'closed':
            reasons.append('CLOSED_NOT_SALES_TRAINING_ROW')
        if row.get('quality_flags', '').strip():
            reasons.append('UNRESOLVED_QUALITY_FLAGS')
        if row.get('stockout_at', '').strip():
            try:
                stockout = timestamp(row['stockout_at'])
                if stockout.date() != date.fromisoformat(row['business_date']) or stockout > cutoff:
                    reasons.append('STOCKOUT_TIME_INVALID')
            except (ValueError, TypeError):
                reasons.append('STOCKOUT_TIME_INVALID')
        output = dict(row, input_csv_line=index)
        if reasons:
            quarantined.append(dict(output, reason_codes=';'.join(sorted(set(reasons)))))
        else:
            output['net_sold_qty'] = str(values['sold_regular_qty'] + values['sold_discount_qty'])
            output['supply_censored'] = bool(row.get('stockout_at', '').strip() or values['unavailable_minutes'] > 0)
            accepted.append(output)
    reason_counts = Counter(code for row in quarantined for code in row['reason_codes'].split(';'))
    return {'accepted': accepted, 'quarantined': quarantined, 'summary': {
        'input_rows': len(rows), 'accepted_rows': len(accepted), 'quarantined_rows': len(quarantined),
        'accepted_fraction': len(accepted)/len(rows) if rows else None,
        'reason_counts': dict(sorted(reason_counts.items())),
        'censored_accepted_rows': sum(r['supply_censored'] for r in accepted),
        'training_ready': False,
        'limitation': 'Schema admission only; manual source evidence, coverage, temporal splits and feature availability still required.'}}


def read_csv(path):
    with path.open(encoding='utf-8-sig', newline='') as stream:
        reader = csv.DictReader(stream)
        if not reader.fieldnames or len(reader.fieldnames) != len(set(reader.fieldnames)):
            raise ValueError('CSV header missing or duplicated')
        rows = list(reader)
        if any(None in row or any(v is None for v in row.values()) for row in rows):
            raise ValueError('CSV row width does not match header')
        return rows, reader.fieldnames


def validate_forecasts(rows, sources):
    """Availability gate only; optional missing features remain missing."""
    registry = defaultdict(list)
    for source in sources:
        registry[source.get('source_id', '')].append(source)
    fields = ['school_id', 'stall_id', 'dish_id', 'target_date', 'meal_period', 'prediction_cutoff_at']
    keys = Counter(tuple(row.get(k, '') for k in fields) for row in rows)
    accepted, quarantined = [], []
    for line, row in enumerate(rows, 2):
        reasons = []
        key = tuple(row.get(k, '') for k in fields)
        if any(not v.strip() for v in key):
            reasons.append('MISSING_FORECAST_KEY')
        if keys[key] != 1:
            reasons.append('DUPLICATE_FORECAST_KEY')
        matches = registry.get(row.get('source_id', ''), [])
        if len(matches) != 1:
            reasons.append('SOURCE_MISSING_OR_AMBIGUOUS')
        elif (matches[0].get('provenance_status') != 'verified' or
              not matches[0].get('authorization_reference', '').strip() or
              'model_features' not in matches[0].get('permitted_use', '').split(';')):
            reasons.append('FEATURE_SOURCE_NOT_AUTHORIZED')
        try:
            cutoff = timestamp(row.get('prediction_cutoff_at', ''))
            target = date.fromisoformat(row.get('target_date', ''))
            if cutoff.date() > target:
                reasons.append('CUTOFF_AFTER_TARGET_DATE')
            if timestamp(row.get('available_at', '')) > cutoff:
                reasons.append('FEATURES_AFTER_CUTOFF')
            if any(row.get(f, '').strip() for f in ['forecast_temperature', 'forecast_precipitation']):
                if timestamp(row.get('forecast_issued_at', '')) > cutoff:
                    reasons.append('WEATHER_AFTER_CUTOFF')
            if row.get('price', '').strip() and timestamp(row.get('price_effective_at', '')) > cutoff:
                # Conservative v1 contract: future-effective price needs a separate announcement timestamp.
                reasons.append('PRICE_EFFECTIVE_AFTER_CUTOFF')
        except (ValueError, TypeError):
            reasons.append('FEATURE_TIME_INVALID')
        for field in ['price', 'unit_cost', 'capacity_qty', 'min_batch_qty', 'lead_time_minutes', 'forecast_precipitation']:
            if row.get(field, '').strip():
                try:
                    number(row[field])
                except (ValueError, TypeError, InvalidOperation):
                    reasons.append('INVALID_NUMBER:' + field)
        if row.get('forecast_temperature', '').strip():
            try:
                if not Decimal(row['forecast_temperature']).is_finite():
                    raise ValueError('finite required')
            except (ValueError, TypeError, InvalidOperation):
                reasons.append('INVALID_NUMBER:forecast_temperature')
        output = dict(row, input_csv_line=line)
        if reasons:
            quarantined.append(dict(output, reason_codes=';'.join(sorted(set(reasons)))))
        else:
            accepted.append(output)
    return {'accepted': accepted, 'quarantined': quarantined,
        'summary': {'input_rows': len(rows), 'accepted_rows': len(accepted),
                    'quarantined_rows': len(quarantined), 'training_ready': False}}


def write_csv(path, rows, fields):
    with path.open('w', encoding='utf-8-sig', newline='') as stream:
        writer = csv.DictWriter(stream, fieldnames=list(dict.fromkeys(fields)))
        writer.writeheader()
        writer.writerows(rows)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--observations', type=Path, required=True)
    parser.add_argument('--sources', type=Path, required=True)
    parser.add_argument('--forecasts', type=Path, help='Optional forecast snapshots, separate from outcomes')
    parser.add_argument('--as-of', required=True, help='Timezone-aware audit snapshot time')
    parser.add_argument('--output', type=Path, required=True, help='New directory; existing output is never overwritten')
    args = parser.parse_args()
    rows, fields = read_csv(args.observations)
    sources, _ = read_csv(args.sources)
    result = validate_observations(rows, sources, args.as_of)
    forecast_result, forecast_fields = None, []
    if args.forecasts:
        forecasts, forecast_fields = read_csv(args.forecasts)
        forecast_result = validate_forecasts(forecasts, sources)
    args.output.mkdir(parents=True, exist_ok=False)
    write_csv(args.output/'accepted.csv', result['accepted'], fields+['input_csv_line', 'net_sold_qty', 'supply_censored'])
    write_csv(args.output/'quarantined.csv', result['quarantined'], fields+['input_csv_line', 'reason_codes'])
    manifest = {'as_of': args.as_of, 'summary': result['summary'], 'inputs': {
        'observations': hashlib.sha256(args.observations.read_bytes()).hexdigest(),
        'sources': hashlib.sha256(args.sources.read_bytes()).hexdigest()},
        'script_sha256': hashlib.sha256(Path(__file__).read_bytes()).hexdigest()}
    if forecast_result is not None:
        write_csv(args.output/'forecasts_accepted.csv', forecast_result['accepted'], forecast_fields+['input_csv_line'])
        write_csv(args.output/'forecasts_quarantined.csv', forecast_result['quarantined'], forecast_fields+['input_csv_line', 'reason_codes'])
        manifest['forecast_summary'] = forecast_result['summary']
        manifest['inputs']['forecasts'] = hashlib.sha256(args.forecasts.read_bytes()).hexdigest()
    (args.output/'report.json').write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding='utf-8')
    print(json.dumps(result['summary'], ensure_ascii=True))


if __name__ == '__main__':
    main()
