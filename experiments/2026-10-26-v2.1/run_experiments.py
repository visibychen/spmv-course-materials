#!/usr/bin/env python3
"""Frozen archive builds; sequential resumable experiments after source push."""
import csv,hashlib,io,json,os,random,re,statistics,subprocess,sys,tarfile,time
from pathlib import Path
import numpy as np
HERE=Path(__file__).resolve().parent
MATERIALS=HERE.parents[1];CORE=MATERIALS.parent/'csrspmv'
OLD=MATERIALS/'experiments/2026-10-26-v2'
COMMITS={'original':'9352c865044f4c8b344d6fe5a277200a89f7a08b',
 'v2':'9b652e8da85b7a1ad255e0b4f8ddadc5e0558f1a',
 'v21':'aa1ef3d9bfb93002f19d0bfffdb3074225bb7f15',
 'v1':'f089579a489723547a354459d591c551a313c4bb'}
FLAGS='-O3 -march=native -g -Wall -iquote src -fopenmp'
VARIANTS={'original':('original',[]),'v2':('v2',['--kernel=v2']),
 'v21':('v21',['--kernel=v2.1','--v21-profile='+str(HERE/'profile.txt')]),
 'v21-original':('v21',['--kernel=v2.1','--v21-kernel=original']),
 'v21-csr':('v21',['--kernel=v2.1','--v21-kernel=csr','--partition=rows','--execution=parallel']),
 'v21-short8':('v21',['--kernel=v2.1','--v21-kernel=short8','--partition=rows','--execution=parallel']),
 'v21-long':('v21',['--kernel=v2.1','--v21-kernel=long','--partition=rows','--execution=parallel']),
 'v21-work':('v21',['--kernel=v2.1','--v21-kernel=csr','--partition=work','--execution=parallel']),
 'v21-serial':('v21',['--kernel=v2.1','--v21-kernel=csr','--execution=serial']),
 'v21-merge':('v21',['--kernel=v2.1','--v21-kernel=merge','--execution=parallel']),
 'v21-no-cache':('v21',['--kernel=v2.1','--v21-kernel=merge','--execution=parallel','--v21-cache=0']),
 'v21-serial-fixup':('v21',['--kernel=v2.1','--v21-kernel=merge','--execution=parallel','--v21-fixup=serial']),
 'v21-prep-serial':('v21',['--kernel=v2.1','--v21-profile='+str(HERE/'profile.txt'),'--v21-prepare=serial']),
 'v21-prep-parallel':('v21',['--kernel=v2.1','--v21-profile='+str(HERE/'profile.txt'),'--v21-prepare=parallel']),
 'v1-pack':('v1',['--kernel=csr-pack']),
 'original-novec':('original-novec',[])}
FIELDS=['phase','matrix','variant','threads','repeat','sample','pair','order','execute_s','prepare_s','cleanup_s','total_s','wall_s','max_rss_kib','major_faults','actual_threads','selected','partition','prepare_threads','reason','extra_bytes','validation_s','policy_s','profile_match','predicted_s','baseline_predicted_s','command_file']
def save(name,obj): (HERE/name).write_text(json.dumps(obj,ensure_ascii=False,indent=2)+'\n')
def sha(path):
 h=hashlib.sha256()
 with Path(path).open('rb') as f:
  for b in iter(lambda:f.read(4*1024*1024),b''):h.update(b)
 return h.hexdigest()
def env(t):
 e={k:v for k,v in os.environ.items() if not k.startswith(('OMP_','GOMP_'))}
 e.update(OMP_NUM_THREADS=str(t),OMP_DYNAMIC='FALSE',OMP_PLACES='cores',OMP_PROC_BIND='spread',OMP_WAIT_POLICY='PASSIVE',LC_ALL='C');return e
