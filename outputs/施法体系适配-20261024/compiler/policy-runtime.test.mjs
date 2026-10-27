import test from 'node:test';
import assert from 'node:assert/strict';
import fs from 'node:fs';
import {actionPrice,legacyPrice} from './policy-runtime.mjs';
const contract=JSON.parse(fs.readFileSync(new URL('../execution/shared.rule.json',import.meta.url),'utf8'));
const p=contract.definition.authoringOnly.policies;
test('fixed action q is converted once and never creates an AP pool',()=>{
  assert.deepEqual(actionPrice(p.actionPrice,6).spend,{standard:1});
  assert.deepEqual(actionPrice(p.actionPrice,8).spend,{standard:1,swift:1});
  assert.deepEqual(actionPrice(p.actionPrice,10).spend,{standard:1,move:1});
  assert.deepEqual(actionPrice(p.actionPrice,12).spend,{standard:1,move:1,swift:1});
  assert.deepEqual(actionPrice(p.actionPrice,3).spend,{move:1});
  assert.deepEqual(actionPrice(p.actionPrice,0).spend,{});
  assert.deepEqual(actionPrice(p.actionPrice,2.1).spend,{move:1});
  const q14=actionPrice(p.actionPrice,14);assert.equal(q14.fullRounds,1);assert.deepEqual(q14.completion.spend,{swift:1});
  const q36=actionPrice(p.actionPrice,36);assert.equal(q36.fullRounds,3);assert.equal(q36.completion,null);
});
test('reflex surcharge remains a future action debt and retains its lock',()=>{
  const q4=actionPrice(p.actionPrice,4,{reflex:true});
  assert.deepEqual(q4.spend,{reflex:1});assert.deepEqual(q4.nextTurnDebt,{move:1});
  assert.equal(q4.reflexLock,'through-next-action-end');
  assert.throws(()=>actionPrice(p.actionPrice,13,{reflex:true}),/未声明/);
});
test('candidate prices preserve explicit XP and do not reinterpret material currency or grant resources',()=>{
  assert.equal(legacyPrice(p.learningPrice,{grade:'D',points:500}).xp,10);
  assert.equal(legacyPrice(p.learningPrice,{grade:'C',points:1000}).xp,25);
  assert.equal(legacyPrice(p.learningPrice,{grade:'B',points:2000}).xp,65);
  assert.equal(legacyPrice(p.learningPrice,{grade:'A',points:4000}).xp,175);
  assert.equal(legacyPrice(p.learningPrice,{grade:'S',points:8000}).xp,485);
  assert.equal(legacyPrice(p.learningPrice,{grade:'C',points:2000,explicitXP:22}).xp,22);
  assert.equal(legacyPrice(p.learningPrice,{grade:'D',points:1}).xp,6);
  assert.throws(()=>legacyPrice(p.learningPrice,{grade:'D'}),/缺少/);
  assert.equal(legacyPrice(p.learningPrice,{grade:'D',points:500}).adopted,false);
});
