#!/usr/bin/env python3
"""Read-only registered-offer acquisition tests; outputs evidence, never writes it."""
import sys
sys.dont_write_bytecode=True
import importlib.util,json,re,subprocess
from pathlib import Path
BASE=Path(__file__).resolve().parents[1]
spec=importlib.util.spec_from_file_location('candidate_compiler',BASE/'compiler/compile.py');compiler=importlib.util.module_from_spec(spec);spec.loader.exec_module(compiler)
docs,_=compiler.load();result={'result':'passed','engineModules':[],'acquisitions':{},'testCount':0,'writes':0};checked={};modules={}
for d in docs:
 scope=d['definition']['authoringOnly'].get('runtimeAcquisition')
 if not scope:continue
 cases=[]
 for relative in scope['testFiles']:
  if relative not in checked:
   command=['node','--test','--test-isolation=none','--test-reporter=tap',str((compiler.ROOT/relative).resolve())]
   r=subprocess.run(command,text=True,capture_output=True,check=True)
   counts={k:int(re.search(r'^# '+k+r' (\d+)$',r.stdout,re.M)[1]) for k in ['tests','pass','fail']}
   compiler.require(counts['tests']>0 and counts['pass']==counts['tests'] and counts['fail']==0,'acquisition cases did not pass')
   checked[relative]=re.findall(r'^# Subtest: (.+)$',r.stdout,re.M)
   compiler.require(len(checked[relative])==counts['tests'],'actual acquisition test count differs');result['testCount']+=counts['tests']
  cases.extend(checked[relative])
 result['acquisitions'][d['id']]={'result':'passed','fingerprint':compiler.acquisition_fingerprint(d),'testCases':cases,'testFiles':scope['testFiles']}
 for module in scope['engineModules']:modules[module]=compiler.sha(compiler.ROOT/module)
result['engineModules']=[{'path':p,'sha256':h} for p,h in sorted(modules.items())]
print(json.dumps(result,ensure_ascii=False,sort_keys=True,indent=2))
