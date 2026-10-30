#!/usr/bin/env python3
"""One-time freeze immediately before the first formal process."""
import json,subprocess,time
import run_experiments as r
def main():
 assert not (r.HERE/'measurements.csv').exists()
 assert len(r.matrices())==80
 assert len(json.loads((r.HERE/'correctness.json').read_text()))==489
 assert subprocess.check_output(['git','rev-parse','origin/optimization/v2.2.1'],cwd=r.CORE,text=True).strip()==r.COMMITS['v221']
 assert not subprocess.check_output(['git','status','--porcelain'],cwd=r.CORE,text=True)
 names=['run_experiments.py','verify_and_inputs.py','protocol.json','matrices.json','build.json']
 r.save('frozen-harness.json',dict(before_first_formal_unix=time.time(),client_date='2026-10-30 Asia/Shanghai',files={n:r.sha(r.HERE/n) for n in names},core=r.COMMITS['v221'],default='serial validation, calibrated before source push'))
 print('Frozen source/binaries/harness/input metadata before formal timing')
if __name__=='__main__':main()
