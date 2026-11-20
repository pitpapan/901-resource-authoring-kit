"""Read-only verification of paired source, deterministic projections and local proof."""
import subprocess,sys
from contracts import *
import compile as compiler
import jsonschema

docs,reuse=compiler.load()
shared=json.loads((BASE/'execution/shared.rule.json').read_text())
jsonschema.validate(shared,json.loads((ROOT/'resources/execution/resource.schema.json').read_text()))
assert sha(ROOT/shared['reading']['path'])==shared['reading']['sha256'],'shared reading changed'
for ref in shared['definition']['authoringOnly']['additionalSources']:
    assert sha(ROOT/ref['path'])==ref['sha256'],'shared price source changed'
proof=json.loads((BASE/'execution/runtime-verification.json').read_text())
actual=json.loads(subprocess.check_output(['node',str(BASE/'compiler/runtime-check.mjs')],text=True))
assert proof==actual,'passive execution proof changed'
acquisition=json.loads((BASE/'execution/acquisition-verification.json').read_text())
actual_acquisition=json.loads(subprocess.check_output([sys.executable,str(BASE/'compiler/check-acquisition.py')],text=True))
assert acquisition==actual_acquisition,'acquisition execution proof changed'
artifacts,counts=compiler.build(docs,reuse,proof,acquisition_evidence=acquisition)
for name,body in artifacts.items():
    assert (BASE/'execution/generated'/name).read_text()==body,'stale projection: '+name
subprocess.run(['node','--test','--test-isolation=none',str(BASE/'compiler/policy-runtime.test.mjs')],check=True,stdout=subprocess.DEVNULL)
subprocess.run(['node','--test','--test-isolation=none',str(BASE/'compiler/semantic-check.test.mjs')],check=True,stdout=subprocess.DEVNULL)
subprocess.run([sys.executable,str(BASE/'_validate.py')],check=True,stdout=subprocess.DEVNULL)
print(json.dumps({'result':'PASS','counts':counts,'passiveTests':proof['testCount'],'policyTests':3,'semanticTests':6,'acquisitionTests':acquisition['testCount'],
    'writes':0,'deployed':False,'limits':['arcane and frost D/C acquisition integrated; fire and higher stages pending','child-technique semantics incomplete','no external model test']},ensure_ascii=False))
