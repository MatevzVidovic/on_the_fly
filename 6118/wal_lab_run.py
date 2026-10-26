"""Optional launcher; each experiment also runs independently."""
from pathlib import Path
import subprocess
import sys

if '--output' in sys.argv:
    raise SystemExit('Use --output with an individual experiment; each needs its own directory.')
for variant in ('full', 'unlogged_full', 'batched', 'unlogged_batched'):
    subprocess.run([sys.executable, str(Path(__file__).with_name('wal_lab_' + variant + '.py')),
                    *sys.argv[1:]], check=True)
