// Source-derived checks of the declarative data. These are not acquisition tests.
import test from 'node:test';
import assert from 'node:assert/strict';
import fs from 'node:fs';
import {effectValue} from '../../../../901-tavern/work/rules_engine/resource-effects.mjs';
const directory=new URL('../execution/contracts/',import.meta.url);
const docs=Object.fromEntries(fs.readdirSync(directory).filter(x=>x.endsWith('.rule.json')).map(x=>{
 const d=JSON.parse(fs.readFileSync(new URL(x,directory),'utf8'));return [d.identity.name,d];
}));
const body=n=>docs[n].definition.authoringOnly.baseMechanisms;
test('selected set retains Arcane Throne and never restores the six excluded bundles',()=>{
 assert.equal(Object.keys(docs).length,33);assert.ok(docs.奥术神座);
 for(const name of ['SEED','恐怖黎明奥术师','现代魔法','生化术士','瘟疫使者','佛说力士移山经'])assert.equal(docs[name],undefined);
});
test('planeswalker power progression replaces totals 1/2/4/8 and does not sum 15',()=>{
 const stages=body('旅法师').stages;
 for(const [grade,expected]of [['C',1],['B',2],['A',4],['S',8]]){
  const fx=stages.find(s=>s.grade===grade).effects.find(e=>e.id==='火花P');
  assert.equal(fx.parameters.value,expected);assert.equal(fx.stacking.mode,'replace-total');
 }
});
test('book study vests capped finite bonuses once, never XP or repeated full grants',()=>{
 const stages=body('魔导书总纲').stages;
 for(const [grade,cap,attribute,dp]of [['D',20,1,3],['C',50,2,6],['SSS',2750,72,144],['九S',7930,216,432]]){
  const s=stages.find(s=>s.grade===grade),a=s.effects.find(e=>e.id==='研读属性兑现').parameters,k=s.effects.find(e=>e.id==='研读知识兑现').parameters;
  const context={confirmedBook:{study:{[grade]:{progress:cap,attributeAlreadyVested:0,knowledgeDPAlreadyVested:0}}}};
  assert.equal(effectValue(a.eachStageEntitlement,{},context),attribute);assert.equal(effectValue(k.stageEntitlement,{},context),dp);
  context.confirmedBook.study[grade].progress=cap*2;
  assert.equal(effectValue(a.eachStageEntitlement,{},context),attribute);
  context.confirmedBook.study[grade].attributeAlreadyVested=attribute;context.confirmedBook.study[grade].knowledgeDPAlreadyVested=dp;
  assert.equal(effectValue(a.delta,{},context),0);assert.equal(effectValue(k.delta,{},context),0);
  assert.equal(a.grantsXP,false);assert.equal(k.grantsXP,false);assert.equal(a.doesNotChangeBaseAttributes,true);
 }
 const d=stages.find(s=>s.grade==='D').effects.find(e=>e.id==='研读知识兑现').parameters;
 assert.equal(effectValue(d.stageEntitlement,{}, {confirmedBook:{study:{D:{progress:10}}}}),1);
});
test('book inheritance is the same acquisition and non-sale 27S grants nothing',()=>{
 const inherited=body('夜天之书').inheritsBaseContract;
 assert.equal(inherited.sameBookAndAcquisition,true);assert.equal(inherited.notAdditionalPoolOrCasterStack,true);
 assert.equal(inherited.resourceId,docs.魔导书总纲.id);
 const stage=body('魔导书总纲').stages.find(s=>s.grade==='二十七S');
 assert.equal(stage.purchasable,false);assert.deepEqual(stage.grants,[]);assert.deepEqual(stage.effects,[]);
});
test('agent D uses two attribute increases and two scoped DP benefits, not a third will attribute',()=>{
 const effects=body('代行者').stages.find(s=>s.grade==='D').effects;
 assert.equal(effects.filter(e=>e.id.startsWith('属性-')).length,2);
 assert.equal(effects.some(e=>e.id==='属性-意志'),false);
 assert.equal(effects.find(e=>e.id==='意志豁免修行').parameters.value,6);
 assert.equal(effects.find(e=>e.id==='神秘驱魔修行').parameters.value,3);
});
test('full bundles and missing-rule branches never enter executable action or automatic acquisition lists',()=>{
 for(const d of Object.values(docs)){
  assert.equal(d.verification.runtimeFullyVerified,false);
  assert.equal(d.definition.authoringOnly.acquisition.autoGrantToT0,false);
  assert.equal(d.definition.authoringOnly.acquisition.treeEntryGrantsChildren,false);
  assert.ok(d.actions.every(a=>a.operation===null&&a.availability==='blocked'&&a.allowsModelNumericEffects===false));
 }
 const issues=Object.values(docs).flatMap(d=>d.unresolvedRules);
 assert.equal(issues.length,11);assert.equal(new Set(issues.map(x=>x.group)).size,4);
});
