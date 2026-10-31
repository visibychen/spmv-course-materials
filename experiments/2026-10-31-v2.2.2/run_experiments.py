#!/usr/bin/env python3
"""Frozen archive builds; sequential resumable experiments after source push."""
import csv,hashlib,io,json,os,random,re,statistics,subprocess,sys,tarfile,time
from pathlib import Path
import numpy as np
HERE=Path(__file__).resolve().parent
MATERIALS=HERE.parents[1];CORE=MATERIALS.parent/'csrspmv'
OLD=MATERIALS/'experiments/2026-10-30-v2.2.1'
COMMITS={'original':'9352c865044f4c8b344d6fe5a277200a89f7a08b',
 'v2':'9b652e8da85b7a1ad255e0b4f8ddadc5e0558f1a',
 'v22':'10f6b89ef7829e66ee83cdacd38953ba7ad7497b',
 'v222':subprocess.check_output(['git','rev-parse','optimization/v2.2.2'],cwd=CORE,text=True).strip()}
FLAGS='-O3 -march=native -g -Wall -iquote src -fopenmp'
VARIANTS={'original':('original',[]),'v2':('v2',['--kernel=v2']),
 'v22':('v22',['--kernel=v2.2']),'v222':('v222',['--kernel=v2.2.2']),
 'v222-parent':('v222',['--kernel=v2.2.2','--v222-policy=v22']),
 'v222-v2':('v222',['--kernel=v2.2.2','--v222-policy=v2']),
 'v222-runs-off':('v222',['--kernel=v2.2.2','--v222-runs=off']),
 'v222-runs-on':('v222',['--kernel=v2.2.2','--v222-runs=on']),
 'original-novec':('original-novec',[]),
 'v2-aa-a':('v2',['--kernel=v2']),'v2-aa-b':('v2',['--kernel=v2'])}
FIELDS=['phase','matrix','variant','threads','repeat','sample','pair','order','execute_s','prepare_s','cleanup_s','total_s','wall_s','max_rss_kib','major_faults','actual_threads','selected','partition','route','prepare_threads','reason','extra_bytes','validation_s','policy_s','profile_match','predicted_s','baseline_predicted_s','executor','validation_threads','index_retry','index_capacity','statistics_known','retry_s','active','empty_runs','discarded_index_bytes','retained_run_bytes','command_file']
def save(name,obj): (HERE/name).write_text(json.dumps(obj,ensure_ascii=False,indent=2)+'\n')
def sha(path):
 h=hashlib.sha256()
 with Path(path).open('rb') as f:
  for b in iter(lambda:f.read(4*1024*1024),b''):h.update(b)
 return h.hexdigest()
WAIT_POLICY="PASSIVE"
def env(t):
 e={k:v for k,v in os.environ.items() if not k.startswith(('OMP_','GOMP_'))}
 e.update(OMP_NUM_THREADS=str(t),OMP_DYNAMIC='FALSE',OMP_PLACES='cores',OMP_PROC_BIND='spread',OMP_WAIT_POLICY=WAIT_POLICY,LC_ALL='C');return e
