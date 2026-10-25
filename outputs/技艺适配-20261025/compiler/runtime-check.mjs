// Read-only tests against the actual shared JS effect executor. No registry writes.
import assert from 'node:assert/strict';
import fs from 'node:fs';
import path from 'node:path';
import crypto from 'node:crypto';
import {fileURLToPath,pathToFileURL} from 'node:url';
const BASE=path.resolve(path.dirname(fileURLToPath(import.meta.url)),'..');
const ROOT=path.resolve(BASE,'../..');
const enginePath=path.resolve(ROOT,'../901-tavern/work/rules_engine/resource-effects.mjs');
const {collectEffects,stackEffects,effectValue}=await import(pathToFileURL(enginePath));
const stable=x=>Array.isArray(x)?x.map(stable):x&&typeof x==='object'?Object.fromEntries(Object.keys(x).sort().map(k=>[k,stable(x[k])])):x;
const hash=x=>crypto.createHash('sha256').update(typeof x==='string'?x:JSON.stringify(stable(x))).digest('hex');
const docs=fs.readdirSync(path.join(BASE,'execution/contracts')).filter(x=>x.endsWith('.rule.json')).sort().map(x=>JSON.parse(fs.readFileSync(path.join(BASE,'execution/contracts',x),'utf8')));
const report={result:'passed',engine:{path:enginePath,sha256:hash(fs.readFileSync(enginePath,'utf8'))},slices:{},assertionCases:[]};
function test(name,fn){fn();report.assertionCases.push(name);}
for(const d of docs){
 const auth=d.definition.authoringOnly;
 for(const slice of auth.runtimeSlices){
  const fx=slice.effectIndexes.map(i=>d.definition.effects[i]);
  const definition={effects:fx,ownership:d.definition.ownership};const defs={[d.id]:definition};
  const records={};
  for(const sibling of auth.runtimeSlices){records[sibling.stageResourceId]=structuredClone(sibling.requiredAcquisitionRecord);if(sibling.id===slice.id)break;}
  const qualified={learnedResources:records};
  const score=(state,stat='attack',baseline={})=>stackEffects(collectEffects(state,defs,stat),baseline).value;
  // Independent reading-rule oracle: do not derive the expected bonus from
  // the very effect data being tested (that would accept wrong low-tier values).
  const expected={D:3,C:9,B:21,A:45}[slice.grade];
  const first=report.assertionCases.length;
  test(slice.id+'/eligible-attack',()=>assert.equal(score(qualified),expected));
  test(slice.id+'/eligible-defense',()=>assert.equal(score(qualified,'defense'),expected));
  test(slice.id+'/not-owned',()=>assert.equal(score({learnedResources:{}}),0));
  test(slice.id+'/collection-learned-is-insufficient',()=>assert.equal(score({learnedResources:{[d.id]:{learned:true,grade:'A',version:d.version}}}),0));
  test(slice.id+'/bare-stage-learned-is-insufficient',()=>assert.equal(score({learnedResources:{[slice.stageResourceId]:{learned:true}}}),0));
  for(const [key,bad]of [['version','old-version'],['grade','S'],['adoptionStatus','candidate'],['qualificationVersion','stale']]){
   test(slice.id+'/reject-'+key,()=>{const s=structuredClone(qualified);s.learnedResources[slice.stageResourceId][key]=bad;assert.equal(score(s),0);});
  }
  test(slice.id+'/same-group-higher-baseline',()=>assert.equal(score(qualified,'attack',{insight:expected+5}),0));
  test(slice.id+'/same-group-lower-baseline',()=>assert.equal(score(qualified,'attack',{insight:1}),expected-1));
  if(slice.stagePrerequisites.length)test(slice.id+'/cross-tier-without-prerequisite',()=>{const s=structuredClone(qualified);delete s.learnedResources[slice.stagePrerequisites[0]];assert.equal(score(s),0);});
  test(slice.id+'/no-state-write',()=>{const before=JSON.stringify(qualified);score(qualified);assert.equal(JSON.stringify(qualified),before);});
  const fingerprint=hash({slice:Object.fromEntries(Object.entries(slice).filter(([k])=>k!=='verification')),effects:fx,contractVersion:d.version,readingHash:d.reading.sha256,sharedHash:auth.sharedRulesLock});
  report.slices[slice.id]={result:'passed',fingerprint,testCases:report.assertionCases.slice(first)};
 }
 if(auth.runtimeSlices.length){
  test(d.id+'/reading-rule-values',()=>{
   const reading=fs.readFileSync(path.join(ROOT,d.reading.path),'utf8');
   assert.ok(reading.includes('攻击和防御上获得3/9/21/45点洞察加值。各级间数值替换。'));
  });
  const records=Object.fromEntries(auth.runtimeSlices.map(s=>[s.stageResourceId,structuredClone(s.requiredAcquisitionRecord)]));
  test(d.id+'/all-tiers-replace-not-sum',()=>assert.equal(stackEffects(collectEffects({learnedResources:records},{[d.id]:d.definition},'attack')).value,45));
 }
}
test('formula-effective-attribute-context',()=>assert.equal(effectValue({op:'mul',args:[10,{context:'INT'},{context:'P'}]},{attributes:{智力:3}},{INT:8,P:24}),1920));
report.assertionCount=report.assertionCases.length;
process.stdout.write(JSON.stringify(report,null,2)+'\n');
