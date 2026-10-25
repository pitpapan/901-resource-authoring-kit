#!/usr/bin/env python3
"""Candidate-only 901-resource/1 compiler. Contracts are the sole machine authoring source."""
from pathlib import Path
import argparse,csv,hashlib,json,re,sys
import jsonschema
BASE=Path(__file__).resolve().parents[1];ROOT=BASE.parents[1];OUT=BASE/'execution/generated'
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def digest(v):return hashlib.sha256(json.dumps(v,sort_keys=True,ensure_ascii=False,separators=(',',':')).encode()).hexdigest()
def encoded(v):return json.dumps(v,ensure_ascii=False,sort_keys=True,indent=2)+'\n'
def require(ok,msg):
 if not ok:raise ValueError(msg)
def load():
 schema=json.loads((ROOT/'resources/execution/resource.schema.json').read_text());validator=jsonschema.Draft202012Validator(schema);docs=[]
 for p in sorted((BASE/'execution/contracts').glob('*.rule.json')):
  d=json.loads(p.read_text());validator.validate(d);require(d['schemaVersion']=='901-resource/1','schema')
  source=ROOT/d['reading']['path'];require(source.resolve().is_relative_to(ROOT.resolve()),'reading path escape');require(sha(source)==d['reading']['sha256'],d['id']+': reading stale')
  body=source.read_text();auth=d['definition']['authoringOnly'];require(d['identity']['adoptionStatus']=='candidate','candidate namespace')
  require(not d['verification']['runtimeFullyVerified'],'partial corpus may not be fully verified')
  shared=d['identity']['sharedDependencies'];require(digest(shared)==auth['sharedRulesLock'],d['id']+': shared lock differs')
  for r in shared:require(sha(ROOT/r['path'])==r['sha256'],d['id']+': shared dependency stale '+r['path'])
  ids=set()
  for u in auth['units']:
   require(u['id'] not in ids,'duplicate clause ID');ids.add(u['id']);anchor=u['reading']['anchor'];m=re.search(r'<a id="'+re.escape(anchor)+r'"></a>(.*?)(?=<a id="|\Z)',body,re.S)
   require(m is not None,'missing clause '+anchor);require(hashlib.sha256(m[1].encode()).hexdigest()==u['reading']['sectionSha256'],'clause text stale '+anchor)
   for field in ['learning','actions','requirements','upgrades','target','duration','cooldown','costs','stacking','mechanisms']:require(field in u,'missing structured field '+field)
   for ref in u['sourceReferences']:require(sha(ROOT/ref['path'])==ref['sha256'],'original source stale')
  require(len(d['clauses'])==len(auth['units']),'clause correspondence')
  for a in d['actions']:
   if a['operation'] is None:require(a['availability']=='blocked','unregistered action state')
   else:
    require(a['operation'] in d['definition'].get('programs',{}),'action has no standard program')
    require(a['allowsModelNumericEffects'] is False,'model-provided effects forbidden')
    require(any(x['operation']==a['operation'] for x in auth.get('runtimePrograms',[])),'program lacks verification scope')
  docs.append(d)
 require(len(docs)==268,'candidate contract count');require(len({d['id'] for d in docs})==len(docs),'duplicate resource ID')
 manifest=json.loads((BASE/'execution/source-coverage.json').read_text());reuse=json.loads((BASE/'execution/reuse-map.json').read_text());require(len(manifest['sources'])==192,'192 sources')
 for path,h in manifest['sourceHashes'].items():require(sha(ROOT/path)==h,'source manifest stale '+path)
 for dep in manifest['sharedDependencies']:require(sha(ROOT/dep['path'])==dep['sha256'],'source manifest shared dependency stale '+dep['path'])
 official={json.loads(p.read_text())['id']:json.loads(p.read_text()) for p in (ROOT/'resources/execution').glob('*.rule.json')}
 for r in reuse:
  d=official[r['resourceId']];require(d['version']==r['version'] and d['reading']==r['contractReading'],'reuse contract stale');require(r['curriculumProhibited']==(r['status']=='prohibited'),'prohibition scope')
 used={r['path'] for d in docs for r in d['identity']['sourceReferences']}|{r['source']['path'] for r in reuse}
 require(used==set(manifest['sourceHashes']),'source coverage set')
 return docs,reuse
SUPPORTED_STATS={'check','attack','defense','save','initiative','speed','extraSuccess','willEnhancement','willMax','spellPower','ignoreSpeed'}
def program_fingerprint(d,operation):
 return digest({'learning':d['definition'].get('learning'),'acquisition':d['definition'].get('acquisition'),'program':d['definition']['programs'][operation],'actions':[a for a in d['actions'] if a['operation']==operation],'grade':d['definition'].get('grade'),'subskills':d['definition'].get('subskills'),'requiresAllSchools':d['definition'].get('requiresAllSchools'),'contractVersion':d['version'],'readingHash':d['reading']['sha256'],'sharedHash':d['definition']['authoringOnly']['sharedRulesLock']})