def build():
 result={}
 for name in ['original','v2','v22','v222','original-novec']:
  dest=HERE/'build'/name;dest.mkdir(exist_ok=True)
  commit=COMMITS['original' if name=='original-novec' else name]
  data=subprocess.check_output(['git','archive',commit],cwd=CORE)
  with tarfile.open(fileobj=io.BytesIO(data)) as tf:tf.extractall(dest)
  subprocess.run(['make','clean'],cwd=dest,check=True,capture_output=True)
  flags=FLAGS+(' -fno-tree-loop-vectorize -fno-tree-slp-vectorize' if name=='original-novec' else '')
  cmd=['make','-j12','CFLAGS='+flags+' -fopt-info-vec-all='+str(HERE/f'raw/vectorization-{name}.txt')]
  p=subprocess.run(cmd,cwd=dest,capture_output=True,text=True);(HERE/f'raw/build-{name}.txt').write_text(p.stdout+p.stderr);p.check_returncode()
  result[name]={'commit':commit,'command':cmd,'binary_sha256':sha(dest/'csrspmv'),'flags':flags}
  if name=='v222':
   for symbol in ['spmv_v22_execute','zero_rows','nonempty_rows','spmv_v222_prepare','spmv_v222_execute','spmv_plan_execute']:
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
DONE=None
def measure(phase,n,v,t,R,s,pair='',order=''):
 global DONE
 if DONE is None:DONE={tuple(x[k] for k in FIELDS[:6]) for x in records()}
 key=(phase,n,v,str(t),str(R),str(s))
 if key in DONE:return
 tag=f'{phase}-{n}-{v}-t{t}-r{R}-s{s}';res=HERE/f'raw/{tag}.resource.json';cmd=command(v,n,R)
 full=['/usr/bin/time','-f','{"wall_s":%e,"max_rss_kib":%M,"major_faults":%F}','-o',str(res),*cmd]
 save(f'raw/{tag}.command.json',{'argv':full,'environment':{k:v for k,v in env(t).items() if k.startswith('OMP_')}})
 p=subprocess.run(full,env=env(t),capture_output=True,text=True,timeout=1200)
 (HERE/f'raw/{tag}.stdout.txt').write_text(p.stdout);(HERE/f'raw/{tag}.stderr.txt').write_text(p.stderr);p.check_returncode()
 e=re.search(r'csr_matrix_int32_spmv: ([\d.]+) seconds (\d+) multiplications (\d+) flops',p.stdout);assert e and int(e[2])==R,(tag,p.stdout)
 expected=matrix(n).get('expanded_nonzeros_verified',matrix(n)['nonzeros']);assert int(e[3])==2*expected*R,(tag,e[3],expected)
 prep=re.search(r'spmv_prepare: ([\d.]+).*selected=(\S+) reason=(\S+).*extra_bytes=(\d+)',p.stdout)
 info=re.search(r'spmv_v222: (.*)',p.stdout) or re.search(r'spmv_v22: (.*)',p.stdout) or re.search(r'spmv_v2: (.*)',p.stdout)
 info=dict(re.findall(r'(\w+)=(\S+)',info[1])) if info else {}
 cleanup=re.search(r'spmv_cleanup: ([\d.]+)',p.stdout);team=re.search(r'spmv_team: actual_threads=(\d+)',p.stdout)
 ps=float(prep[1]) if prep else 0;cs=float(cleanup[1]) if cleanup else 0
 row={'phase':phase,'matrix':n,'variant':v,'threads':t,'repeat':R,'sample':s,'pair':pair,'order':order,
  'execute_s':float(e[1]),'prepare_s':ps,'cleanup_s':cs,'total_s':float(e[1])+ps+cs,**json.loads(res.read_text()),
  'actual_threads':int(team[1]) if team else t,'selected':info.get('kernel','original'),'partition':info.get('partition','original'),
  'route':info.get('route','original'),'prepare_threads':info.get('prepare_threads',''),'reason':prep[3] if prep else 'original-source','extra_bytes':int(prep[4]) if prep else 0,
  'validation_s':info.get('validation_s',float(info.get('row_scan_s',0))+float(info.get('column_validation_s',0))),
  'policy_s':info.get('policy_s',0),'profile_match':info.get('profile_match',''),'predicted_s':info.get('predicted_s',''),
  'baseline_predicted_s':info.get('baseline_predicted_s',''),'executor':info.get('executor',prep[2] if prep else v),'validation_threads':info.get('validation_threads',''),'index_retry':info.get('index_retry',''),'index_capacity':info.get('index_capacity',''),'statistics_known':info.get('statistics_known',''),'retry_s':info.get('retry_s',''),'active':info.get('active',''),'empty_runs':info.get('empty_runs',''),'discarded_index_bytes':info.get('discarded_index_bytes',''),'retained_run_bytes':info.get('retained_run_bytes',''),'command_file':f'raw/{tag}.command.json'}
 f=HERE/'measurements.csv';exist=f.exists()
 with f.open('a',newline='') as out:
  w=csv.DictWriter(out,fieldnames=FIELDS,lineterminator='\n')
  if not exist:w.writeheader()
  w.writerow(row)
 DONE.add(key)
 print(tag,f'total={row["total_s"]*1000:.3f}ms P={ps*1000:.3f}',row['selected'],'T='+str(row['actual_threads']),flush=True)
