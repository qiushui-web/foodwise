"""Verify exact replay of the entity/interval experiment and save test logs."""
from pathlib import Path
import hashlib
import json
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[2]


def main():
    first, replay = sorted((ROOT/'modeling/data/03_output').glob('entity_interval_*'))[-2:]
    files = ['internal_predictions.csv', 'window_metrics.csv', 'interval_metrics.csv',
             'interval_predictions.csv', 'old_test_exploratory_predictions.csv',
             'split_manifest.csv', 'calibration.json', 'tree_counts.json', 'final_l1.txt', 'final_l2.txt']
    matches = {name: hashlib.sha256((first/name).read_bytes()).hexdigest() ==
                     hashlib.sha256((replay/name).read_bytes()).hexdigest() for name in files}
    tests = subprocess.run([sys.executable, '-m', 'unittest', 'discover', '-s', 'modeling/tests', '-v'],
                           cwd=ROOT, capture_output=True, text=True)
    (replay/'test_log.txt').write_text(tests.stdout+tests.stderr, encoding='utf-8')
    report = dict(first_run=first.name, replay_run=replay.name, byte_identical=matches,
                  tests_exit_code=tests.returncode, limitation='Same-machine replay; not independent predictive confirmation')
    (replay/'reproduction_verification.json').write_text(json.dumps(report, indent=2), encoding='utf-8')
    print(json.dumps(report, indent=2))
    if tests.returncode or not all(matches.values()):
        raise SystemExit(1)


if __name__ == '__main__':
    main()