def acquisition_fingerprint(d):
 return digest({'learning':d['definition'].get('learning'),'acquisition':d['definition'].get('acquisition'),'requires':d['definition'].get('requires'),'identity':d['identity'],'grade':d['definition'].get('grade'),'subskills':d['definition'].get('subskills'),'requiresAllSchools':d['definition'].get('requiresAllSchools'),'contractVersion':d['version'],'reading':d['reading'],'sharedHash':d['definition']['authoringOnly']['sharedRulesLock']})
def projection(docs,evidence=None,program_evidence=None,acquisition_evidence=None):
 data={};passives=[];blocked=[];catalog=[];action_index=[];verified_programs=[];verified_acquisitions=[]
 verified=(evidence or {}).get('slices',{})
 for d in docs:
  auth=d['definition']['authoringOnly'];catalog.append({'resourceId':d['id'],'version':d['version'],'identity':d['identity'],'reading':d['reading'],'units':auth['units'],'inputs':d['inputs'],'verification':d['verification'],'unresolvedRules':d['unresolvedRules'],'implementationGaps':d['implementationGaps']})
  acquisition_proof=(acquisition_evidence or {}).get('acquisitions',{}).get(d['id'])
  acquisition_verified=bool(acquisition_proof and acquisition_proof['result']=='passed' and acquisition_proof['fingerprint']==acquisition_fingerprint(d))
  if acquisition_verified:
   require(not d['unresolvedRules'],'unresolved acquisition cannot be promoted')
   verified_acquisitions.append({'resourceId':d['id'],'verifiedScope':auth['runtimeAcquisition']['verifiedScope'],'testCases':acquisition_proof['testCases']})
  catalog[-1]['learningVerification']={'status':'execution-verified' if acquisition_verified else 'unverified','requiresRegisteredOffer':True,'route':'resource'}
  accepted={};covered_units=set()
  for scope in auth.get('runtimePrograms',[]):
   operation=scope['operation'];proof=(program_evidence or {}).get('programs',{}).get(d['id']+'/'+operation)
   if proof and proof['result']=='passed' and proof['fingerprint']==program_fingerprint(d,operation):
    require(not d['unresolvedRules'],'unresolved program cannot be promoted')
    accepted[operation]=d['definition']['programs'][operation];covered_units.update(scope['clauseIds']);verified_programs.append({'resourceId':d['id'],'operation':operation,'verifiedScope':scope['verifiedScope'],'testCases':proof['testCases']})
  if accepted:
   actions=[dict(a,availability='execution-verified') for a in d['actions'] if a['operation'] in accepted]
   action_index.append({'resourceId':d['id'],'version':d['version'],'name':d['identity']['name'],'adoptionStatus':d['identity']['adoptionStatus'],'reading':d['reading'],'sourceChecked':True,'actions':actions,'status':'partial','runtimeFullyVerified':False,'verifiedScope':'declared-programs-and-registered-offer-acquisition' if acquisition_verified else 'declared-programs-only; acquisition-excluded','implementationGaps':d['implementationGaps'],'unresolvedRules':d['unresolvedRules']})
   if acquisition_verified:action_index[-1]['learning']={'action':'resource','availability':'execution-verified','requiresRegisteredOffer':True,'requestFields':['actorId','offerId','paymentId'],'allowsModelNumericEffects':False,'contractVersion':d['version']}
  for u in auth['units']:
   if u['id'] in covered_units and not u['implementationGaps']:continue
   blocked.append({'resourceId':d['id'],'clauseId':u['id'],'name':u['name'],'reading':u['reading'],'availability':'blocked','operation':None,'allowsModelNumericEffects':False,'gapCodes':u['implementationGaps'] or ['program-runtime-proof-not-current'],'unresolvedRuleIds':u['unresolvedRuleIds'],'actionCost':u['actions'],'mayPlanSelection':True,'mayExecute':False})
  chosen=[]
  for s in auth['runtimeSlices']:
   sid=s['id'];indexes=s['effectIndexes'];effects=[d['definition']['effects'][i] for i in indexes];proof=verified.get(sid)
   expected=digest({'slice':{k:v for k,v in s.items() if k!='verification'},'effects':effects,'contractVersion':d['version'],'readingHash':d['reading']['sha256'],'sharedHash':auth['sharedRulesLock']})
   require(all(e['stat'] in SUPPORTED_STATS for e in effects),'unknown runtime stat')
   for e in effects:
    conditions=e.get('when',{}).get('all',[]);render=json.dumps(conditions,ensure_ascii=False)
    for token in ['version','grade','adoptionStatus','qualificationVersion']:require(token in render,'missing passive gate '+token)
   if proof and proof['fingerprint']==expected and proof['result']=='passed':
    require(not s.get('unresolvedRuleIds'),'unresolved slice promoted');chosen.extend(indexes)
    passives.append({'resourceId':d['id'],'sliceId':sid,'clauseId':s['clauseId'],'scope':'verified-passive-fragment','effectIndexes':indexes,'testCases':proof['testCases']})
   else:blocked.append({'resourceId':d['id'],'sliceId':sid,'name':s['name'],'availability':'blocked','operation':None,'gapCodes':['passive-runtime-test-not-current'],'mayExecute':False})
  if chosen or accepted or acquisition_verified:
   data[d['id']]={k:v for k,v in d['definition'].items() if k not in ['authoringOnly','effects','programs']}
   if d['definition'].get('learning',{}).get('policy') and not acquisition_verified:data[d['id']].pop('learning',None)
   data[d['id']].update(effects=[d['definition']['effects'][i] for i in sorted(set(chosen))],programs=accepted,identity=d['identity'],contractVersion=d['version'],readingHash=d['reading']['sha256'],reading=d['reading'],verification={'status':'partial','sourceChecked':True,'runtimeFullyVerified':False,'verifiedScope':'registered-offer-acquisition-and-programs' if acquisition_verified else 'programs-and-selected-passive-fragments' if accepted else 'collectEffects-only'},operations=list(accepted))
 return data,passives,blocked,catalog,action_index,verified_programs,verified_acquisitions
