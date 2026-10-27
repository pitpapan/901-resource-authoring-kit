"""One-time scaffold. Refuses to overwrite reviewed machine contracts.

The temporary base-mechanisms input is inlined; after import .rule.json files
are the only machine rule source. This script is not run by the compiler.
"""
import argparse,json,re
from contracts import *

def seed(base_rules):
    directory=BASE/'execution/contracts'
    if list(directory.glob('*.rule.json')):raise ValueError('已有契约：请直接修订，不从脚手架覆盖')
    rows=manifest();assert len(rows)==33 and set(base_rules)=={r['name'] for r in rows}
    shared=shared_dependencies();directory.mkdir(parents=True,exist_ok=True)
    for row in rows:
        name=row['name'];assert name not in EXCLUDED
        path=BASE/row['reading'];pieces=sections(path);units=[build_unit(p) for p in pieces]
        rid=source_id(name)
        # Each selectable intent is bound to its exact clause, never executable merely
        # because a prose fragment contains an action word.
        actions=[]
        for p,u in zip(pieces,units):
            if u['actionPrices'] or u['declaredFields'].get('施放') or re.search(r'(?:动作|施放|发动|每当|每轮)',p['body']):
                actions.append({'id':rid+'/'+u['id'],'name':u['name'],'operation':None,'actionCost':u['actionPrices'],
                    'requiredChoice':[],'requestFields':[],'allowsModelNumericEffects':False,'availability':'blocked',
                    'clauseId':u['id'],'missingPolicy':'implementation-needed; do not ask player for a rule'})
        doc={'schemaVersion':'901-resource/1','id':rid,'version':VERSION,
            'identity':{'name':name,'grade':'multi','category':'rule' if name=='魔导书总纲' else 'bundle','tree':name,
                'adoptionStatus':'candidate','aliases':[],'sharedDependencies':shared,
                'sourceReferences':[{'path':row['path'],'sha256':row['sha256']}]},
            'reading':{'path':path.relative_to(ROOT).as_posix(),'sha256':sha(path)},
            'definition':{'effects':[],'programs':{},'authoringOnly':{'units':units,'baseMechanisms':base_rules[name],
                'sharedRulesLock':digest(shared),'runtimeSlices':[],
                'acquisition':{'requiresAdoptedOffer':True,'requiresActualQualification':True,'treeEntryGrantsChildren':False,
                    'resetState':False,'autoGrantToT0':False,'unverifiedPricesMayNotBeCharged':True}}},
            'clauses':[{'heading':u['name'],'effectStats':[],'status':'pending'} for u in units],
            'actions':actions,'inputs':[
                {'id':'ownedResource','type':'versioned-acquisition-record','provider':'saved-state','requiredFor':['effects','actions'],'missingPolicy':'block-related-operation'},
                {'id':'choices','type':'declared-selection','provider':'player','requiredFor':['acquisition'],'missingPolicy':'ask-only-required-choice'},
                {'id':'sceneFacts','type':'sourced-target-and-scene','provider':'host','requiredFor':['actions'],'missingPolicy':'block-related-operation'}],
            'unresolvedRules':[],
            'implementationGaps':['本体声明尚需逐机制接入与执行证明；技能树逐条款保留来源定位，尚未完整编码；未验证动作不进入执行白名单。'],
            'verification':{'status':'pending','sourceChecked':True,'runtimeFullyVerified':False,'scope':'paired-source-and-declarative-base; not full runtime'}}
        for path in base_rules[name].get('inputBindings',{}).get('stateReads',[]):
            doc['inputs'].append({'id':'state:'+path,'type':'number','provider':'saved-state','requiredFor':['base-mechanisms'],'missingPolicy':'block-only-dependent-operation-before-cost'})
        for binding in base_rules[name].get('inputBindings',{}).get('contextInputs',[]):
            doc['inputs'].append({'id':'context:'+binding['path'],'type':binding['type'],'provider':'host',
                'requiredFor':[x['grade']+'/'+x['effectId'] for x in binding.get('affectedEffects',[])],
                'missingPolicy':binding['missingPolicy'],'basis':binding['provider'],'sourceRequired':True,
                'runtimeAdapterStatus':binding['runtimeAdapterStatus']})
        for issue in base_rules[name].get('unresolvedRules',[]):
            doc['unresolvedRules'].append({'parameter':issue['parameter'],'basis':issue['reason']+'；'+json.dumps(issue.get('sourceEvidence',[]),ensure_ascii=False),
                'recommendation':'只暂停依赖此缺口的取得或效果；按未决项.md所列原文核定，不从相邻阶位补造。'})
        base=doc['definition']['authoringOnly']['baseMechanisms'];base['status']='declarative-contract-source'
        if base.get('inheritsBaseContract'):
            reference=base['inheritsBaseContract'];reference['resourceId']=source_id(reference['resource']);reference['version']=VERSION
        for unit,clause in zip(units,doc['clauses']):
            unit['baseMechanismRefs']=[]
            for si,stage in enumerate(base.get('stages',[])):
                for ei,effect in enumerate(stage.get('effects',[])):
                    if any(ref.get('reading',{}).get('path')==doc['reading']['path'] and
                        unit['reading']['startLine']<=ref['reading']['lines'][0]<=unit['reading']['endLine']
                        for ref in effect.get('sourceEvidence',[])):
                        unit['baseMechanismRefs'].append('/definition/authoringOnly/baseMechanisms/stages/'+str(si)+'/effects/'+str(ei))
            if unit['baseMechanismRefs']:clause['status']='partial'
        (directory/(rid+'.rule.json')).write_text(encoded(doc))
    print(json.dumps({'created':len(rows)},ensure_ascii=False))

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--base-mechanisms',required=True,type=Path);a=p.parse_args()
    seed(json.loads(a.base_mechanisms.read_text()))
