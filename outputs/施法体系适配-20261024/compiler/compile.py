"""Validate and project canonical 901-resource/1 magic bundle candidates.

This command never rewrites reading material, contracts, or gameplay state.
Unimplemented actions are exposed only in the blocked/selection indexes.
"""
import argparse,importlib.util,sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parent))
from contracts import *
import jsonschema

def require(ok,message):
    if not ok:raise ValueError(message)

def load():
    schema=json.loads((ROOT/'resources/execution/resource.schema.json').read_text())
    validator=jsonschema.Draft202012Validator(schema);docs=[]
    rows={r['name']:r for r in manifest()}
    shared=json.loads((BASE/'execution/shared.rule.json').read_text());validator.validate(shared)
    require(sha(ROOT/shared['reading']['path'])==shared['reading']['sha256'],'shared policy reading changed')
    for ref in shared['definition']['authoringOnly']['additionalSources']:
        require(sha(ROOT/ref['path'])==ref['sha256'],'shared policy source changed')
    for p in sorted((BASE/'execution/contracts').glob('*.rule.json')):
        d=json.loads(p.read_text());validator.validate(d)
        require(d['version']==VERSION,'unexpected version')
        name=d['identity']['name'];require(name in rows and name not in EXCLUDED,'selection differs')
        require(d['id']==source_id(name),'identity differs')
        require(d['identity']['adoptionStatus']=='candidate','must remain candidate')
        path=ROOT/d['reading']['path'];require(path.resolve().is_relative_to(BASE.resolve()),'reading outside package')
        require(sha(path)==d['reading']['sha256'],'reading changed: '+name)
        for ref in d['identity']['sourceReferences']+d['identity']['sharedDependencies']:
            require(sha(ROOT/ref['path'])==ref['sha256'],'dependency changed: '+ref['path'])
        auth=d['definition']['authoringOnly'];require(digest(d['identity']['sharedDependencies'])==auth['sharedRulesLock'],'shared lock differs')
        require(auth['baseMechanisms']['readingSHA256']==d['reading']['sha256'],'base mechanism reading lock changed: '+name)
        actual=sections(path);require([x['id'] for x in actual]==[x['id'] for x in auth['units']],'clause coverage differs: '+name)
        require(len(d['clauses'])==len(actual),'contract clause count')
        for expected,unit,clause in zip(actual,auth['units'],d['clauses']):
            require(unit['reading']==expected['reading'],'clause changed: '+unit['id'])
            require(clause['heading']==unit['name']==expected['heading'],'clause identity differs')
        require(not d['verification']['runtimeFullyVerified'],'full bundle execution not verified')
        require(all(a['operation'] is None and a['availability']=='blocked' for a in d['actions']),'no active program verified in this batch')
        require(not d['definition'].get('programs'),'unproved program')
        for stage in auth['baseMechanisms'].get('stages',[]):
            require(stage.get('grade') in GRADES,'unknown grade')
        # All finite formulas use the same AST accepted by the actual executor.
        value_validator=jsonschema.Draft202012Validator({'$ref':'#/$defs/value','$defs':schema['$defs']})
        def walk(value):
            if isinstance(value,dict):
                if set(value)=={'op','args'}:value_validator.validate(value)
                for evidence in value.get('sourceEvidence',[]):
                    if not isinstance(evidence,dict) or 'reading' not in evidence:continue
                    ref=evidence['reading'];source=ROOT/ref['path'];start,end=ref['lines']
                    quote='\n'.join(source.read_text().splitlines()[start-1:end])
                    require(ref['quote'] in quote,'mechanism evidence moved: '+name)
                    require(not re.fullmatch(r'[\s|:-]+',ref['quote']),'separator is not rule evidence: '+name)
                    original=evidence.get('original')
                    if original:
                        a,b=original['lines'];require(1<=a<=b<=len((ROOT/original['path']).read_text().splitlines()),'invalid original line range: '+name)
                for child in value.values():walk(child)
            elif isinstance(value,list):
                for child in value:walk(child)
        walk(auth['baseMechanisms']);docs.append(d)
    require(len(docs)==33 and {d['identity']['name'] for d in docs}==set(rows),'33 selected resources required')
    return docs,[]

