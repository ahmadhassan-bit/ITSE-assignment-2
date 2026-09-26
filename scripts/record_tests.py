"""Capture real unittest output, command, UTC time and exit status."""
from datetime import datetime, timezone
from pathlib import Path
import subprocess
import sys

target = Path(sys.argv[1])
arguments = sys.argv[2:] or ["discover", "-s", "tests", "-v"]
command = [sys.executable, "-m", "unittest", *arguments]
started = datetime.now(timezone.utc).isoformat()
run = subprocess.run(command, capture_output=True, text=True)
target.parent.mkdir(parents=True, exist_ok=True)
target.write_text(f"UTC start: {started}\nCommand: python -m unittest {' '.join(arguments)}\n"
                  f"Exit code: {run.returncode}\n\n{run.stdout}{run.stderr}", encoding="utf-8")
print(target.read_text())
sys.exit(run.returncode)

