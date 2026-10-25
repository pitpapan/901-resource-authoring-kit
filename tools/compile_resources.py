"""Validate paired resource contracts and generate runtime data/action indexes.

No inference from prose, no model call, no gameplay-state writes. Unknown rules
and unfinished implementations remain separate in the generated coverage list.
"""
from pathlib import Path
import argparse,hashlib,json,re
ROOT=Path(__file__).resolve().parents[1]
def write_text(p,value):
    p.parent.mkdir(parents=True,exist_ok=True)
    p.write_text(value,encoding='utf-8',newline='\r\n' if p.exists() and b'\r\n' in p.read_bytes() else '\n')
def dump(p,data):
    write_text(p,json.dumps(data,ensure_ascii=False,indent=2)+'\n')
def load_contracts():
    docs=[]
    for p in sorted((ROOT/'resources/execution').glob('*.rule.json')):
        d=json.loads(p.read_text(encoding='utf-8'))
        required=['schemaVersion','id','version','identity','reading','definition','clauses','actions','inputs','unresolvedRules','implementationGaps','verification']
        if any(k not in d for k in required):raise ValueError(f'{p.name}: missing contract fields')
        if d['schemaVersion']!='901-resource/1':raise ValueError(f'{p.name}: unknown schema')
        source=ROOT/d['reading']['path']
        if not source.resolve().is_relative_to(ROOT.resolve()):raise ValueError('Reading source outside kit')
        if hashlib.sha256(source.read_bytes()).hexdigest()!=d['reading']['sha256']:raise ValueError(f'{d["id"]}: 阅读版已变化，须重新核对执行版')
        body=source.read_text(encoding='utf-8')
        if d['reading'].get('heading'):
            heading=d['reading']['heading']
            match=re.search(r'^'+('#'*d['reading'].get('headingDepth',3))+' '+re.escape(heading)+r'\s*$',body,re.M)
            if not match:raise ValueError('Source section not found: '+heading)
            headings={heading}
        else:headings=set(re.findall(r'^### (.+)$',body,re.M))
        covered={c['heading'] for c in d['clauses']}
        if headings!=covered:raise ValueError(f'{d["id"]}: 条款对应不完整 {headings^covered}')
        if d['verification']['runtimeFullyVerified'] and d['unresolvedRules']:raise ValueError('未决规则不能标记全部可执行')
        if d['verification']['runtimeFullyVerified'] and (d['implementationGaps'] or any(c['status']!='implemented' for c in d['clauses'])):raise ValueError('未实现条款不能标记全部可执行')
        if d['verification']['runtimeFullyVerified'] and (not d['verification']['sourceChecked'] or d['verification']['status']!='verified'):raise ValueError('全部可执行须有本版本来源核对与verified状态')
        if len({a['id'] for a in d['actions']})!=len(d['actions']):raise ValueError('Duplicate action ID')
        for e in d['definition'].get('effects',[]):
            if 'stat' not in e or 'value' not in e:raise ValueError('Effect requires stat and value')
            if e.get('stacking') not in [None,'add']:raise ValueError('Unknown stacking operator')
        supported={'save','attack','damage','status','heal','removeStatus','effect','capability','trigger','inspect'}
        def validate_steps(steps):
            for step in steps:
                if step.get('op') not in supported:raise ValueError(f'{d["id"]}: unsupported operation {step.get("op")}')
                if step['op']=='trigger':validate_steps(step['steps'])
        for program in d['definition'].get('programs',{}).values():
            validate_steps(program['steps'])
        docs.append(d)
    if len({d['id'] for d in docs})!=len(docs):raise ValueError('Duplicate resource ID')
    return docs
def compile_to(destination):
    docs=load_contracts();definitions={d['id']:d['definition'] for d in docs}
    for d in docs:
        definitions[d['id']]['identity']=d['identity']
        definitions[d['id']]['tree']=d['identity']['tree']
        definitions[d['id']]['contractVersion']=d['version']
        definitions[d['id']]['readingHash']=d['reading']['sha256']
        definitions[d['id']]['reading']=d['reading']
        definitions[d['id']]['verification']=d['verification']
        definitions[d['id']]['operations']=[a['operation'] for a in d['actions']]
    destination.mkdir(parents=True,exist_ok=True)
    write_text(destination/'resource-data.mjs','// Generated from paired .rule.json contracts. Do not edit.\nexport const RESOURCE_DATA='+json.dumps(definitions,ensure_ascii=False,separators=(',',':'))+';\n')
    index=[dict(resourceId=d['id'],version=d['version'],name=d['identity']['name'],reading=d['reading'],sourceChecked=d['verification']['sourceChecked'],actions=d['actions'],status=d['verification']['status'],runtimeFullyVerified=d['verification']['runtimeFullyVerified'],implementationGaps=d['implementationGaps'],unresolvedRules=d['unresolvedRules']) for d in docs]
    write_text(destination/'resource-action-index.mjs','// Generated classifier view, not a third authoring source.\nexport const RESOURCE_ACTION_INDEX='+json.dumps(index,ensure_ascii=False,separators=(',',':'))+';\n')
    dump(ROOT/'resources/execution/coverage.json',[dict(id=d['id'],version=d['version'],reading=d['reading'],status=d['verification']['status'],sourceChecked=d['verification']['sourceChecked'],runtimeFullyVerified=d['verification']['runtimeFullyVerified'],programs=list(d['definition'].get('programs',{})),unresolvedRules=d['unresolvedRules'],implementationGaps=d['implementationGaps']) for d in docs])
    return {'contracts':len(docs),'actions':sum(len(d['actions']) for d in docs),'spellPrograms':sum(bool(d['definition'].get('programs')) for d in docs if d['identity']['category']=='spell'),'fullyVerified':sum(d['verification']['runtimeFullyVerified'] for d in docs)}
if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--runtime-output',type=Path);a=p.parse_args()
    print(json.dumps(compile_to(a.runtime_output) if a.runtime_output else {'validatedContracts':len(load_contracts())},ensure_ascii=False))
