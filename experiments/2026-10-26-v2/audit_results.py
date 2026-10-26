#!/usr/bin/env python3
"""Post-benchmark audit. Never run compilation/tests concurrently with timing."""
import ast,collections,json,re,subprocess
from pathlib import Path
import run_experiments as run
H=run.HERE
def main():
    source=json.loads((H/'source-provenance.json').read_text())
    for name,digest in source['source_sha256'].items():assert run.sha(run.CORE/name)==digest,name
    for name,digest in source['formal_harness_sha256'].items():assert run.sha(H/name)==digest,name
    builds=json.loads((H/'build.json').read_text())
    for name,meta in builds.items():assert run.sha(H/f'build/{name}/csrspmv')==meta['binary_sha256']
    for meta in run.matrices():
        assert run.sha(meta['path'])==meta['sha256'],meta['name']
        if 'expected_path' in meta:assert run.sha(meta['expected_path'])==meta['expected_sha256']
    rows=run.records();keys=[tuple(x[k] for k in run.FIELDS[:6]) for x in rows]
    assert len(keys)==len(set(keys))
    counts=dict(collections.Counter(x['phase'] for x in rows))
    assert counts==dict(pilot=180,screen=650,heldout=555,large=180,**{'large-controls':75}),counts
    for x in rows:
        cmdfile=H/x['command_file'];cmd=json.loads(cmdfile.read_text());tag=cmdfile.name.removesuffix('.command.json')
        stdout=(H/f'raw/{tag}.stdout.txt').read_text()
        assert not (H/f'raw/{tag}.stderr.txt').read_text(),tag
        m=re.search(r'csr_matrix_int32_spmv: ([\d.]+) seconds (\d+) multiplications (\d+) flops',stdout)
        assert m and float(m[1])==float(x['execute_s']) and int(m[2])==int(x['repeat']),tag
        meta=run.matrix(x['matrix']);nnz=meta.get('expanded_nonzeros_verified',meta['nonzeros'])
        assert int(m[3])==2*nnz*int(x['repeat']),tag
        assert abs(float(x['total_s'])-sum(float(x[k]) for k in ['execute_s','prepare_s','cleanup_s']))<1e-12,tag
        assert Path(cmd['argv'][5]).exists() and Path(cmd['argv'][6]).exists(),tag
    # Recheck standalone option spelling, counter preflight and strict fallback.
    extra=[]
    options=[['--kernel','v2','--v2-kernel','short8','--partition','work','--execution','serial','--prefetch','128','--serial-threshold','32768','--plan-memory-mib','4'],
             ['--kernel=v2','--v2-kernel=merge','--execution=serial'],
             ['--kernel=v2','--v2-kernel=merge','--plan-memory-mib=0','--execution=parallel'],
             ['--kernel=v2','--repeat=1','--flops=12287']]
    for i,opts in enumerate(options):
        cmd=run.command('v2-auto','cache-small',1)+opts
        p=subprocess.run(cmd,env=run.env(12),capture_output=True,text=True,timeout=15);p.check_returncode()
        if i==3:assert '3 multiplications 12288 flops' in p.stdout
        extra.append(dict(command=cmd,stdout=p.stdout,exit=p.returncode))
    for opts in [['--flops=9223372036854775807'],['--kernel=v2','--v2-kernel=merge','--strict-order']]:
        cmd=run.command('v2-auto','cache-small',1)+opts
        p=subprocess.run(cmd,env=run.env(12),capture_output=True,text=True,timeout=15)
        assert p.returncode!=0;extra.append(dict(command=cmd,stdout=p.stdout,stderr=p.stderr,exit=p.returncode))
    # 64-bit coordinate search is checked on logical offsets, not fake reads
    # from unavailable multi-gigabyte value/index arrays.
    b=H/'build/v2';exe=H/'build/check-64bit'
    cmd=['gcc','-O2','-Wall','-fopenmp','-iquote',str(b/'src'),str(H/'check_64bit.c'),
      *[str(b/'src'/n) for n in ['spmv_plan.o','spmv_v2.o','csr.o','vector.o','matrix_market.o','parse.o']],'-o',str(exe)]
    p=subprocess.run(cmd,capture_output=True,text=True);p.check_returncode();assert not p.stderr
    p=subprocess.run([str(exe)],capture_output=True,text=True,check=True)
    wide=dict(command=cmd,stdout=p.stdout,exit=p.returncode,binary_sha256=run.sha(exe))
    run.save('64bit-check.json',wide);run.save('supplementary-cli-checks.json',extra)
    for p in H.glob('*.py'):ast.parse(p.read_text(),filename=str(p))
    checked_links=0
    for p in list(H.glob('*.md'))+list((run.CORE/'docs').glob('*.md')):
        for target in re.findall(r'\]\(([^)]+)\)',p.read_text()):
            if target.startswith(('http:','https:','#')):continue
            assert (p.parent/target.split('#')[0]).exists(),(p,target)
            checked_links+=1
    for repo in [run.CORE,run.MATERIALS]:subprocess.run(['git','diff','--check'],cwd=repo,check=True)
    assert subprocess.run(['git','merge-base','--is-ancestor',run.V1,'HEAD'],cwd=run.CORE).returncode==1
    assert subprocess.check_output(['git','merge-base','HEAD','master'],cwd=run.CORE,text=True).strip()==run.ORIGINAL
    run.save('audit.json',dict(status='passed',counts=counts,total_processes=len(rows),
       source_and_binary_hashes_match=True,input_hashes_match=True,raw_and_flop_counts_match=True,
       duplicates=0,local_links_checked=checked_links,v1_not_ancestor_of_v2=True,base_is_original_master=True,
       extra_cli_checks=len(extra),wide_index_check=wide['stdout'],
       biggest_tracked_candidate_bytes=max(p.stat().st_size for p in H.rglob('*') if p.is_file() and not any(d in p.relative_to(H).parts for d in ['build','data','__pycache__'])),
       no_slow_samples_removed=True))
    print('AUDIT PASS:',len(rows),'process records;',wide['stdout'].strip())
if __name__=='__main__':main()