def build():
 result={}
 for name in ['original','v2','v21','v1','original-novec']:
  dest=HERE/'build'/name;dest.mkdir(exist_ok=True)
  commit=COMMITS['original' if name=='original-novec' else name]
  data=subprocess.check_output(['git','archive',commit],cwd=CORE)
  with tarfile.open(fileobj=io.BytesIO(data)) as tf:tf.extractall(dest)
  subprocess.run(['make','clean'],cwd=dest,check=True,capture_output=True)
  flags=FLAGS+(' -fno-tree-loop-vectorize -fno-tree-slp-vectorize' if name=='original-novec' else '')
  cmd=['make','-j12','CFLAGS='+flags+' -fopt-info-vec-all='+str(HERE/f'raw/vectorization-{name}.txt')]
  p=subprocess.run(cmd,cwd=dest,capture_output=True,text=True);(HERE/f'raw/build-{name}.txt').write_text(p.stdout+p.stderr);p.check_returncode()
  result[name]={'commit':commit,'command':cmd,'binary_sha256':sha(dest/'csrspmv'),'flags':flags}
  if name=='v21':
   for symbol in ['row_kernel','packed_sum','merge_kernel']:
    p=subprocess.run(['objdump','-d','-M','intel','--disassemble='+symbol,str(dest/'csrspmv')],capture_output=True,text=True,check=True)
    (HERE/f'raw/assembly-{symbol}.txt').write_text(p.stdout)
  print('BUILD',name,flush=True)
 save('build.json',result)
 er={}
 for cmd in [['lscpu'],['uname','-a'],['gcc','--version'],['free','-b']]:er[' '.join(cmd)]=subprocess.check_output(cmd,text=True)
 er['environment']={k:v for k,v in env(24).items() if k.startswith('OMP_')};er['unix_start']=time.time();save('environment.json',er)
def matrices():return json.loads((HERE/'matrices.json').read_text())
def matrix(n):return next(x for x in matrices() if x['name']==n)
def command(variant,n,R,out=None):
 folder,opts=VARIANTS[variant];m=matrix(n)
 cmd=[str(HERE/'build'/folder/'csrspmv'),m['path'],*opts,'--matrix-format=f32','--source-vector-format=f32','--destination-vector-format=f32','--repeat='+str(R),'-v']
 if m.get('expand_symmetric'):cmd+=['--include-symmetric-part']
 if out:cmd+=['--destination-vector='+str(out),'--destination-vector-prec=9']
 return cmd
def records():return list(csv.DictReader((HERE/'measurements.csv').open())) if (HERE/'measurements.csv').exists() else []
def measure(phase,n,v,t,R,s,pair='',order=''):
 key=(phase,n,v,str(t),str(R),str(s))
 if any(tuple(x[k] for k in FIELDS[:6])==key for x in records()):return
 tag=f'{phase}-{n}-{v}-t{t}-r{R}-s{s}';res=HERE/f'raw/{tag}.resource.json';cmd=command(v,n,R)
 full=['/usr/bin/time','-f','{"wall_s":%e,"max_rss_kib":%M,"major_faults":%F}','-o',str(res),*cmd]
 save(f'raw/{tag}.command.json',{'argv':full,'environment':{k:v for k,v in env(t).items() if k.startswith('OMP_')}})
 p=subprocess.run(full,env=env(t),capture_output=True,text=True,timeout=1200)
 (HERE/f'raw/{tag}.stdout.txt').write_text(p.stdout);(HERE/f'raw/{tag}.stderr.txt').write_text(p.stderr);p.check_returncode()
 e=re.search(r'csr_matrix_int32_spmv: ([\d.]+) seconds (\d+) multiplications (\d+) flops',p.stdout);assert e and int(e[2])==R,(tag,p.stdout)
 expected=matrix(n).get('expanded_nonzeros_verified',matrix(n)['nonzeros']);assert int(e[3])==2*expected*R,(tag,e[3],expected)
 prep=re.search(r'spmv_prepare: ([\d.]+).*selected=(\S+) reason=(\S+).*extra_bytes=(\d+)',p.stdout)
 info=re.search(r'spmv_v21: (.*)',p.stdout) or re.search(r'spmv_v2: (.*)',p.stdout)
 info=dict(re.findall(r'(\w+)=(\S+)',info[1])) if info else {}
 cleanup=re.search(r'spmv_cleanup: ([\d.]+)',p.stdout);team=re.search(r'spmv_team: actual_threads=(\d+)',p.stdout)
 ps=float(prep[1]) if prep else 0;cs=float(cleanup[1]) if cleanup else 0
 row={'phase':phase,'matrix':n,'variant':v,'threads':t,'repeat':R,'sample':s,'pair':pair,'order':order,
  'execute_s':float(e[1]),'prepare_s':ps,'cleanup_s':cs,'total_s':float(e[1])+ps+cs,**json.loads(res.read_text()),
  'actual_threads':int(team[1]) if team else t,'selected':info.get('kernel','original'),'partition':info.get('partition','original'),
  'prepare_threads':info.get('prepare_threads',''),'reason':prep[3] if prep else 'original-source','extra_bytes':int(prep[4]) if prep else 0,
  'validation_s':info.get('validation_s',float(info.get('row_scan_s',0))+float(info.get('column_validation_s',0))),
  'policy_s':info.get('policy_s',0),'profile_match':info.get('profile_match',''),'predicted_s':info.get('predicted_s',''),
  'baseline_predicted_s':info.get('baseline_predicted_s',''),'command_file':f'raw/{tag}.command.json'}
 f=HERE/'measurements.csv';exist=f.exists()
 with f.open('a',newline='') as out:
  w=csv.DictWriter(out,fieldnames=FIELDS,lineterminator='\n')
  if not exist:w.writeheader()
  w.writerow(row)
 print(tag,f'total={row["total_s"]*1000:.3f}ms P={ps*1000:.3f}',row['selected'],'T='+str(row['actual_threads']),flush=True)
