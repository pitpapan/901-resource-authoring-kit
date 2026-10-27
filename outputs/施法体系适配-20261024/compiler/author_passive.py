"""Author the bounded shadow-bundle fortitude declarations; no gameplay writes."""
from contracts import *

path=BASE/'execution/contracts'/(source_id('阴影超魔使')+'.rule.json')
d=json.loads(path.read_text());rid=d['id'];record='learnedResources.'+rid
auth=d['definition']['authoringOnly']
assert '强韧+3G内在DP' in (ROOT/d['reading']['path']).read_text()
effects=[];slices=[]
for i,grade in enumerate(['D','C','B']):
    clauses=[{'test':'eq','left':{'state':record+'.'+key},'right':value} for key,value in
        [('learned',True),('version',d['version']),('adoptionStatus','adopted'),('qualificationVersion',d['version']),('grade',grade)]]
    clauses += [{'test':'contains','left':{'state':record+'.completedStages'},'right':g} for g in ['D','C','B'][:i+1]]
    clauses += [{'test':'present','left':{'state':record+'.source'}},{'test':'eq','left':{'context':'type'},'right':'fort'}]
    effects.append({'stat':'save','value':3*(i+1),'group':'innate','when':{'all':clauses}})
    slices.append({'id':rid+'/'+grade+'/fortitude','grade':grade,'effectIndexes':[i],
        'scope':'fortitude-save-only; excludes HP, darkness, spellPower, learning and other bundle mechanisms',
        'sourceClause':'本体','requiredRecord':{'learned':True,'version':d['version'],'adoptionStatus':'adopted',
            'qualificationVersion':d['version'],'grade':grade,'completedStages':['D','C','B'][:i+1],
            'source':'必须替换为该角色的实际采用与完整资格核验来源'}})
d['definition']['effects']=effects;auth['runtimeSlices']=slices
for clause in d['clauses']:
    if clause['heading']=='本体':clause['status']='partial';clause['effectStats']=['save']
d['verification']['status']='partial'
path.write_text(encoded(d))
