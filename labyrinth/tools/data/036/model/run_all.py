#!/usr/bin/env python3
"""Q0 계약 다시 만들기: 청사진 시안 → 콘텐츠 시제품 → 경제 → 계약 JSON → 검사.

  python3 -B tools/data/036/model/run_all.py [--skip-layout]
"""
import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
steps = ['layout6.py', 'proto036.py', 'economy.py', 'build_contract.py']
if '--skip-layout' in sys.argv and (HERE / 'out/layout.json').exists():
    steps = steps[1:]
for s in steps:
    print(f'── {s}', flush=True)
    r = subprocess.run([sys.executable, '-B', str(HERE / s)], cwd=HERE)
    if r.returncode:
        sys.exit(r.returncode)
r = subprocess.run([sys.executable, '-B', str(HERE.parent / 'check_contract.py')], cwd=HERE.parent)
sys.exit(r.returncode)