GUARDS=['heldout-two-giants','empty99','heldout-empty-cluster','bcsstk18','giant-row','heavy-clustered','wide']
MISSES=['v22-empty90','v22-empty99']
REGRESSIONS=['random8','new-iid8','random64','new-small','heavy-scattered','heldout-iid8','random1','heldout-small']
CRITICAL=GUARDS+MISSES+REGRESSIONS
VERSIONS=['original','v2','v22','v222']
TARGETS=['v222-block1','v222-block4','v222-block8','v222-block90']
ABLATIONS=['v22-empty90','heldout-empty-cluster','empty99','bcsstk18','heldout-two-giants','random8','v222-block1','v222-block8']
def schedule():
 rng=random.Random(2026103107);jobs=[]
 def paired(phase,conditions,controls,count):
  blocks=[(n,t,R,c,k) for n,t,R in conditions for c in controls for k in range(1,count+1)]
  rng.shuffle(blocks)
  flips={(n,t,R,c):rng.randrange(2) for n,t,R in conditions for c in controls}
  for n,t,R,c,k in blocks:
   vs=[c,'v222'] if (k+flips[(n,t,R,c)])%2 else ['v222',c]
   for rank,v in enumerate(vs):jobs.append(dict(phase=phase,n=n,v=v,t=t,R=R,s=k+100*controls.index(c),pair=f'{phase}-{n}-{t}-{R}-{c}-{k}',order=rank))
 paired('critical',[(n,12,100 if n=='wide' else 9) for n in CRITICAL]+[(n,24,100 if n=='wide' else 9) for n in GUARDS+MISSES],['original','v2','v22'],10)
 paired('targets',[(n,12,9) for n in TARGETS],['original','v2','v22'],10)
 paired('large',[('large',24,9)],['original','v2','v22'],20)
 blocks=list(range(1,13));rng.shuffle(blocks)
 for k in blocks:
  vs=['v2-aa-a','v2-aa-b'] if k%2 else ['v2-aa-b','v2-aa-a']
  for rank,v in enumerate(vs):jobs.append(dict(phase='aa',n='large',v=v,t=24,R=9,s=k,pair=f'aa-{k}',order=rank))
 groups={
 'screen':[(m['name'],v,12,100 if m['name'] in ['zero','cache-small','wide'] else 9) for m in matrices() if m['group']=='development' and m['name'] not in CRITICAL and m['name']!='large' for v in VERSIONS],
 'heldout':[(m['name'],v,t,100 if m['nonzeros']<20000 else 9) for m in matrices() if m['group']=='new-heldout' for t in [12,24] if not(t==12 and m['name'] in TARGETS) for v in VERSIONS],
 'large-sensitivity':[('large',v,t,R) for t,R in [(1,9),(12,9),(24,1),(24,100)] for v in VERSIONS],
 'ablations':[(n,v,12,9) for n in ABLATIONS for v in ['v222-parent','v222-v2','v222-runs-off','v222-runs-on']],
 'waiting':[(n,v,12,9) for n in ['bcsstk18','heldout-two-giants','v222-block1','v222-block8'] for v in VERSIONS],
 'original-best':[(n,'original',1,100 if n=='wide' else 9) for n in CRITICAL],
 'controls':[(n,'original-novec',t,9) for n,t in [('large',24),('random8',12),('new-iid8',12),('v222-block1',12)]]}
 for phase,configs in groups.items():
  count=3 if phase in ['waiting','original-best'] else 5
  for k in range(1,count+1):
   configs=configs.copy();rng.shuffle(configs)
   for n,v,t,R in configs:jobs.append(dict(phase=phase,n=n,v=v,t=t,R=R,s=k,pair='',order=''))
 for t in [2,4,8]:
  for k in range(1,4):jobs.append(dict(phase='large-sensitivity',n='large',v='original',t=t,R=9,s=k,pair='',order=''))
 rng.shuffle(jobs) # Paired blocks must remain adjacent: final order rebuilt below.
 grouped={};singles=[]
 for j in jobs:
  if j['pair']:grouped.setdefault(j['pair'],[]).append(j)
  else:singles.append([j])
 units=[sorted(g,key=lambda j:j['order']) for g in grouped.values()]+singles;rng.shuffle(units)
 return [j for unit in units for j in unit]
def phase(name):
 frozen=json.loads((HERE/'protocol.json').read_text())['jobs']
 for j in frozen:
  if name=='formal' or j['phase']==name:
   global WAIT_POLICY
   WAIT_POLICY='ACTIVE' if j['phase']=='waiting' else 'PASSIVE'
   measure(j['phase'],j['n'],j['v'],j['t'],j['R'],j['s'],j['pair'],j['order'])
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
