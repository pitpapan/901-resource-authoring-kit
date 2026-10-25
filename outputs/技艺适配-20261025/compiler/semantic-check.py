#!/usr/bin/env python3
"""Focused source-derived regression checks; no contract or state writes."""
import json
from pathlib import Path

BASE = Path(__file__).resolve().parents[1]
DOCS = [json.loads(p.read_text()) for p in (BASE / 'execution/contracts').glob('*.rule.json')]

def unit(name, anchor):
    doc = next(d for d in DOCS if d['identity']['name'] == name)
    return next(u for u in doc['definition']['authoringOnly']['units'] if u['reading']['anchor'] == anchor)

def values(u, field):
    return [x['value'] for x in u[field]['value'] if x.get('value') is not None]

def check():
    cases = []
    costs = values(unit('无面者', '条目'), 'costs')
    assert [(x['kind'], x['amount']) for x in costs] == [('capacity-cost', 3), ('pool-cost', 3)], '无面者：上限支付不能变成普通余额支付'
    assert costs[0]['scope'] != costs[1]['scope'], '变身与问答分别计费'
    cases.append('capacity-cost-is-not-balance-cost')

    costs = values(unit('引导能量', 'L6'), 'costs')
    assert not any(x['kind'] == 'pool-cost' for x in costs), '引导能量：被替代能耗不是额外扣能量'
    substitution = next(x for x in costs if x['kind'] == 'energy-substitution')
    assert substitution['refund'] is False and substitution['otherCostsUnchanged'] is True
    assert substitution['statusPerReplacedPoint'] == {'type': '晕眩', 'points': 1, 'unavoidable': True, 'recovery': 'long-rest-only'}
    cases.append('energy-substitution-does-not-charge-or-refund-energy')

    u = unit('尘埃剑典', '条目')
    predicates = [p for r in u['requirements']['all'] for p in r.get('predicates', [])]
    assert any(p.get('kind') == 'energy-pool-absent' and p['name'] == '剑气' for p in predicates), '尘埃剑典：没有剑气不可反转成需要气'
    pool = next(p for p in predicates if p.get('kind') == 'energy-pool-exists')
    assert pool['generic'] is True and pool['keyAttributeCategory'] == 'physical' and not pool.get('names')
    cases.append('negative-prerequisite-and-qualified-pool')

    u = unit('左右互搏术', 'L6')
    prices = u['learning']['prices']
    assert {(p['purpose'], p['amount']) for p in prices} == {('base-two-hands', 30), ('evolve-two-hands', 30)} and len(prices) == 2
    additions = u['learning']['additionalHandPrices']
    assert {x['purpose'] for x in additions} == {'add-hand', 'evolve-added-hand'}
    for x in additions:
        assert x['formula'] == {'op': 'mul', 'args': [30, {'op': 'sub', 'args': [{'context': 'handNumber'}, 1]}]}
    assert u['actions']['sharedActionCost'] == ['standard'] and u['actions']['maximumUsesPerRound'] == 1
    cases.append('separate-learning-evolution-and-linear-extra-hands')

    for d in DOCS:
        for u in d['definition']['authoringOnly']['units']:
            for row in u['requirements']['all']:
                for p in row.get('predicates', []):
                    if p.get('kind') == 'energy-pool-exists':
                        assert p.get('generic') is not False, '原文未写通用不等于要求非通用池'
    p = next(p for r in unit('紫薇玄鉴', '条目')['requirements']['all'] for p in r.get('predicates', []) if p.get('kind') == 'energy-pool-exists')
    assert p['nameMatch'] == 'all' and p['minimumPoolCount'] == 2
    p = next(p for r in unit('天位力量', 'L9')['requirements']['all'] for p in r.get('predicates', []) if p.get('kind') == 'energy-pool-exists')
    assert p['minimumGrade'] == 'A' and p['bindAtAcquisition'] is True
    cases.append('pool-qualifications-preserve-all-and-grade')

    u = unit('fate系列通用技能', 'L70')
    assert [p['amount'] for p in u['learning']['prices']] == [35, 85, 215, 565], '皇帝特权：临时能力额度不是购买价'
    assert [x['maximumXP'] for x in u['selectionBudgets']] == [10, 25, 65, 175]
    assert all(x['chargesXP'] is False for x in u['selectionBudgets'])
    cases.append('temporary-selection-budget-is-not-learning-price')

    for name, anchor, target in [('残暴驭手', 'L9', 'mount'), ('符咒之术', 'L51', 'talisman-recipient')]:
        modifiers = [x for x in unit(name, anchor)['mechanisms'] if x.get('kind') == 'numeric-modifier']
        assert modifiers and all(x['target'] == target for x in modifiers), '受益者不能机械默认为自己'
    costs = values(unit('符咒之术', 'L51'), 'costs')
    assert {(x['pool'], x['amount']) for x in costs} == {('道力', 3), ('意志', 3)}
    assert all(x['optional'] and x['phase'] == 'augment' and x['paymentGroup'] == 'extend-to-24-hours' for x in costs)
    cases.append('effect-recipient-and-coupled-optional-cost')

    costs = values(unit('神灭斩', '术018'), 'costs')
    assert [(x['phase'], x['amount']) for x in costs] == [('activate', 7), ('maintain', 7), ('augment', 7)]
    assert costs[1]['trigger'] == 'own-turn-start' and costs[1]['decline'] == 'end-spell' and costs[2]['optional']
    assert costs[2]['changesMaintenanceCost'] is False
    cases.append('activation-maintenance-and-augmentation-are-separate')

    costs = values(unit('奥术弹幕', '术014'), 'costs')
    assert costs[0]['amount'] == 7 and costs[0]['phase'] == 'activate'
    assert costs[1]['amount'] == 2 and costs[1]['optional']
    assert costs[1]['maximumRepetitions'] == {'op': 'sub', 'args': [{'context': 'highestCasterLevel'}, 1]}
    cases.append('optional-repeat-augmentation-has-a-limit')

    doc = next(d for d in DOCS if d['identity']['name'] == '截天七剑')
    assert all(u['upgrades']['mode'] == 'independent' for u in doc['definition']['authoringOnly']['units'])
    assert unit('截天七剑', '条目')['requirements']['applicationScope'] == 'use-not-acquisition'
    cases.append('independent-techniques-do-not-gain-stage-prerequisites')

    for name, anchor, cap in [('完好如初', '术109', {'context': 'P'}), ('治疗微伤', '术127', {'op': 'mul', 'args': [{'context': 'highestCasterLevel'}, 2]})]:
        costs = values(unit(name, anchor), 'costs')
        assert costs[0]['amount'] == 0 and costs[0]['phase'] == 'activate'
        assert costs[1]['optional'] and costs[1]['phase'] == 'augment' and costs[1]['maximumAmount'] == cap
    cases.append('free-base-spells-retain-paid-optional-augmentation')
    return {'result': 'PASS', 'sourceRuleCases': cases, 'writes': 0}

if __name__ == '__main__':
    print(json.dumps(check(), ensure_ascii=False))
