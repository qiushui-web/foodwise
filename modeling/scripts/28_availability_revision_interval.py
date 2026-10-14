"""Availability-aware replay and independent residual interval calibration."""
from datetime import datetime
import json
from pathlib import Path

import numpy as np
import pandas as pd


def visible_at(observations, cutoff):
    """Return only revisions visible at cutoff; latest visible revision wins per stable id."""
    cutoff = pd.Timestamp(cutoff)
    frame = observations.copy()
    frame['available_at'] = pd.to_datetime(frame['available_at'], utc=True, errors='coerce')
    frame['revision_at'] = pd.to_datetime(frame['revision_at'], utc=True, errors='coerce')
    frame = frame[frame.available_at.le(cutoff.tz_localize('UTC') if cutoff.tz is None else cutoff)]
    frame = frame.sort_values(['observation_id', 'revision_at']).drop_duplicates('observation_id', keep='last')
    return frame


def calibrate_residual_interval(calibration, nominal=.8):
    """Use only calibration rows; returns symmetric absolute-residual radius."""
    if calibration.empty:
        raise ValueError('EMPTY_CALIBRATION_SPLIT')
    residual = (calibration['actual'] - calibration['prediction']).abs().to_numpy(float)
    if not np.isfinite(residual).all():
        raise ValueError('NONFINITE_CALIBRATION_RESIDUAL')
    quantile = float(np.ceil((len(residual) + 1) * nominal) / len(residual))
    radius = float(np.quantile(residual, min(1.0, quantile), method='higher'))
    return {'nominal': nominal, 'rows': len(residual), 'radius': radius,
            'method': 'absolute_residual_higher_quantile',
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
