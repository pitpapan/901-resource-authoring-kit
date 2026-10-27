import copy
import unittest
from compile_resources import validate_program

class ProgramValidation(unittest.TestCase):
    def program(self):
        return {'effectComponents': {'mind': {'families': ['mind'], 'gradeBonus': 1}}, 'steps': [
            {'op': 'save', 'component': 'mind', 'type': 'will', 'resolve': {'kind': 'opposed', 'active': {'context': 'cast'}}, 'resultAs': 'opposition'},
            {'op': 'status', 'component': 'mind', 'type': '恐惧', 'points': {'context': 'opposition.margin'}, 'resistance': {'receipt': 'opposition', 'kind': 'resolved'}}]}

    def test_death_program_cannot_reuse_a_periodic_save_receipt(self):
        trigger = {'op': 'trigger', 'event': 'turnStart', 'steps': [{'op': 'save', 'type': 'fort'}],
                   'onDeath': {'radius': 10, 'excludeCaster': True,
                               'steps': [{'op': 'damage', 'amount': {'context': 'save'}, 'severity': 'L', 'energy': 'corrosion'}]}}
        with self.assertRaisesRegex(ValueError, 'save'):
            validate_program({'steps': [trigger]}, 'death-receipts')
        trigger['onDeath']['steps'].insert(0, {'op': 'save', 'type': 'fort'})
        validate_program({'steps': [trigger]}, 'death-receipts')

    def test_additional_damage_event_scope_and_spell_resistance_policy(self):
        extra = {'op': 'additionalDamage', 'amount': 4, 'mode': 'same-type'}
        for program in [{'steps': [extra]}, {'steps': [{'op': 'trigger', 'event': 'turnStart', 'steps': [extra]}]},
                        {'steps': [{'op': 'trigger', 'event': 'attackDamageCaused', 'steps': [{'op': 'damage', 'amount': 4}]}]},
                        {'spellResistance': 'invented', 'steps': []}]:
            with self.subTest(program=program), self.assertRaises(ValueError): validate_program(program, 'event-scope')
        validate_program({'spellResistance': 'ignore', 'steps': [{'op': 'trigger', 'event': 'attackDamageCaused', 'steps': [extra]}]}, 'event-scope')

    def test_other_operations_check_fields_and_item_consumers(self):
        for step in [
            {'op': 'damage', 'amount': True},
            {'op': 'trigger', 'event': 'invented', 'steps': []},
            {'op': 'counter', 'path': 'will.current', 'amount': -1, 'maximunPath': 'will.max'},
            {'op': 'weaponEffect', 'effects': [{'stat': 'defense', 'value': 2}]},
            {'op': 'aura', 'radius': 5, 'effects': [{'stat': 'imaginaryDefense', 'value': 2}]},
        ]:
            with self.subTest(step=step), self.assertRaises(ValueError):
                validate_program({'steps': [step]}, 'typed-operations')
        validate_program({'steps': [{'op': 'weaponEffect', 'effects': [{'stat': 'weaponDamage', 'value': 2}]}]}, 'item-only')

    def test_selected_status_source_value_is_target_local_and_ordered(self):
        p = {'steps': [{'op': 'statusSource', 'type': '燃烧', 'asValue': 'consumedPoints'},
                       {'op': 'damage', 'amount': {'context': 'consumedPoints'}}]}
        validate_program(p, 'selected-status')
        p['steps'].reverse()
        with self.assertRaisesRegex(ValueError, 'earlier target-local producer'):
            validate_program(p, 'selected-status')

    def test_actual_resistance_shape_and_component(self):
        validate_program(self.program(), 'isolated-rule')

    def test_unknown_component_cannot_be_silently_ignored(self):
        p = self.program(); p['steps'][1]['component'] = 'missing'
        with self.assertRaisesRegex(ValueError, 'component'): validate_program(p, 'isolated-rule')

    def test_resistance_requires_an_earlier_receipt_for_same_component(self):
        for mutation in ['before', 'missing', 'cross_component']:
            p = self.program()
            if mutation == 'before': p['steps'].reverse()
            if mutation == 'missing': p['steps'][1]['resistance']['receipt'] = 'not-rolled'
            if mutation == 'cross_component':
                p['effectComponents']['other'] = {'families': ['curse']}; p['steps'][1]['component'] = 'other'
            with self.assertRaisesRegex(ValueError, 'receipt'): validate_program(p, 'isolated-rule')

    def test_unimplemented_lifecycle_and_immunity_policy_fail_compilation(self):
        p = self.program(); p['effectComponents']['mind']['mode'] = 'guess-half'
        with self.assertRaisesRegex(ValueError, 'immunity'): validate_program(p, 'isolated-rule')
        p = self.program(); p['steps'][1]['immunityLifecycle'] = 'suppress'
        with self.assertRaisesRegex(ValueError, 'lifecycle'): validate_program(p, 'isolated-rule')

    def test_explicit_subtraction_rate_and_conditional_receipt(self):
        p = self.program(); p['steps'][1]['resistance'] = {'receipt': 'opposition', 'kind': 'subtract'}
        with self.assertRaisesRegex(ValueError, 'perSuccess'): validate_program(p, 'isolated-rule')
        p = self.program(); p['steps'][0]['when'] = {'test': 'eq', 'left': 1, 'right': 2}
        with self.assertRaisesRegex(ValueError, 'conditional'): validate_program(p, 'isolated-rule')
        p['steps'][1]['when'] = copy.deepcopy(p['steps'][0]['when'])
        validate_program(p, 'isolated-rule')

    def test_lifecycles_are_explicit_and_have_actual_consumers(self):
        for op, lifecycle in [('effect', 'suppress'), ('aura', 'suppress'), ('trigger', 'suppress'), ('status', 'suppress-existing')]:
            p = self.program()
            p['steps'] = [{'op': op, 'component': 'mind', 'immunityLifecycle': lifecycle, **({'effects': []} if op == 'effect' else {'type': '恐惧', 'points': 1} if op == 'status' else {'radius': 5} if op == 'aura' else {'event': 'turnStart', 'steps': []})}]
            validate_program(p, 'isolated-rule')
        p['steps'][0]['immunityLifecycle'] = 'suppress'
        with self.assertRaisesRegex(ValueError, 'lifecycle'): validate_program(p, 'isolated-rule')

    def test_partial_trigger_and_aura_pool_lifecycles_remain_explicit_gaps(self):
        p = self.program(); p['effectComponents']['mind']['mode'] = 'fraction-unblocked'
        p['steps'] = [{'op': 'trigger', 'component': 'mind', 'immunityLifecycle': 'suppress', 'steps': []}]
        with self.assertRaisesRegex(ValueError, 'not implemented'): validate_program(p, 'isolated-rule')
        p['steps'] = [{'op': 'aura', 'component': 'mind', 'immunityLifecycle': 'suppress', 'temporaryAllocation': {'key': 'actual'}}]
        with self.assertRaisesRegex(ValueError, 'not implemented'): validate_program(p, 'isolated-rule')

    def test_registered_exclusive_policy_and_physical_action_consumers(self):
        p = {'steps': [{'op': 'effect', 'effects': [], 'exclusiveGroup': 'haste', 'exclusivePolicy': 'recipient-choice',
                        'actionPrice': {'family': 'physical', 'baseByAction': {'weaponAttack': 5, 'move': 4},
                                        'discount': 2, 'minimumAP': 1, 'perRound': 1, 'quotaKey': 'haste'}}]}
        validate_program(p, 'isolated-rule')
        invalid = copy.deepcopy(p); invalid['steps'][0]['exclusivePolicy'] = 'newest-wins'
        with self.assertRaisesRegex(ValueError, 'exclusive'): validate_program(invalid, 'isolated-rule')
        invalid = copy.deepcopy(p); invalid['steps'][0]['actionPrice']['baseByAction']['cast'] = 5
        with self.assertRaisesRegex(ValueError, 'unregistered'): validate_program(invalid, 'isolated-rule')

    def test_accumulation_and_wound_policies_have_explicit_consumers(self):
        p = {'target': 'self', 'toggle': 'on', 'steps': [
            {'op': 'damage', 'amount': 1, 'recovery': 'aggravated'},
            {'op': 'accumulate', 'key': 'test', 'amount': 1, 'thresholdAttribute': '力量', 'conditionMinutes': 480, 'resetAfterRestMinutes': 480}]}
        validate_program(p, 'isolated-rule')
        invalid = copy.deepcopy(p); invalid['steps'][1]['resetAfterRestMinutes'] = 0
        with self.assertRaisesRegex(ValueError, 'duration'): validate_program(invalid, 'isolated-rule')
        invalid = copy.deepcopy(p); invalid['steps'][0]['recovery'] = 'erase-on-upgrade'
        with self.assertRaisesRegex(ValueError, 'wound'): validate_program(invalid, 'isolated-rule')

    def test_scene_limited_initiative_requires_real_effect_consumer(self):
        p = {'effectComponents': {'mind': {'families': ['mind']}}, 'steps': [{'op': 'effect', 'scene': True, 'targetSceneLimit': 1,
             'turnOrder': 'after-caster-turn', 'effects': [{'stat': 'currentInitiative', 'value': 4}],
             'component': 'mind', 'immunityLifecycle': 'suppress', 'initialBlocked': 'discard'}]}
        validate_program(p, 'isolated-rule')
        for field, value in [('turnOrder', 'immediately'), ('scene', False), ('targetSceneLimit', 0), ('initialBlocked', 'silently-apply'), ('effects', [])]:
            invalid = copy.deepcopy(p); invalid['steps'][0][field] = value
            with self.assertRaises(ValueError): validate_program(invalid, 'isolated-rule')

    def test_status_budget_and_flight_end_policies_require_live_consumers(self):
        p = {'steps': [
            {'op': 'removeStatus', 'types': ['恐惧', '沮丧'], 'budgetScope': 'type', 'amount': 6},
            {'op': 'capability', 'id': 'flight', 'movement': {'mode': 'flight', 'maneuverability': 'perfect', 'speed': 180},
             'onEnd': {'kind': 'descent', 'rounds': 6, 'metersPerRound': 20, 'intervalMinutes': .1}}]}
        validate_program(p, 'isolated-rule')
        invalid = copy.deepcopy(p); invalid['steps'][0]['budgetScope'] = 'each-source'
        with self.assertRaisesRegex(ValueError, 'budget'): validate_program(invalid, 'isolated-rule')
        invalid = copy.deepcopy(p); invalid['steps'][1]['movement']['maneuverability'] = 'average'
        with self.assertRaisesRegex(ValueError, 'movement'): validate_program(invalid, 'isolated-rule')
        invalid = copy.deepcopy(p); invalid['steps'][1]['onEnd']['intervalMinutes'] = 0
        with self.assertRaisesRegex(ValueError, 'termination'): validate_program(invalid, 'isolated-rule')

    def test_operation_inputs_use_shared_types_and_reject_ignored_fields(self):
        for step, field in [
            ({'op': 'heal', 'amount': 3, 'ratios': {'L': True}}, 'ratios'),
            ({'op': 'heal', 'amount': 3, 'recipient': 'everyone'}, 'recipient'),
            ({'op': 'status', 'type': '恐惧', 'points': 3, 'durationRound': 2}, 'durationRound'),
            ({'op': 'effect', 'effects': [{'stat': 'defense', 'value': 2}], 'scene': 'true'}, 'scene'),
            ({'op': 'status', 'type': '恐惧'}, 'points')]:
            with self.subTest(field=field), self.assertRaisesRegex(ValueError, field):
                validate_program({'steps': [step]}, 'isolated-rule')

    def test_effects_require_registered_consumers_and_receipt_fields_require_producers(self):
        with self.assertRaisesRegex(ValueError, 'consumer'):
            validate_program({'steps': [{'op': 'effect', 'effects': [{'stat': 'imaginaryDefense', 'value': 3}]}]}, 'isolated-rule')
        p = self.program(); p['steps'][1]['points'] = {'context': 'opposition.nonexistent'}
        with self.assertRaisesRegex(ValueError, 'nonexistent'): validate_program(p, 'isolated-rule')
        p = self.program(); p['steps'][1].pop('resistance'); p['steps'].reverse()
        with self.assertRaisesRegex(ValueError, 'opposition'): validate_program(p, 'isolated-rule')

    def test_receipt_type_cannot_feed_boolean_success_into_numeric_points(self):
        p = self.program(); p['steps'][1]['points'] = {'op': 'mul', 'args': [2, {'context': 'opposition.success'}]}
        with self.assertRaisesRegex(ValueError, 'boolean.*number'): validate_program(p, 'isolated-rule')
        p['steps'][1]['points'] = {'op': 'mul', 'args': [2, {'context': 'opposition.margin'}]}
        validate_program(p, 'isolated-rule')

    def test_consumer_report_preserves_passive_gaps_and_rejects_wrong_execution_scope(self):
        from operation_contracts import inspect_definition_consumers
        from compile_resources import CAPABILITIES
        report = inspect_definition_consumers({'effects': [{'stat': 'defenseBypass', 'value': 2}]}, CAPABILITIES)
        self.assertEqual(report['status'], 'consumer-missing')
        self.assertEqual(report['effects'][0]['stat'], 'defenseBypass')
        with self.assertRaisesRegex(ValueError, 'consumer'):
            validate_program({'steps': [{'op': 'effect', 'effects': [{'stat': 'weaponDamage', 'value': 2}]}]}, 'isolated-rule')
        report = inspect_definition_consumers({'programs': {'cast': {'steps': [{'op': 'weaponEffect', 'effects': [{'stat': 'weaponDamage', 'value': 2}]}]}}}, CAPABILITIES)
        self.assertEqual(report['effects'][0]['scope'], 'item')
        self.assertEqual(report['effects'][0]['status'], 'connected')

    def test_formula_arity_and_numeric_arguments_use_exported_engine_spec(self):
        for formula in [{'op': 'sub', 'args': [10, 2, 3]}, {'op': 'min', 'args': []}, {'op': 'mul', 'args': [2, 'P']}, {'op': 'floor', 'args': []}]:
            with self.assertRaisesRegex(ValueError, 'steps.*amount'):
                validate_program({'steps': [{'op': 'damage', 'amount': formula}]}, 'isolated-rule')
        validate_program({'steps': [{'op': 'damage', 'amount': {'op': 'mul', 'args': [2, {'context': 'P'}]}}]}, 'isolated-rule')

    def test_condition_shape_and_literal_numeric_fields_are_checked(self):
        for condition in [{'test': 'gte', 'left': 2}, {'all': [] , 'test': 'eq', 'left': 1, 'right': 1}, {'test': 'in', 'left': 1, 'values': '123'}]:
            with self.assertRaisesRegex(ValueError, 'steps.*when'):
                validate_program({'steps': [{'op': 'damage', 'amount': 3, 'when': condition}]}, 'isolated-rule')
        with self.assertRaisesRegex(ValueError, 'amount'):
            validate_program({'steps': [{'op': 'damage', 'amount': 'P'}]}, 'isolated-rule')
        validate_program({'steps': [{'op': 'damage', 'amount': 3, 'when': {'all': [False, True]}}]}, 'isolated-rule')

if __name__ == '__main__': unittest.main()

class DefinitionPolicyValidation(unittest.TestCase):
    def test_saved_effect_policy_migration_cannot_patch_values_or_state(self):
        import json, tempfile, shutil
        from pathlib import Path
        from unittest.mock import patch
        import compile_resources as compiler
        original = compiler.ROOT
        doc = json.loads((original/'resources/execution/85670628fcf1.rule.json').read_text())
        doc['definition']['effectPolicyMigrations'][0]['set']['value'] = 999
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root/'resources/execution').mkdir(parents=True)
            reading = root/doc['reading']['path']; reading.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(original/doc['reading']['path'], reading)
            (root/'resources/execution/test.rule.json').write_text(json.dumps(doc))
            with patch.object(compiler, 'ROOT', root), self.assertRaisesRegex(ValueError, 'effectPolicyMigrations'):
                compiler.load_contracts()
