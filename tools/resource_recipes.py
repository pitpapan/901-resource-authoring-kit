"""Finite, versioned build-time templates. Never executes resource code."""
from pathlib import Path
import copy, hashlib, json, re
RECIPES=Path(__file__).resolve().parents[1]/'resources/execution/_recipes'

def expression(value):
    if type(value) in (int,float):return True
    if not isinstance(value,dict):return False
    if set(value)=={'context'}:return isinstance(value['context'],str) and bool(value['context'])
    return set(value)=={'op','args'} and value['op'] in ['add','sub','mul','div','floor','min','max'] and isinstance(value['args'],list) and all(expression(x) for x in value['args'])

def compile_contract(contract):
    doc=copy.deepcopy(contract)
    for operation,program in doc['definition'].get('programs',{}).items():
        if 'recipe' not in program:continue
        if doc.get('authoring',{}).get('executionSource')!='contract':raise ValueError('Recipe requires contract as the sole execution source')
        if 'steps' in program:raise ValueError('Recipe and handwritten steps are competing execution sources')
        ref=program.pop('recipe');name=ref['id'];version=ref['version']
        if not re.fullmatch('[a-z][a-z0-9-]*',name) or type(version) is not int:raise ValueError('Invalid recipe identity')
        path=RECIPES/f'{name}.v{version}.json'
        if not path.is_file():raise ValueError('Unsupported recipe version: '+str(ref))
        raw=path.read_bytes();recipe=json.loads(raw)
        if recipe['id']!=name or recipe['version']!=version:raise ValueError('Recipe identity mismatch')
        if ref.get('clauseId') not in {c.get('id') for c in doc['clauses']}:raise ValueError('Recipe requires an actual source clause')
        args=ref['args'];specs=recipe['parameters']
        if set(args)!=set(specs):raise ValueError('Recipe parameter set differs from the declared interface')
        for key,spec in specs.items():
            v=args[key];kind=spec['type']
            valid=(kind=='expression' and expression(v) or kind=='string' and isinstance(v,str) and bool(v)
                   or kind=='object' and isinstance(v,dict) or kind=='enum' and v in spec['values'])
            if not valid:raise ValueError('Recipe parameter type mismatch: '+key)
        def expand(value):
            if isinstance(value,list):return [expand(x) for x in value]
            if not isinstance(value,dict):return value
            if set(value)=={'parameter'}:
                if value['parameter'] not in args:raise ValueError('Undeclared recipe parameter')
                return copy.deepcopy(args[value['parameter']])
            return {k:expand(v) for k,v in value.items()}
        program['steps']=expand(recipe['steps'])
        program['compilation']={'recipeId':name,'templateVersion':version,'templateSHA256':hashlib.sha256(raw).hexdigest(),
            'resourceId':doc['id'],'resourceVersion':doc['version'],'clauseId':ref['clauseId'],'reading':copy.deepcopy(doc['reading']),
            'stepIds':[operation+'/'+step['id'] for step in recipe['steps']]}
        for step,step_id in zip(program['steps'],program['compilation']['stepIds']):step['id']=step_id
        # The human action keeps labels/route; its executable metadata is derived.
        for action in doc['actions']:
            if action['operation']!=operation:continue
            action.update(programSource=copy.deepcopy(program['compilation']),actionCost=program['action'],targetMode=program['target'],choices=copy.deepcopy(program.get('choices',{})),
                allocations=copy.deepcopy(program.get('allocations',[])),effectComponents=copy.deepcopy(program.get('effectComponents',{})),
                resistanceModes=[{'profile':s['type'],'kind':s.get('resolve',{}).get('kind','roll'),'receipt':s.get('resultAs',s.get('as','save'))} for s in program['steps'] if s['op']=='save'],
                immunityLifecycles=[{'operation':s['op'],'component':s['component'],'policy':s['immunityLifecycle']} for s in program['steps'] if s.get('immunityLifecycle')])
    return doc
