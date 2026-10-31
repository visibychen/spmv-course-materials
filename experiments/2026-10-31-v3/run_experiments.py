#!/usr/bin/env python3
"""One frozen schedule, sequential and resumable. No inference or tuning."""
import collections,csv,itertools,json,random,re,subprocess
import common as c
H=c.H
VERSIONS=['original','v2','v3']
GUARDS=['heldout-two-giants','empty99','heldout-empty-cluster','bcsstk18','giant-row','heavy-clustered','wide']
FIELDS=['phase','matrix','variant','threads','repeat','sample','block','order','mode','prepare_s','execute_s','cleanup_s','total_s','wall_s','max_rss_kib','major_faults','actual_threads','flops','backend','simd','command_file']
def matrices():return json.loads((H/'matrices.json').read_text())
def matrix(n):return next(x for x in matrices() if x['name']==n)
def reps(m):return 100 if m['name'] in ['zero','cache-small','wide'] or (m['group']=='new-heldout' and m['nonzeros']<20000) else 9
def schedule():
 rng=random.Random(2026103151);units=[]
 def triples(phase,conditions,count,mode='fixture'):
  perms=list(itertools.permutations(VERSIONS));base=perms*(count//6)
  if count%6==2:base+=[('original','v2','v3'),('v3','original','v2')]
  elif count%6:base+=rng.sample(perms,count%6)
  for n,t,R in conditions:
   orders=base.copy();rng.shuffle(orders)
   for k,order in enumerate(orders,1):
    units.append([dict(phase=phase,n=n,v=v,t=t,R=R,s=k,block=f'{phase}-{n}-{t}-{R}-{k}',order=rank,mode=mode) for rank,v in enumerate(order)])
 triples('main',[('large',24,9)],20)
 triples('critical',[(n,t,reps(matrix(n))) for n in GUARDS for t in [12,24]],8)
 triples('cli',[('large',24,9)],5,'cli')
 for phase,control,count in [('aa','aa-a',12),('mechanism','v3-csr',10),('cross12','original',10)]:
  for k in range(1,count+1):
   vs=[control,'aa-b' if phase=='aa' else 'v3'];vs=vs if k%2 else vs[::-1]
   units.append([dict(phase=phase,n='large',v=v,t=12 if phase=='cross12' and v=='original' else 24,R=9,s=k,block=f'{phase}-{k}',order=rank,mode='fixture') for rank,v in enumerate(vs)])
 groups={
  'screen':[(m['name'],v,12,reps(m)) for m in matrices() if m['group']=='development' and m['name'] not in GUARDS+['large'] for v in VERSIONS],
  'heldout':[(m['name'],v,t,reps(m)) for m in matrices() if m['group']=='new-heldout' for t in [12,24] for v in VERSIONS],
  'sensitivity':[('large',v,t,R) for t,R in [(1,9),(12,9),(24,1),(24,100)] for v in VERSIONS],
  'ablations':[(n,v,t,9) for n,t in [('large',24),('random8',12),('v3-ragged78',12),('v3-short4',12),('heavy-clustered',12),('giant-row',12)] for v in ['v3-tile','v3-pipeline','v3-csr','v3-rows']],
  'waiting':[(n,v,12,9) for n in ['random8','bcsstk18','v3-short4','v3-u8-wide'] for v in VERSIONS],
  'original-best':[(n,'original',1,reps(matrix(n))) for n in GUARDS]}
 for phase,configs in groups.items():
  count=5 if phase=='sensitivity' else 3
  for k in range(1,count+1):
   for n,v,t,R in configs:units.append([dict(phase=phase,n=n,v=v,t=t,R=R,s=k,block='',order='',mode='fixture')])
 for t in [2,4,8]:
  for k in range(1,4):units.append([dict(phase='sensitivity',n='large',v='original',t=t,R=9,s=k,block='',order='',mode='fixture')])
 rng.shuffle(units)
 return [j for unit in units for j in unit]
def command(j):
 m=matrix(j['n'])
 if j['mode']=='fixture':return [str(H/'build/bench'),'run',m['fixture_path'],str(c.VARIANTS[j['v']]),str(j['R'])]
 exe=H/'build'/j['v']/'csrspmv';opts=[] if j['v']=='original' else ['--kernel='+j['v']]
 cmd=[str(exe),m['path'],*opts,'--matrix-format=f32','--source-vector-format=f32','--destination-vector-format=f32','--repeat='+str(j['R']),'-v']
 if m.get('expand_symmetric'):cmd+=['--include-symmetric-part']
 return cmd
def rows():return list(csv.DictReader((H/'measurements.csv').open())) if (H/'measurements.csv').exists() else []
def key(r):return tuple(str(r[k]) for k in FIELDS[:6])
def measure(j,done):
 initial=dict(phase=j['phase'],matrix=j['n'],variant=j['v'],threads=j['t'],repeat=j['R'],sample=j['s'])
 if key(initial) in done:return
 tag=f'{j["phase"]}-{j["n"]}-{j["v"]}-t{j["t"]}-r{j["R"]}-s{j["s"]}';res=H/f'raw/{tag}.resource.json'
 argv=['/usr/bin/time','-f','{"wall_s":%e,"max_rss_kib":%M,"major_faults":%F}','-o',str(res),*command(j)]
 env=c.env(j['t'],'ACTIVE' if j['phase']=='waiting' else 'PASSIVE')
 c.save(f'raw/{tag}.command.json',dict(argv=argv,environment={k:v for k,v in env.items() if k.startswith('OMP_')}))
 p=subprocess.run(argv,env=env,capture_output=True,text=True,timeout=1200)
 (H/f'raw/{tag}.stdout.txt').write_text(p.stdout);(H/f'raw/{tag}.stderr.txt').write_text(p.stderr);p.check_returncode()
 if j['mode']=='fixture':m=json.loads(p.stdout)
 else:
  e=re.search(r'csr_matrix_int32_spmv: ([\d.]+) seconds (\d+) multiplications (\d+) flops',p.stdout);assert e
  prep=re.search(r'spmv_prepare: ([\d.]+)',p.stdout);cleanup=re.search(r'spmv_cleanup: ([\d.]+)',p.stdout);team=re.search(r'spmv_team: actual_threads=(\d+)',p.stdout)
  P=float(prep[1]) if prep else 0;D=float(cleanup[1]) if cleanup else 0
  m=dict(prepare_s=P,execute_s=float(e[1]),cleanup_s=D,total_s=P+float(e[1])+D,repeat=int(e[2]),flops=int(e[3]),actual_threads=int(team[1]) if team else j['t'],backend=j['v'],simd='')
 meta=matrix(j['n']);nnz=meta.get('expanded_nonzeros_verified',meta['nonzeros'])
 assert m['repeat']==j['R'] and m['flops']==2*nnz*j['R']
 assert abs(m['total_s']-sum(m[k] for k in ['prepare_s','execute_s','cleanup_s']))<3e-9
 row=dict(**initial,block=j['block'],order=j['order'],mode=j['mode'],**{k:m[k] for k in ['prepare_s','execute_s','cleanup_s','total_s','actual_threads','flops','backend','simd']},**json.loads(res.read_text()),command_file=f'raw/{tag}.command.json')
 f=H/'measurements.csv';exists=f.exists()
 with f.open('a',newline='') as out:
  w=csv.DictWriter(out,fieldnames=FIELDS,lineterminator='\n')
  if not exists:w.writeheader()
  w.writerow(row)
 done.add(key(row));print(len(done),tag,f'{m["total_s"]*1000:.3f}ms',flush=True)
def run():
 jobs=json.loads((H/'protocol.json').read_text())['jobs'];done={key(r) for r in rows()}
 for j in jobs:measure(j,done)
 print('FORMAL COMPLETE',len(done),flush=True)
if __name__=='__main__':run()
