// Test only declared passive slices against both the shared stacker and actual save consumer.
// Temporary in-memory registration is restored; this script does not install or grant anything.
import fs from 'node:fs';
import path from 'node:path';
import crypto from 'node:crypto';
import assert from 'node:assert/strict';
import {fileURLToPath} from 'node:url';
import {collectEffects,stackEffects} from '../../../../901-tavern/work/rules_engine/resource-effects.mjs';
import {RESOURCE_DEFINITIONS} from '../../../../901-tavern/work/rules_engine/resource-definitions.mjs';
import {saveProfile} from '../../../../901-tavern/work/rules_engine/combat/mechanics.mjs';
import {createOpeningRoster} from '../../../../901-tavern/work/rules_engine/combat/opening.mjs';
const base=path.resolve(path.dirname(fileURLToPath(import.meta.url)),'..'),root=path.resolve(base,'../..');
const hash=x=>crypto.createHash('sha256').update(x).digest('hex');
const sorted=x=>Array.isArray(x)?x.map(sorted):x&&typeof x==='object'?Object.fromEntries(Object.keys(x).sort().map(k=>[k,sorted(x[k])])):x;
const digest=x=>hash(JSON.stringify(sorted(x)));
const report={result:'passed',engineModules:[],slices:{},tests:[]};
// Lock the actual transitive local module closure, excluding generated registries
// whose inclusion would make an executable projection depend on its own hash.
const visited=new Set();
function closure(file){
  file=path.resolve(file);if(visited.has(file)||/resource-(?:data|catalog|action-index)\.mjs$/.test(file))return;
  visited.add(file);const code=fs.readFileSync(file,'utf8');
  report.engineModules.push({path:path.relative(root,file).split(path.sep).join('/'),sha256:hash(fs.readFileSync(file))});
  for(const m of code.matchAll(/(?:from\s*|import\s*)['"]([^'"]+)['"]/g))if(m[1].startsWith('.'))closure(path.resolve(path.dirname(file),m[1]));
}
closure(fileURLToPath(import.meta.url));
const pristine=createOpeningRoster();
for(const file of fs.readdirSync(path.join(base,'execution/contracts')).filter(x=>x.endsWith('.rule.json')).sort()){
  const d=JSON.parse(fs.readFileSync(path.join(base,'execution/contracts',file),'utf8')),auth=d.definition.authoringOnly;
  for(const slice of auth.runtimeSlices){
    const fx=slice.effectIndexes.map(i=>d.definition.effects[i]);
    const expected={D:3,C:6,B:9}[slice.grade]; // Independent source rule: 3G, D/C/B = 1/2/3.
    const cases=[];function run(name,fn){fn();cases.push(name);report.tests.push(slice.id+'/'+name);}
    const actor=structuredClone(pristine.player),baseline=saveProfile(actor,'fort');
    actor.state.learnedResources??={};actor.state.learnedResources[d.id]=structuredClone(slice.requiredRecord);
    const score=(s,type='fort',baseline={})=>stackEffects(collectEffects(s,{[d.id]:{effects:fx}},'save',{type}),baseline).value;
    run('source-rule',()=>assert.ok(fs.readFileSync(path.join(root,d.reading.path),'utf8').includes('强韧+3G内在DP')));
    run('correct-grade-value',()=>assert.equal(score(actor.state),expected));
    run('not-reflex-or-will',()=>{assert.equal(score(actor.state,'reflex'),0);assert.equal(score(actor.state,'will'),0);});
    run('same-group-takes-highest',()=>assert.equal(score(actor.state,'fort',{innate:expected+2}),0));
    run('not-owned',()=>assert.equal(score({}),0));
    for(const [field,bad]of [['version','stale'],['adoptionStatus','candidate'],['qualificationVersion','stale'],['completedStages',[]]]){
      run('reject-'+field,()=>{const s=structuredClone(actor.state);s.learnedResources[d.id][field]=bad;assert.equal(score(s),0);});
    }
    run('actual-saveProfile-and-save-reload',()=>{
      const old=RESOURCE_DEFINITIONS[d.id];RESOURCE_DEFINITIONS[d.id]=d.definition;
      try{const loaded=JSON.parse(JSON.stringify(actor));const before=JSON.stringify(loaded);
        assert.equal(saveProfile(loaded,'fort').dp,baseline.dp+expected);
        assert.equal(JSON.stringify(loaded),before);
      }finally{if(old===undefined)delete RESOURCE_DEFINITIONS[d.id];else RESOURCE_DEFINITIONS[d.id]=old;}
    });
    const fingerprint=digest({slice,effects:fx,version:d.version,reading:d.reading,sharedHash:auth.sharedRulesLock});
    report.slices[slice.id]={result:'passed',fingerprint,testCases:cases};
  }
}
assert.deepEqual(createOpeningRoster(),pristine);
report.testCount=report.tests.length;process.stdout.write(JSON.stringify(report,null,2)+'\n');
