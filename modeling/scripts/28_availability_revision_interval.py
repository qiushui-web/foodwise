"""Availability-aware replay and independent residual interval calibration."""
from datetime import datetime
import json
from pathlib import Path

import numpy as np
import pandas as pd


def visible_at(observations, cutoff):
    """Return only revisions visible at cutoff; latest visible revision wins per stable id."""
    cutoff = pd.Timestamp(cutoff)
    if cutoff.tzinfo is None:
        cutoff = cutoff.tz_localize('UTC')
    else:
        cutoff = cutoff.tz_convert('UTC')
    frame = observations.copy()
    required = {'observation_id', 'available_at', 'revision_at'}
    missing = required.difference(frame.columns)
    if missing:
        raise ValueError('MISSING_REPLAY_COLUMNS:' + ','.join(sorted(missing)))
    if frame['observation_id'].isna().any() or frame['observation_id'].astype(str).str.strip().eq('').any():
        raise ValueError('MISSING_OBSERVATION_ID')
    frame['available_at'] = pd.to_datetime(frame['available_at'], utc=True, errors='coerce')
    frame['revision_at'] = pd.to_datetime(frame['revision_at'], utc=True, errors='coerce')
    if frame[['available_at', 'revision_at']].isna().any().any():
        raise ValueError('INVALID_REPLAY_TIMESTAMP')
    frame = frame[frame.available_at.le(cutoff) & frame.revision_at.le(cutoff)]
    frame = frame[frame.revision_at.ge(frame.available_at)]
    if frame.duplicated(['observation_id', 'revision_at'], keep=False).any():
        raise ValueError('AMBIGUOUS_REVISION_TIMESTAMP')
    identity = [name for name in ('school_id', 'stall_id', 'dish_id', 'business_date', 'meal_period') if name in frame]
    if identity and frame.groupby('observation_id')[identity].nunique(dropna=False).gt(1).any().any():
        raise ValueError('UNSTABLE_OBSERVATION_ID')
    frame = frame.sort_values(['observation_id', 'revision_at', 'available_at']).drop_duplicates('observation_id', keep='last')
    return frame


def calibrate_residual_interval(calibration, nominal=.8):
    """Use only calibration rows; returns symmetric absolute-residual radius."""
    if calibration.empty:
        raise ValueError('EMPTY_CALIBRATION_SPLIT')
    if not 0 < nominal < 1:
        raise ValueError('INVALID_NOMINAL_COVERAGE')
    residual = (calibration['actual'] - calibration['prediction']).abs().to_numpy(float)
    if not np.isfinite(residual).all():
        raise ValueError('NONFINITE_CALIBRATION_RESIDUAL')
    rank = int(np.ceil((len(residual) + 1) * nominal))
    if rank > len(residual):
        raise ValueError('INSUFFICIENT_CALIBRATION_ROWS_FOR_NOMINAL')
    radius = float(np.sort(residual)[rank - 1])
    return {'nominal': nominal, 'rows': len(residual), 'radius': radius,
            'method': 'absolute_residual_finite_sample_order_statistic',
            'warning': 'Coverage is descriptive and may fail under temporal drift.'}


def replay_and_calibrate(observations, calibration, cutoff):
    visible = visible_at(observations, cutoff)
    interval = calibrate_residual_interval(calibration)
    return {'visible_rows': len(visible), 'visible_observation_ids': visible.observation_id.tolist(),
            'interval': interval, 'training_ready': False}


def main():
    raise SystemExit('Use as a library from the campus training chain; no default files are assumed.')


if __name__ == '__main__':
    main()
