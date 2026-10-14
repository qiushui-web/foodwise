"""Current verification entry. Never runs historical source-patching tools."""
from pathlib import Path
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[2]

def main():
    commands = [
        [sys.executable, '-m', 'unittest', 'discover', '-s', 'modeling/tests'],
        [sys.executable, 'modeling/scripts/15_feature_contract_check.py'],
    ]
    if '--experiment' in sys.argv:
        commands.append([sys.executable, 'modeling/scripts/14_public_sales_validation.py'])
    for command in commands:
        subprocess.run(command, cwd=ROOT, check=True)
    print('Current verification passed. Java parity requires gradlew test; public report publication is separate.')

if __name__ == '__main__':
    main()
