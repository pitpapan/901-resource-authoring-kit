#!/usr/bin/env python3
"""Read-only actual program tests; emits a reproducible proof, never writes it."""
import sys
sys.dont_write_bytecode=True
import importlib.util,json,re,subprocess
from pathlib import Path
BASE=Path(__file__).resolve().parents[1]
spec=importlib.util.spec_from_file_location('candidate_compiler',BASE/'compiler/compile.py');compiler=importlib.util.module_from_spec(spec);spec.loader.exec_module(compiler)
docs,_=compiler.load();result={'result':'passed','engineModules':[],'programs':{},'testCount':0,'writes':0};checked={};modules={}
for d in docs:
 for scope in d['definition']['authoringOnly'].get('runtimePrograms',[]):
  relative=scope['testFile'];path=compiler.ROOT/relative
  if relative not in checked:
   command=['node','--test','--test-isolation=none','--test-reporter=tap',str(path.resolve())]
   r=subprocess.run(command,text=True,capture_output=True,check=True)
   counts={k:int(re.search(r'^# '+k+r' (\d+)$',r.stdout,re.M)[1]) for k in ['tests','pass','fail']}
   compiler.require(counts['tests']>0 and counts['pass']==counts['tests'] and counts['fail']==0,'program cases did not pass')
   cases=re.findall(r'^# Subtest: (.+)$',r.stdout,re.M);compiler.require(len(cases)==counts['tests'],'actual test case count differs')
   checked[relative]=cases;result['testCount']+=counts['tests']
  key=d['id']+'/'+scope['operation'];result['programs'][key]={'result':'passed','fingerprint':compiler.program_fingerprint(d,scope['operation']),'testCases':checked[relative],'testFile':relative}
  for module in scope['engineModules']:modules[module]=compiler.sha(compiler.ROOT/module)
result['engineModules']=[{'path':p,'sha256':h} for p,h in sorted(modules.items())]
print(json.dumps(result,ensure_ascii=False,sort_keys=True,indent=2))