CRITICAL=['heldout-two-giants','empty99','heldout-empty-cluster','bcsstk18','giant-row','heavy-clustered']
def phase(name):
 rng=random.Random(20262100+sum(map(ord,name)))
 if name in ['critical','large']:
  conditions=[(n,t,9) for n in CRITICAL for t in [12,24]] if name=='critical' else [('large',t,9) for t in [12,24]]
  for sample in range(1,11):
   rng.shuffle(conditions)
   for n,t,R in conditions:
    controls=['original','v2'];rng.shuffle(controls)
    for control in controls:
     order=[control,'v21'];rng.shuffle(order);pid=f'{n}-{t}-{R}-{control}-{sample}'
     for rank,v in enumerate(order):
      # Keep both v21 samples in each condition: sample IDs must be unique.
      sid=sample if control=='original' else sample+10
      measure(name,n,v,t,R,sid,pid,rank)
  summarize();return
 if name=='screen':
  jobs=[(m['name'],v,12,100 if m['name'] in ['zero','cache-small','wide'] else 9) for m in matrices() if m['group']=='development' and m['name'] not in CRITICAL and m['name']!='large' for v in ['original','v2','v21']]
 elif name=='heldout':jobs=[(m['name'],v,t,100 if m['nonzeros']<20000 else 9) for m in matrices() if m['group'] in ['new-heldout','new-real'] for t in [12,24] for v in ['original','v2','v21']]
 elif name=='large-sensitivity':
  jobs=[('large',v,t,R) for t,R in [(1,9),(24,1),(24,100)] for v in ['original','v2','v21']]
  jobs+=[('large','original',t,9) for t in [2,4,8]]
 elif name=='ablations':
  jobs=[(n,v,12,9) for n in ['heldout-two-giants','giant-row','empty99','bcsstk18','banded8','heavy-clustered'] for v in ['v21-csr','v21-work','v21-long','v21-serial','v21-prep-serial','v21-prep-parallel']]
  jobs += [(n,v,12,9) for n in ['heldout-two-giants','giant-row'] for v in ['v21-merge','v21-no-cache','v21-serial-fixup','v1-pack']]
  jobs += [('large',v,24,9) for v in ['v21-csr','v21-short8','v21-original','original-novec']]
 else:raise ValueError(name)
 for sample in range(1,6):
  rng.shuffle(jobs)
  for n,v,t,R in jobs:measure(name,n,v,t,R,sample)
 summarize()
def summarize():
 g={}
 for r in records():g.setdefault(tuple(r[k] for k in FIELDS[:5]),[]).append(r)
 result=[]
 for key,rows in sorted(g.items()):
  item=dict(zip(FIELDS[:5],key));item['samples']=len(rows)
  for k in ['execute_s','prepare_s','cleanup_s','total_s','wall_s']:
   vals=[float(x[k]) for x in rows];item[k+'_median']=statistics.median(vals)
   if k=='total_s':item['total_s_min']=min(vals);item['total_s_max']=max(vals)
  for k in ['selected','partition','actual_threads','prepare_threads','reason']:item[k]=','.join(sorted({r[k] for r in rows}))
  item['extra_bytes']=max(int(r['extra_bytes']) for r in rows);item['max_rss_kib']=max(int(r['max_rss_kib']) for r in rows)
  result.append(item)
 save('summary.json',result)
 if result:
  with (HERE/'summary.csv').open('w',newline='') as out:
   w=csv.DictWriter(out,fieldnames=list(result[0]),lineterminator='\n');w.writeheader();w.writerows(result)
 print('SUMMARY',len(result),'conditions',len(records()),'processes',flush=True)
if __name__=='__main__':
 stage=sys.argv[1]
 if stage in ['build','summarize']:globals()[stage]()
 elif stage in ['inputs','verify']:
  from verify_and_inputs import inputs,verify
  globals()[stage]()
 else:phase(stage)
