"""Build an immutable local model bundle for startup loading and audit."""
import argparse
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import shutil


def sha256(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def build_bundle(model, features, calibration, output, source_kind):
    output.mkdir(parents=False, exist_ok=False)
    copied = {}
    for source, name in ((model, 'model.txt'), (features, 'features.json')):
        destination = output / name
        shutil.copyfile(source, destination)
        copied[name] = {'sha256': sha256(destination), 'bytes': destination.stat().st_size}
    if calibration:
        destination = output / 'calibration.json'
        shutil.copyfile(calibration, destination)
        copied['calibration.json'] = {'sha256': sha256(destination), 'bytes': destination.stat().st_size}
    manifest = {
        'bundle_version': 'campus-local-v1',
        'created_at_utc': datetime.now(timezone.utc).isoformat(),
        'source_kind': source_kind,
        'load_once_at_startup': True,
        'online_model_overwrite': False,
        'artifacts': copied,
        'limitations': [
            'Bundle packaging does not establish label authenticity or field accuracy.',
            'Calibration is not valid until it is fitted on an independent campus calibration split.',
            'Java feature values and inference parity require a separate acceptance run.'
        ]
    }
    (output / 'manifest.json').write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding='utf-8')
    return manifest


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--model', type=Path, required=True)
    parser.add_argument('--features', type=Path, required=True)
    parser.add_argument('--calibration', type=Path)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--source-kind', default='derived-target-demonstration')
    args = parser.parse_args()
    manifest = build_bundle(args.model, args.features, args.calibration, args.output, args.source_kind)
    print(json.dumps(manifest, ensure_ascii=True))


if __name__ == '__main__':
    main()
