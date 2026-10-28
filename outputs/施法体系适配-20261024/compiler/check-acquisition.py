"""Run the declared acquisition tests and emit proof bound to their local closure."""
import json,re,subprocess
import compile as compiler
from contracts import ROOT,BASE,sha

docs,_=compiler.load()
report={'result':'passed','engineModules':[],'acquisitions':{},'testCount':0,'writes':0}
modules={};checked={}
def closure(path):
    path=path.resolve()
    if path.name in ['resource-data.mjs','resource-catalog.mjs','resource-action-index.mjs'] or path in modules:return
    modules[path]=sha(path)
    for relative in re.findall(r'''(?:from\s*|import\s*)['"]([^'"]+)['"]''',path.read_text(encoding='utf-8')):
        if relative.startswith('.'):closure(path.parent/relative)
for d in docs:
    scope=d['definition']['authoringOnly'].get('runtimeAcquisition')
    if not scope:continue
    cases=[]
    for relative in scope['testFiles']:
        path=ROOT/relative
        if relative not in checked:
            result=subprocess.run(['node','--test','--test-isolation=none','--test-reporter=tap',str(path.resolve())],text=True,capture_output=True)
            if result.returncode:raise RuntimeError(result.stdout+result.stderr)
            counts={k:int(re.search(r'^# '+k+r' (\d+)$',result.stdout,re.M)[1]) for k in ['tests','pass','fail','skipped','cancelled']}
            compiler.require(counts['tests']>0 and counts['pass']==counts['tests'] and not any(counts[k] for k in ['fail','skipped','cancelled']),'incomplete acquisition tests')
            checked[relative]=[name for name in re.findall(r'^\s*# Subtest: (.+)$',result.stdout,re.M) if name!='arcane staged acquisition']
            compiler.require(len(checked[relative])==counts['tests'],'test count differs')
            report['testCount']+=counts['tests'];closure(path)
        cases.extend(checked[relative])
    report['acquisitions'][d['id']]={'result':'passed','fingerprint':compiler.acquisition_fingerprint(d),'testCases':cases,'testFiles':scope['testFiles']}
# Compiler and proof adapter are part of the export boundary, too.
for path in [BASE/'compiler/compile.py',BASE/'compiler/contracts.py',__file__]:
    from pathlib import Path
    path=Path(path).resolve();modules[path]=sha(path)
report['engineModules']=[{'path':__import__('os').path.relpath(p,ROOT).replace('\\','/'),'sha256':h} for p,h in sorted(modules.items())]
print(json.dumps(report,ensure_ascii=False,sort_keys=True,indent=2))
