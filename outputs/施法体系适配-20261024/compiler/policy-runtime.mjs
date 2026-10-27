// Pure computations over declared candidate policy. No action spending or XP writes.
import {effectValue} from '../../../../901-tavern/work/rules_engine/resource-effects.mjs';

export function actionPrice(policy,q,{reflex=false}={}){
  if(!Number.isFinite(q)||q<0)throw Error('动作标值须为已确定的非负数');
  q=Math.ceil(q);
  const rows=reflex?policy.reflex:policy.ordinary;
  const row=rows.find(r=>q>=r.minimum&&q<=r.maximum);
  if(row)return {q,...structuredClone(row.result),candidatePolicy:true};
  if(reflex)throw Error('超过12的反射价格未声明，不能自动预支');
  const fullRounds=Math.floor(q/policy.fullRoundPrice),remainder=q%policy.fullRoundPrice;
  return {q,fullRounds,completion:remainder?actionPrice(policy,remainder):null,
    cannotCombineRounds:true,candidatePolicy:true};
}

export function legacyPrice(policy,{grade,points,explicitXP}={}){
  if(explicitXP!==undefined){
    if(!Number.isInteger(explicitXP)||explicitXP<0)throw Error('明价须为非负整数');
    return {xp:explicitXP,basis:'explicit-source-xp',adopted:false};
  }
  const weight=policy.branchWeights[grade];
  if(weight===undefined||!Number.isInteger(points)||points<0)throw Error('缺少实际旧阶位或分数价格');
  return {xp:effectValue(policy.formula,{}, {branchWeight:weight,legacyPoints:points}),basis:'candidate-conversion',adopted:false};
}
