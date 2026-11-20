"""Validate paired resource contracts and generate runtime data/action indexes.

No inference from prose, no model call, no gameplay-state writes. Unknown rules
and unfinished implementations remain separate in the generated coverage list.
"""
from pathlib import Path
import argparse,hashlib,importlib.util,json,re
from resource_recipes import compile_contract
from rule_expressions import validate_rule_data
from operation_contracts import validate_schema,validate_operation_fields,validate_receipt_references,inspect_definition_consumers
ROOT=Path(__file__).resolve().parents[1]
def dump(p,data):
    p.parent.mkdir(parents=True,exist_ok=True)
    p.write_text(json.dumps(data,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
ENGINE=json.loads((ROOT/'resources/execution/_engine-capabilities.json').read_text(encoding='utf-8'))
CAPABILITIES=ENGINE['capabilities']
if json.loads(ENGINE['abi'])!=CAPABILITIES:raise ValueError('Capability artifact ABI mismatch; regenerate from the actual engine')
SUPPORTED_OPS=set(CAPABILITIES['operators'])

def validate_technique(technique, resource_id):
    """Validate shared clause data, without registering a new execution operator."""
    def literal(value):
        return {'type': 'boolean' if type(value) is bool else 'null' if value is None else 'integer' if type(value) is int else 'string', 'enum': [value]}
    def obj(fields): return {'type': 'object', 'fields': fields, 'required': list(fields)}
    text={'type':'string','minLength':1}
    strings={'type':'array','items':text}
    number={'type':'number','minimum':0}
    params=obj({'attack':literal('melee_blades'),'weapon':literal('katana'),'attacksPerTarget':literal(1),
        'damageCap':literal('current_weapon_native_cap'),'protection':literal('normal'),
        'attackDP':number,'bonusType':literal('增强'),'maxElectricFraction':number,
        'paralysisBasis':literal('actual_electric_damage'),'save':literal('fortitude')})
    schema=obj({'schemaVersion':literal('901-weapon-technique/1'),'mode':literal('active'),'action':literal('standard'),
        'cost':obj({'sourcePool':text,'nativeResourceId':literal(None),'amount':{'type':'integer','minimum':0}}),
        'cooldownRounds':{'type':'integer','minimum':0},
        'effects':{'type':'array','items':obj({'op':literal('weapon_technique'),'params':params})},
        'optionalAcquiredBranches':{'type':'array','items':obj({'name':text,'additionalXP':number,'ownershipRef':literal(None),
            'canActivate':literal(False),'eligibleTargets':strings,'maxElectricFraction':number,'electricDamageBonus':number,'tags':strings,'otherTargets':text})},
        'limits':strings})
    common={'damageCap':literal('current_weapon_native_cap'),'protection':literal('normal')}
    if resource_id=='huang.rock_cleaver':
        schema['fields']['effects']['items']['fields']['params']=obj({**common,
            'attack':literal('melee_blades'),'weapon':literal('katana'),'attacksPerTarget':literal(1),
            'hands':literal(2),'weaponValueDelta':number,'armorPenetration':number,'tags':strings,'ignoreReductionOrHardness':number})
        schema['fields']['optionalAcquiredBranches']['items']=obj({'name':text,'additionalXP':number,'ownershipRef':literal(None),'canActivate':literal(False),
            'redirect':literal('adjacent_to_struck_target'),'defenseBasis':literal('struck_target_basic_defense'),'coverAttack':literal(True),
            'actualTargetFlatFooted':literal(True),'defenseReductionType':literal('flat_footed'),'immuneFlatFooted':literal('unaffected_by_this_use')})
    elif resource_id=='huang.iai':
        schema['fields'].update(mode=literal('triggered'),action=literal('passive_weapon_trigger'),cost=literal(None),cooldownRounds=literal(None),
            prerequisites=obj({'DEX':number,'PRE':number,'WIL':number,'effectiveBlades':number,'bladeSubskill':literal('existing_qualification'),'quickDraw':literal('existing_qualification')}))
        schema['required'].append('prerequisites')
        schema['fields']['effects']['items']=obj({'op':literal('drawn_weapon_first_strike'),'params':obj({
            'weapon':literal('slender_curved_blade'),'oneHandBladeMaxArmspanFraction':number,'twoHandKatanaLengthException':literal('existing_training_only'),
            'normalWieldingRequired':literal(True),'initiativeBonus':number,'initiativeBonusType':literal('修行'),'initiativeCondition':literal('wear_applicable_weapon'),
            'attack':literal('first_melee_blades_attack_in_unsheathing_turn'),'attackDP':number,'bonusType':literal('招式'),
            'aggravateMaxL':number,'aggravateCondition':literal('initiative_ahead_of_target'),'defensePenalty':number,'defensePenaltyStarts':literal('after_strike'),
            'defensePenaltyExpires':literal('next_own_action_start'),'grantsQuickDraw':literal(False),'grantsExtraAttack':literal(False)})})
    elif resource_id=='kuanglan':
        schema['fields']['cooldownRounds']=literal(None)
        schema['fields']['effects']['items']['fields']['params']=obj({**common,
            'mode':{'type':'string','enum':['gale','tornado']},'exclusiveModes':literal(True),'weapon':literal('usable_current_qifeng'),'attack':literal('blades'),
            'targets':{'type':'string','enum':['all_eligible_enemies_in_radius','one_eligible_enemy']},'rangeMeters':number,
            'requiresLocalization':literal(True),'requiresLineOfEffect':literal(True),'excludeAllies':literal(True),'attacksPerTarget':literal(1),
            'separateRolls':literal(True),'paymentsPerAction':literal(1),'attackDP':number,'bonusType':{'type':'string','enum':['招式','none']},'defenseReduction':number,
            'defenseReductionType':{'type':'string','enum':['combined_multiattack_and_environment','unspecified_total']},'duration':literal('this_attack_only'),
            'drawIfSheathed':literal('within_same_action'),'damageType':literal('current_weapon'),'stackLegacyReduction':literal(False)})
    elif resource_id!='huang.thunder_sword':
        raise ValueError(resource_id+': unsupported shared technique consumer')
    validate_schema(technique,schema,resource_id+'.technique')
    if len(technique['effects'])!=(2 if resource_id=='kuanglan' else 1) or not technique['limits']:
        raise ValueError(resource_id+': technique requires one complete base clause and limits')
    if resource_id in ['huang.iai','kuanglan'] and technique['optionalAcquiredBranches']:
        raise ValueError(resource_id+': no acquired optional branch is supported')
    if resource_id=='kuanglan' and [e['params']['mode'] for e in technique['effects']]!=['gale','tornado']:
        raise ValueError(resource_id+': requires both distinct modes in source order')
    if resource_id=='huang.thunder_sword' and (technique['effects'][0]['params']['maxElectricFraction']>1 or any(b['maxElectricFraction']>1 for b in technique['optionalAcquiredBranches'])):
        raise ValueError(resource_id+': electric fraction exceeds whole damage')

def validate_program(program, resource_id):
    """Validate the new shared consumers; this is not a complete IR type checker."""
    if 'supportedGrades' in program and (not isinstance(program['supportedGrades'],list) or not program['supportedGrades'] or any(x not in CAPABILITIES['programPolicies']['supportedGrades'] for x in program['supportedGrades'])):raise ValueError(resource_id+': unsupported program grade')
    if 'spellResistance' in program and program['spellResistance'] not in CAPABILITIES['programPolicies']['spellResistance']:raise ValueError(resource_id+': unsupported spell resistance policy')
    if 'toggle' in program and (program['toggle'] not in CAPABILITIES['programPolicies']['toggle'] or program.get('target')!='self'):raise ValueError(resource_id+': unsupported toggle policy')
    if 'endEffects' in program and (program['endEffects'] not in CAPABILITIES['programPolicies']['endEffects'] or program.get('casting') is not False or program.get('action')!='free' or program.get('cost')!=0 or program.get('steps')):raise ValueError(resource_id+': unsupported voluntary termination')
    if program.get('area',{}).get('shape')=='cone':validate_schema(program['area'],CAPABILITIES['programPolicies']['coneArea'],resource_id+'.area')
    if 'cooldownAfterUses' in program and 'cooldown' in program:raise ValueError(resource_id+': conflicting cooldown policies')
    for key in ['targetAllocation','targetProgression','cooldownAfterUses']:
        if key in program:validate_schema(program[key],CAPABILITIES['programPolicies'][key],resource_id+'.'+key)
    if 'targetProgression' in program and program.get('target')!='single':raise ValueError(resource_id+': target progression needs single target')
    if 'requiredItems' in program:validate_schema(program['requiredItems'],CAPABILITIES['programPolicies']['requiredItems'],resource_id+'.requiredItems')
    validate_rule_data(program, CAPABILITIES, resource_id)
    components=program.get('effectComponents',{})
    def reject(message): raise ValueError(f'{resource_id}: {message}')
    for name,component in components.items():
        if not isinstance(component,dict) or not isinstance(component.get('families'),list) or not all(isinstance(x,str) and x for x in component['families']):reject('invalid component families: '+name)
        if component.get('mode','any-blocks') not in CAPABILITIES['immunityModes']:reject('unsupported immunity mode')
        if type(component.get('gradeBonus',0)) is not int:reject('component gradeBonus must be integer')
        for key in ['grade','maximumGrade']:
            if key in component and component[key] not in ['none','D','C','B','A','S','SS','SSS']:reject('invalid component grade')
    def steps(rows):
        receipts={}
        for index,step in enumerate(rows):
            if step.get('op') not in SUPPORTED_OPS:reject('unsupported operation '+str(step.get('op')))
            component=step.get('component')
            if component is not None and component not in components:reject('unknown component '+component)
            if 'immunityLifecycle' in step:
                lifecycle=step['immunityLifecycle']
                if lifecycle not in CAPABILITIES['operators'][step['op']]['lifecycles']:reject('unsupported immunity lifecycle for this operation')
                if component is None:reject('immunity lifecycle requires component')
                if step['op']=='aura' and step.get('temporaryAllocation'):reject('immunity lifecycle for aura pools is not implemented')
                if components[component].get('mode')=='fraction-unblocked':
                    if step['op'] in ['trigger','status']:reject('partial immunity lifecycle for this operation is not implemented')
                    if step.get('immunityScaling')!='floor-magnitude':reject('partial immunity requires explicit scaling')
            if 'immunityScaling' in step and (step.get('immunityLifecycle')!='suppress' or step['immunityScaling']!='floor-magnitude'):reject('unsupported immunity scaling')
            if 'exclusivePolicy' in step and (step['op']!='effect' or not step.get('exclusiveGroup') or step['exclusivePolicy'] not in CAPABILITIES['operators']['effect']['exclusivePolicies']):reject('unsupported exclusive effect policy')
            if 'movement' in step:
                move=step['movement']
                if step['op']!='capability' or move.get('mode') not in CAPABILITIES['operators']['capability']['movementModes'] or move.get('maneuverability') not in CAPABILITIES['operators']['capability']['maneuverability'] or not ('speed' in move or move.get('speedBasis') in CAPABILITIES['operators']['capability']['movementSpeedBases'] and 'speedMultiplier' in move):reject('unsupported movement consumer')
            if 'onEnd' in step:
                end=step['onEnd']
                if step['op']!='capability' or end.get('kind') not in CAPABILITIES['operators']['capability']['endConsequences'] or end['kind']=='descent' and ('rounds' not in end or any(type(end.get(k)) not in (int,float) or end[k]<=0 for k in ['intervalMinutes','metersPerRound'])):reject('unsupported termination consequence')
            if 'budgetScope' in step and (step['op']!='removeStatus' or step['budgetScope'] not in CAPABILITIES['operators']['removeStatus']['budgetScopes'] or not isinstance(step.get('types'),list) or not step['types'] or len(set(step['types']))!=len(step['types'])):reject('invalid status budget scope')
            if 'initialBlocked' in step and (step['op']!='effect' or step.get('immunityLifecycle')!='suppress' or step['initialBlocked'] not in CAPABILITIES['operators']['effect']['initialBlockedPolicies']):reject('unsupported initial blocked policy')
            if 'turnOrder' in step and (step['op']!='effect' or step['turnOrder'] not in CAPABILITIES['operators']['effect']['turnOrderPolicies'] or not any(e.get('stat')=='currentInitiative' for e in step.get('effects',[]))):reject('unsupported turn order consumer')
            if 'targetSceneLimit' in step and (step['op']!='effect' or step.get('scene') is not True or type(step['targetSceneLimit']) is not int or step['targetSceneLimit']<1):reject('invalid target scene limit')
            if step['op']=='accumulate':
                if not step.get('key') or step.get('thresholdAttribute') not in ['力量','敏捷','智力','感知','意志','风度'] or 'amount' not in step:reject('incomplete accumulator')
                if any(type(step.get(k)) is not int or step[k]<=0 for k in ['conditionMinutes','resetAfterRestMinutes']):reject('invalid accumulator recovery duration')
            if 'recovery' in step and (step['op']!='damage' or step['recovery'] not in CAPABILITIES['operators']['damage']['recoveryRestrictions']):reject('unsupported wound recovery restriction')
            if 'requiresConscious' in step and (step['op']!='trigger' or type(step['requiresConscious']) is not bool):reject('invalid trigger consciousness policy')
            if 'actionPrice' in step:
                price=step['actionPrice']
                if step['op']!='effect' or price.get('family') not in CAPABILITIES['operators']['effect']['actionPriceFamilies'] or not isinstance(price.get('baseByAction'),dict):reject('unsupported action pricing consumer')
                if set(price['baseByAction'])-set(CAPABILITIES['operators']['effect']['pricedActions']):reject('unregistered physical action price')
                if any(type(n) is not int or not 1<=n<=12 for n in price['baseByAction'].values()):reject('invalid base action price')
                if any(type(price.get(k)) is not int or price[k]<1 for k in ['minimumAP','perRound']):reject('invalid action price minimum or quota')
                if ('discount' in price)==('surcharge' in price) or not price.get('quotaKey'):reject('need exactly one action price adjustment and quota identity')
            if step['op']=='save':
                validate_schema(step.get('type'),CAPABILITIES['operators']['save']['fields']['type'],resource_id+'.save.type')
                resolution=step.get('resolve',{'kind':'roll'});kind=resolution.get('kind')
                needed={'roll':[],'opposed':['active'],'threshold':['dc'],'subtract':['incoming','perSuccess']}
                if kind not in CAPABILITIES['resistanceModes'] or kind not in needed or any(k not in resolution for k in needed[kind]):reject('incomplete resistance resolution')
                key=step.get('resultAs',step.get('as','save'))
                receipts[key]=(component,step.get('when'))
            resistance=step.get('resistance')
            if isinstance(resistance,dict):
                if step['op'] not in ['status','damage']:reject('resistance receipt has no consumer for operation')
                key=resistance.get('receipt');receipt=receipts.get(key)
                if receipt is None or receipt[0]!=component:reject('missing or cross-component resistance receipt')
                if receipt[1] is not None and receipt[1]!=step.get('when'):reject('conditional resistance receipt needs matching guard')
                if resistance.get('kind') not in ['resolved','subtract']:reject('unsupported resistance receipt consumer')
                if resistance['kind']=='subtract' and (not isinstance(resistance.get('perSuccess'),(int,float)) or isinstance(resistance.get('perSuccess'),bool) or resistance['perSuccess']<0):reject('subtract requires explicit perSuccess')
            validate_operation_fields(step,CAPABILITIES,f'{resource_id}: steps[{index}]')
            if step['op']=='trigger':
                steps(step['steps'])
                if 'onDeath' in step:
                    if step['event']!='turnStart' or any(x['op'] not in CAPABILITIES['programPolicies']['automaticReference']['steps'] for x in step['onDeath']['steps']):reject('unsupported death area program')
                    steps(step['onDeath']['steps'])
    steps(program['steps'])
    validate_receipt_references(program,CAPABILITIES,resource_id)

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
        if d['verification']['runtimeFullyVerified'] and (not d['verification'].get('sourceChecked',False) or d['verification']['status']!='verified'):raise ValueError('全部可执行须有本版本来源核对与verified状态')
        if d['verification']['runtimeFullyVerified'] and (d['implementationGaps'] or any(c['status']!='implemented' for c in d['clauses'])):raise ValueError('未实现条款不能标记全部可执行')
        if len({a['id'] for a in d['actions']})!=len(d['actions']):raise ValueError('Duplicate action ID')
        for e in d['definition'].get('effects',[]):
            if 'stat' not in e or 'value' not in e:raise ValueError('Effect requires stat and value')
            if e.get('stacking') not in [None,*CAPABILITIES['operators']['effect']['fields']['effects']['items']['fields']['stacking']['enum']]:raise ValueError('Unknown stacking operator')
        if 'effectPolicyMigrations' in d['definition']:validate_schema(d['definition']['effectPolicyMigrations'],CAPABILITIES['definitionPolicies']['effectPolicyMigrations'],d['id']+'.effectPolicyMigrations')
        d=compile_contract(d)
        if 'technique' in d['definition']:
            validate_technique(d['definition']['technique'],d['id'])
        validate_rule_data(d['definition'], CAPABILITIES, d['id'])
        for program in d['definition'].get('programs',{}).values():
            validate_program(program,d['id'])
        d['consumerCoverage']=inspect_definition_consumers(d['definition'],CAPABILITIES)
        docs.append(d)
    if len({d['id'] for d in docs})!=len(docs):raise ValueError('Duplicate resource ID')
    definitions={d['id']:d['definition'] for d in docs}
    def references(node):
        if isinstance(node,dict):
            if 'onDepleted' in node:
                ref=node['onDepleted'];program=definitions.get(ref['resourceId'],{}).get('programs',{}).get(ref['operation'])
                allowed=CAPABILITIES['programPolicies']['automaticReference']
                if not program or program.get('target')!=allowed['target'] or program.get('area',{}).get('center')!=allowed['center'] or program.get('area',{}).get('team')!=allowed['team'] or program.get('area',{}).get('selected') or any(s['op'] not in allowed['steps'] for s in program['steps']):raise ValueError('unsupported automatic referenced program: '+ref['resourceId'])
            for child in node.values():references(child)
        elif isinstance(node,list):
            for child in node:references(child)
    for d in docs:references(d['definition'])
    return docs
def load_candidate_package(package):
    """Read a verified authoring package, without adopting it or executing its tests.

    Its compiler checks source/contract/proof fingerprints. Only its executable
    projection is eligible for development runtime inclusion; blocked units stay out.
    """
    package=Path(package).resolve()
    if not package.is_relative_to(ROOT.resolve()):raise ValueError('Candidate package outside kit')
    path=package/'compiler/compile.py'
    spec=importlib.util.spec_from_file_location('candidate_resource_projection',path)
    module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
    docs,reuse=module.load()
    evidence=[]
    for name in ['runtime-verification.json','program-verification.json','acquisition-verification.json']:
        p=package/'execution'/name
        evidence.append(json.loads(p.read_text()) if p.exists() else None)
    artifacts,counts=module.build(docs,reuse,*evidence)
    for name,body in artifacts.items():
        p=package/'execution/generated'/name
        if not p.exists() or p.read_text()!=body:raise ValueError('Candidate projection is stale: '+name)
    def data(name,export):
        match=re.search(r'export const '+export+r'=(.*);\s*$',artifacts[name],re.S)
        if not match:raise ValueError('Invalid candidate projection: '+name)
        return json.loads(match[1])
    definitions=data('resource-data.mjs','RESOURCE_DATA')
    index=data('resource-action-index.mjs','RESOURCE_ACTION_INDEX')
    selected={d['id']:d for d in docs if d['id'] in definitions}
    if set(definitions)!=set(selected):raise ValueError('Unknown executable candidate identity')
    for id,d in selected.items():
        if definitions[id]['contractVersion']!=d['version'] or definitions[id]['reading']!=d['reading']:
            raise ValueError('Candidate runtime provenance differs: '+id)
    return definitions,index,selected,counts

def candidate_packages(packages):
    """Keep the original single-package Python API as well as repeated CLI flags."""
    if packages is None:return []
    if isinstance(packages,(str,Path)):return [Path(packages).resolve()]
    return [Path(package).resolve() for package in packages]

def load_candidate_packages(packages):
    definitions={};index=[];selected={};reports=[]
    for package in candidate_packages(packages):
        data,actions,docs,counts=load_candidate_package(package)
        if set(definitions)&set(data):raise ValueError('Candidate identity collides across packages')
        definitions.update(data);index.extend(actions);selected.update(docs)
        reports.append(dict(path=package.relative_to(ROOT.resolve()).as_posix(),counts=counts))
    return definitions,index,selected,reports

def compile_to(destination,candidate_package=None):
    docs=load_contracts();definitions={d['id']:d['definition'] for d in docs}
    for d in docs:
        definitions[d['id']]['identity']=d['identity']
        definitions[d['id']]['tree']=d['identity'].get('tree')
        definitions[d['id']]['reading']=d['reading']
        definitions[d['id']]['verification']=d['verification']
        definitions[d['id']]['contractVersion']=d['version']
        definitions[d['id']]['readingHash']=d['reading']['sha256']
        definitions[d['id']]['operations']=[a['operation'] for a in d['actions']]
    candidates={}
    if candidate_package:
        candidates,candidate_index,_,_=load_candidate_packages(candidate_package)
        if set(definitions)&set(candidates):raise ValueError('Candidate identity collides with maintained resource')
        definitions.update(candidates)
    destination.mkdir(parents=True,exist_ok=True)
    (destination/'resource-data.mjs').write_text('// Generated from paired .rule.json contracts. Do not edit.\nexport const RESOURCE_ENGINE_ABI='+json.dumps(ENGINE['abi'],ensure_ascii=False)+';\nexport const RESOURCE_DATA='+json.dumps(definitions,ensure_ascii=False,separators=(',',':'))+';\n',encoding='utf-8')
    index=[dict(resourceId=d['id'],access=d['definition'].get('access','owned'),version=d['version'],name=d['identity']['name'],reading=d['reading'],sourceChecked=d['verification'].get('sourceChecked',False),consumerCoverage=d['consumerCoverage'],actions=d['actions'],status=d['verification']['status'],adoptedDecisions=d.get('adoptedDecisions',[]),runtimeFullyVerified=d['verification']['runtimeFullyVerified'],implementationGaps=d['implementationGaps'],unresolvedRules=d['unresolvedRules']) for d in docs]
    if candidate_package:index.extend(candidate_index)
    (destination/'resource-action-index.mjs').write_text('// Generated classifier view, not a third authoring source.\nexport const RESOURCE_ACTION_INDEX='+json.dumps(index,ensure_ascii=False,separators=(',',':'))+';\n',encoding='utf-8')
    dump(ROOT/'resources/execution/coverage.json',[dict(id=d['id'],version=d['version'],reading=d['reading'],sourceChecked=d['verification'].get('sourceChecked',False),runtimeFullyVerified=d['verification']['runtimeFullyVerified'],programs=list(d['definition'].get('programs',{})),consumerCoverage=d['consumerCoverage'],status=d['verification']['status'],unresolvedRules=d['unresolvedRules'],implementationGaps=d['implementationGaps']) for d in docs])
    return {'contracts':len(docs),'actions':sum(len(d['actions']) for d in docs),'fullyVerified':sum(d['verification']['runtimeFullyVerified'] for d in docs),'developmentCandidates':len(candidates),'candidateActions':sum(len(x['actions']) for x in index if x['resourceId'] in candidates)}
if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--runtime-output',type=Path);p.add_argument('--candidate-package',type=Path,action='append',help='Repeat to include multiple proof-current candidate packages in development output');a=p.parse_args()
    if a.runtime_output:result=compile_to(a.runtime_output,a.candidate_package)
    else:
        result={'validatedContracts':len(load_contracts())}
        if a.candidate_package:result['validatedDevelopmentCandidates']=len(load_candidate_packages(a.candidate_package)[0])
    print(json.dumps(result,ensure_ascii=False))