def build(docs,reuse,evidence=None,program_evidence=None,acquisition_evidence=None):
 if evidence:
  engine=(ROOT.parent/'901-tavern/work/rules_engine/resource-effects.mjs').resolve()
  require((ROOT/evidence['engine']['path']).resolve()==engine,'unexpected effect executor proof path')
  require(sha(engine)==evidence['engine']['sha256'],'runtime executor changed; rerun collectEffects tests before promotion')
 if program_evidence:
  for module in program_evidence['engineModules']:
   require(sha(ROOT/module['path'])==module['sha256'],'program executor or test changed; execution proof stale: '+module['path'])
 if acquisition_evidence:
  for module in acquisition_evidence['engineModules']:
   require(sha(ROOT/module['path'])==module['sha256'],'learning executor or test changed; acquisition proof stale: '+module['path'])
 data,passives,blocked,catalog,action_index,verified_programs,verified_acquisitions=projection(docs,evidence,program_evidence,acquisition_evidence)
 counts={'candidateContracts':len(docs),'structuredUnits':sum(len(d['definition']['authoringOnly']['units']) for d in docs),'structuredMechanismFragments':sum(len(u['mechanisms']) for d in docs for u in d['definition']['authoringOnly']['units']),'sourceCount':192,'officialReuseRecords':len(reuse),'officialUniqueIDs':len({r['resourceId'] for r in reuse}),'verifiedPassiveSlices':len(passives),'verifiedPassiveEffects':sum(len(v['effects']) for v in data.values()),'runnableActionWhitelist':sum(len(x['actions']) for x in action_index),'verifiedPrograms':len(verified_programs),'verifiedAcquisitionTransactions':len(verified_acquisitions),'fullyExecutableCandidateContracts':0,'allSemanticsEncoded':False,'blockedUnits':len([x for x in blocked if x.get('clauseId')]),'blockedActionIntents':sum(len(d['actions']) for d in docs)-sum(len(x['actions']) for x in action_index),'unresolvedRuleCount':len({r['parameter'] for d in docs for r in d['unresolvedRules']})}
 warning='// Generated from 901-resource/1 candidate contracts; do not edit. No adoption or installation implied.\n'
 artifacts={'resource-data.mjs':warning+'export const RESOURCE_DATA='+json.dumps(data,ensure_ascii=False,separators=(',',':'))+';\n','resource-action-index.mjs':warning+'export const RESOURCE_ACTION_INDEX='+json.dumps(action_index,ensure_ascii=False,separators=(',',':'))+';\n','resource-blocked-index.mjs':warning+'export const RESOURCE_BLOCKED_INDEX='+json.dumps(blocked,ensure_ascii=False,separators=(',',':'))+';\n','resource-contract-index.mjs':warning+'export const RESOURCE_CONTRACT_INDEX='+json.dumps(catalog,ensure_ascii=False,separators=(',',':'))+';\n','coverage.json':encoded({'counts':counts,'passiveSlices':passives,'verifiedPrograms':verified_programs,'verifiedAcquisitions':verified_acquisitions,'reuseReferences':reuse,'contractFingerprints':{d['id']:digest(d) for d in docs}})}
 return artifacts,counts
if __name__=='__main__':
 ap=argparse.ArgumentParser();ap.add_argument('--check',action='store_true',help='read-only deterministic artifact validation');a=ap.parse_args()
 docs,reuse=load();proof=BASE/'execution/runtime-verification.json';evidence=json.loads(proof.read_text()) if proof.exists() else None
 program_proof=BASE/'execution/program-verification.json';program_evidence=json.loads(program_proof.read_text()) if program_proof.exists() else None
 acquisition_proof=BASE/'execution/acquisition-verification.json';acquisition_evidence=json.loads(acquisition_proof.read_text()) if acquisition_proof.exists() else None
 artifacts,counts=build(docs,reuse,evidence,program_evidence,acquisition_evidence)
 for name,text in artifacts.items():
  p=OUT/name
  if a.check:require(p.exists() and p.read_text()==text,'generated artifact stale '+name)
  else:p.write_text(text)
 print(json.dumps({'result':'PASS','mode':'read-only-check' if a.check else 'compile','counts':counts},ensure_ascii=False))
