#!/usr/bin/env python3
"""Read-only schema, fingerprints, deterministic compilation and actual JS checks."""
import sys
sys.dont_write_bytecode=True
import importlib.util,json,subprocess
from pathlib import Path
BASE=Path(__file__).resolve().parents[1]
spec=importlib.util.spec_from_file_location('candidate_compiler',BASE/'compiler/compile.py');compiler=importlib.util.module_from_spec(spec);spec.loader.exec_module(compiler)
docs,reuse=compiler.load();proof=json.loads((BASE/'execution/runtime-verification.json').read_text());program_proof=json.loads((BASE/'execution/program-verification.json').read_text());artifacts,counts=compiler.build(docs,reuse,proof,program_proof)
for name,text in artifacts.items():compiler.require((BASE/'execution/generated'/name).read_text()==text,'generated drift: '+name)
# True unresolved rules and ordinary target/implementation inputs remain separate.
compiler.require({r['parameter'] for d in docs for r in d['unresolvedRules']}=={'U01','U02','U03','U04'},'unresolved scope')
spells=[d for d in docs if d['identity']['category']=='spell']
compiler.require(len(spells)==127,'new spell count')
for d in spells:
 u=d['definition']['authoringOnly']['units'][0]
 compiler.require(bool(u['learning']['prices']),'spell learning price missing: '+d['identity']['name'])
 compiler.require(bool(u['costs']['value']),'spell known cost missing: '+d['identity']['name'])
 compiler.require(bool(u['duration']['value']),'spell known duration missing: '+d['identity']['name'])
 compiler.require(d['identity']['grade'] in ['ungraded','B','A','S'],'spell grade')
 compiler.require('"state": "attributes.智力"' not in json.dumps(u['target'],ensure_ascii=False),'base attribute substituted for effective range')
for name in ['_initialize.py','_passive_init.py']:compiler.require(not (BASE/'compiler'/name).exists(),'temporary rule initializer remains')
# Tests are read-only and return evidence to stdout; they never modify a registry or save.
r=subprocess.run(['node',str(BASE/'compiler/runtime-check.mjs')],capture_output=True,text=True,check=True);actual=json.loads(r.stdout)
compiler.require(actual==proof,'runtime proof is stale or differs from actual tests')
s=subprocess.run([sys.executable,str(BASE/'compiler/semantic-check.py')],capture_output=True,text=True,check=True);semantics=json.loads(s.stdout)
m=subprocess.run(['node',str(BASE/'compiler/module-check.mjs')],capture_output=True,text=True,check=True);modules=json.loads(m.stdout)
p=subprocess.run([sys.executable,str(BASE/'compiler/check-programs.py')],capture_output=True,text=True,check=True);actual_programs=json.loads(p.stdout)
compiler.require(actual_programs==program_proof,'program proof is stale or differs from actual execution')
# Deterministic second build uses the same contracts and produces exactly the same artifacts.
again,_=compiler.build(docs,reuse,proof,program_proof);compiler.require(again==artifacts,'non-deterministic compiler')
print(json.dumps({'result':'PASS','schema':'901-resource/1','counts':counts,'jsAssertions':actual['assertionCount'],'programExecutionTests':actual_programs['testCount'],'semanticRegression':semantics,'esm':modules,'writes':0},ensure_ascii=False))
