"""Verify deterministic replay and execute temporal/unit contract tests."""
from pathlib import Path
import hashlib
import json
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[2]


def main():
    runs = sorted((ROOT/'modeling/data/03_output').glob('optimization_*'))
    before, after = runs[-2:]
    names = ['predictions.csv', 'ablation_metrics.csv', 'split_manifest.csv',
             'candidate_model.txt', 'tree_counts.json', 'calibration.json']
    matches = {name: hashlib.sha256((before/name).read_bytes()).hexdigest() ==
                     hashlib.sha256((after/name).read_bytes()).hexdigest() for name in names}
    result = subprocess.run([sys.executable, '-m', 'unittest', 'discover', '-s', 'modeling/tests', '-v'],
                            cwd=ROOT, capture_output=True, text=True)
    (after/'test_log.txt').write_text(result.stdout+result.stderr, encoding='utf-8')
    report = dict(first_run=before.name, replay_run=after.name, byte_identical=matches,
                  test_exit_code=result.returncode, same_machine_replay_only=True,
                  limitations='Not external confirmation, field evidence or cross-platform determinism')
    (after/'reproduction_verification.json').write_text(json.dumps(report, indent=2), encoding='utf-8')
    print(json.dumps(report, indent=2))
    if result.returncode or not all(matches.values()):
        raise SystemExit(1)


if __name__ == '__main__':
    main()