def build(docs,reuse=None,evidence=None,program_evidence=None,acquisition_evidence=None):
    require(not program_evidence and not acquisition_evidence,'no program/acquisition proof adapter')
    definitions={};slices=[];proofs=(evidence or {}).get('slices',{})
    if evidence:
        for ref in evidence['engineModules']:
            require(sha(ROOT/ref['path'])==ref['sha256'],'executor/test changed; rerun proof: '+ref['path'])
    catalog=[];selection=[];blocked=[]
    formula_count=0;effect_count=0
    def formulas(v):
        if isinstance(v,dict):return int(set(v)=={'op','args'})+sum(formulas(x) for x in v.values())
        if isinstance(v,list):return sum(formulas(x) for x in v)
        return 0
    def compact(v):
        # Evidence remains in the canonical contract; model selection receives
        # only the relevant rule fields plus the top-level source/version pointer.
        if isinstance(v,dict):return {k:compact(x) for k,x in v.items() if k not in ['sourceEvidence','readingSHA256']}
        if isinstance(v,list):return [compact(x) for x in v]
        return v
    for d in docs:
        auth=d['definition']['authoringOnly'];formula_count+=formulas(auth['baseMechanisms'])
        effect_count+=sum(len(s.get('effects',[])) for s in auth['baseMechanisms'].get('stages',[]))
        catalog.append(d)
        selection.append({'resourceId':d['id'],'name':d['identity']['name'],'version':d['version'],'adoptionStatus':'candidate',
            'reading':d['reading'],'stages':compact(auth['baseMechanisms'].get('stages',[])),
            'units':[{'id':u['id'],'name':u['name'],'reading':u['reading'],'fields':u['declaredFields'],'learning':u['learning']} for u in auth['units']],
            'mayPlanSelection':True,'mayExecute':False,'grantsOwnership':False,'unresolvedRules':d['unresolvedRules']})
        blocked += [dict(a,resourceId=d['id'],mayExecute=False) for a in d['actions']]
        accepted=[]
        for s in auth.get('runtimeSlices',[]):
            proof=proofs.get(s['id']);fx=[d['definition']['effects'][i] for i in s['effectIndexes']]
            fp=digest({'slice':s,'effects':fx,'version':d['version'],'reading':d['reading'],'sharedHash':auth['sharedRulesLock']})
            if proof and proof.get('result')=='passed' and proof.get('fingerprint')==fp:
                accepted.extend(s['effectIndexes']);slices.append({'resourceId':d['id'],'sliceId':s['id'],'scope':s['scope']})
        if accepted:
            definitions[d['id']]={'effects':[d['definition']['effects'][i] for i in sorted(set(accepted))],
                'identity':d['identity'],'contractVersion':d['version'],'reading':d['reading'],'operations':[],
                'verification':{'status':'partial','sourceChecked':True,'runtimeFullyVerified':False,'scope':'verified-passive-slices-only'}}
    counts={'candidateContracts':len(docs),'structuredUnits':sum(len(d['clauses']) for d in docs),
        'sharedPolicyContracts':1,'declaredBaseEffects':effect_count,
        'declaredBaseStages':sum(len(d['definition']['authoringOnly']['baseMechanisms'].get('stages',[])) for d in docs),
        'formulaASTNodes':formula_count,'verifiedPassiveSlices':len(slices),'runtimeDefinitions':len(definitions),
        'runnableActionWhitelist':0,'verifiedAcquisitionTransactions':0,'fullyExecutableCandidateContracts':0,
        'blockedActionIntents':len(blocked),'allSemanticsEncoded':False,
        'unresolvedRuleCount':len({r['parameter'] for d in docs for r in d['unresolvedRules']}),
        'unresolvedRuleGroups':len({r.get('group',r['parameter']) for d in docs for r in d['unresolvedRules']})}
    def esm(export,data):return '// Generated from candidate contracts; no adoption, acquisition or deployment.\nexport const '+export+'='+json.dumps(data,ensure_ascii=False,separators=(',',':'))+';\n'
    artifacts={'resource-data.mjs':esm('RESOURCE_DATA',definitions),'resource-action-index.mjs':esm('RESOURCE_ACTION_INDEX',[]),
        'resource-selection-index.mjs':esm('RESOURCE_SELECTION_INDEX',selection),'resource-blocked-index.mjs':esm('RESOURCE_BLOCKED_INDEX',blocked),
        'resource-contract-index.mjs':esm('RESOURCE_CONTRACT_INDEX',catalog),
        'resource-policies.mjs':esm('RESOURCE_SHARED_POLICIES',json.loads((BASE/'execution/shared.rule.json').read_text())),
        'coverage.json':encoded({'counts':counts,'passiveSlices':slices,'contractFingerprints':{d['id']:digest(d) for d in docs}})}
    table=['# 魔幻能力组双版本索引','',
        '由机械契约生成；阅读版与契约是两种表示，本表不是另一个规则来源。选择资源不授予人物持有。',
        '本体已按阶段声明；技能树的未编码条款仍标为实现缺口，动作白名单仅接纳实际验证的动作。','',
        '| 资源 | 本体阶段 | 本体效果声明 | 阅读版 | 机械契约 |',
        '| --- | --- | ---: | --- | --- |']
    for d in sorted(docs,key=lambda d:d['identity']['name']):
        b=d['definition']['authoringOnly']['baseMechanisms'];stages=b.get('stages',[])
        table.append('| '+d['identity']['name']+' | '+' / '.join(s['grade'] for s in stages)+' | '+str(sum(len(s.get('effects',[])) for s in stages))+
            ' | [阅读](../../阅读版/'+d['identity']['name']+'.md) | [JSON](../contracts/'+d['id']+'.rule.json) |')
    table+=['','共用动作／学习报价：[机械契约](../shared.rule.json)。详细实际覆盖：[coverage.json](coverage.json)。',
        '未安装到主运行环境；未创建NPC、修改T0或授予能力。','']
    artifacts['机械版索引.md']='\n'.join(table)
    return artifacts,counts

if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('--check',action='store_true');args=parser.parse_args()
    docs,reuse=load();proof=BASE/'execution/runtime-verification.json'
    artifacts,counts=build(docs,reuse,json.loads(proof.read_text()) if proof.exists() else None)
    output=BASE/'execution/generated'
    if not args.check:output.mkdir(parents=True,exist_ok=True)
    for name,body in artifacts.items():
        p=output/name
        if args.check:require(p.exists() and p.read_text()==body,'generated artifact stale: '+name)
        else:p.write_text(body)
    print(json.dumps({'result':'PASS','mode':'check' if args.check else 'compile','counts':counts},ensure_ascii=False))
