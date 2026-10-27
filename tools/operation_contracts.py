"""Consume field/receipt/consumer declarations exported by the actual JS engine."""
import math


def validate_schema(value, spec, path):
    def fail(message): raise ValueError(f'{path}: {message}')
    if 'anyOf' in spec:
        for choice in spec['anyOf']:
            try:
                validate_schema(value, choice, path)
                return
            except ValueError: pass
        fail('no supported value shape')
    if spec.get('expression') and isinstance(value, dict):
        if any(isinstance(value.get(k), str) for k in ['state', 'context', 'choice', 'op']): return
        fail('expected literal or value expression')
    kind = spec['type']
    if kind == 'condition':
        if value is None or type(value) is bool or isinstance(value, dict): return
        fail('condition required')
    if kind == 'array':
        if not isinstance(value, list): fail('array required')
        for i, item in enumerate(value): validate_schema(item, spec['items'], f'{path}[{i}]')
        return
    if kind == 'object':
        if not isinstance(value, dict): fail('object required')
        for key in spec.get('required', []):
            if key not in value: raise ValueError(f'{path}.{key}: required field')
        for key, item in value.items():
            child = spec.get('fields', {}).get(key)
            if child: validate_schema(item, child, path + '.' + key)
            elif not spec.get('additional'): raise ValueError(f'{path}.{key}: unsupported field')
        return
    if kind in ['number', 'integer']:
        if type(value) not in (int, float) or not math.isfinite(value) or kind == 'integer' and int(value) != value: fail(kind + ' required')
        if 'minimum' in spec and value < spec['minimum'] or 'exclusiveMinimum' in spec and value <= spec['exclusiveMinimum']: fail('outside numeric bounds')
    elif kind == 'boolean':
        if type(value) is not bool: fail('boolean required')
    elif kind == 'string':
        if not isinstance(value, str): fail('string required')
    if spec.get('minLength', 0) and len(value) < spec['minLength']: fail('nonempty value required')
    if 'enum' in spec and value not in spec['enum']: fail('unsupported enum value')


def effect_consumer(capabilities, stat, scope):
    spec = capabilities['effectConsumers'].get(stat, {})
    return spec if spec.get('status') == 'connected' and scope in spec['scopes'] else None


def validate_operation_fields(step, capabilities, path):
    spec = capabilities['operators'][step['op']]
    if 'fields' in spec:
        validate_schema(step, {'type': 'object', 'fields': spec['fields'], 'required': spec['required']}, path)
    if step['op'] in ['effect', 'weaponEffect', 'temporaryHealth', 'aura']:
        for i, effect in enumerate(step.get('effects', [])):
            if not effect_consumer(capabilities, effect['stat'], 'item' if step['op'] == 'weaponEffect' else 'actor'):
                raise ValueError(f'{path}.effects[{i}]: consumer-missing for {effect["stat"]}')


def guard_implies(consumer, producer):
    if producer is None or consumer == producer: return True
    if isinstance(consumer, dict) and 'all' in consumer:
        return any(guard_implies(part, producer) for part in consumer['all'])
    return False


def validate_receipt_references(program, capabilities, resource_id):
    """Typed target-local outputs; not a full state/scene/context type inference."""
    number = {'type': 'number'}
    def walk(rows, inherited=None, event=None):
        available = dict(inherited or {})
        reserved = {'save', 'hit', 'damage', 'actualDamage'}
        for row in rows:
            if row['op'] == 'statusSource': reserved.add(row['asValue'])
            if row['op'] == 'save': reserved.update([row.get('as', 'save'), row.get('resultAs', row.get('as', 'save'))])
        def refs(node, path, expected=None):
            if isinstance(node, dict):
                if isinstance(node.get('context'), str): yield node['context'], path, expected.get('type') if expected and expected.get('expression') else None
                for key, child in node.items():
                    if key not in ('steps',):
                        child_schema = {'type': 'array', 'items': {'type': 'number', 'expression': True}} if key == 'args' and node.get('op') in capabilities['expressions'] else (expected or {}).get('fields', {}).get(key)
                        yield from refs(child, path + '.' + key, child_schema)
            elif isinstance(node, list):
                for i, child in enumerate(node): yield from refs(child, f'{path}[{i}]', (expected or {}).get('items'))
        for index, row in enumerate(rows):
            required_event = capabilities['operators'][row['op']].get('requiresEvent')
            if required_event and required_event != event: raise ValueError(f'{resource_id}: operation requires event scope {required_event}')
            allowed = capabilities.get('eventOperatorScopes', {}).get(event)
            if allowed is not None and row['op'] not in allowed: raise ValueError(f'{resource_id}: operation forbidden in event scope {event}')
            for ref, path, expected_type in refs(row, f'{resource_id}: steps[{index}]', {'fields': capabilities['operators'][row['op']].get('fields', {})}):
                root, *parts = ref.split('.')
                if root not in reserved: continue
                item = available.get(root)
                if not item: raise ValueError(f'{path}: {ref} has no earlier target-local producer')
                spec, guard, component = item
                if not guard_implies(row.get('when'), guard): raise ValueError(f'{path}: {ref} requires matching producer guard')
                if component is not None and component != row.get('component'): raise ValueError(f'{path}: cross-component receipt {ref}')
                for part in parts:
                    spec = spec.get('fields', {}).get(part)
                    if spec is None: raise ValueError(f'{path}: no output field {ref}')
                if expected_type and spec['type'] != expected_type: raise ValueError(f'{path}: {ref} output type {spec["type"]} cannot supply {expected_type}')
            if row['op'] == 'save':
                op = capabilities['operators']['save']
                available[row.get('as', 'save')] = (number, row.get('when'), row.get('component'))
                if row.get('resultAs'):
                    variant = row.get('resolve', {}).get('kind', 'roll')
                    available[row['resultAs']] = (op['outputs'][variant], row.get('when'), row.get('component'))
            elif row['op'] == 'statusSource':
                available[row['asValue']] = (number, row.get('when'), row.get('component'))
            elif row['op'] == 'attack':
                for key in ['hit', 'damage']: available[key] = (number, row.get('when'), row.get('component'))
            elif row['op'] == 'damage':
                prior = available.get('actualDamage')
                available['actualDamage'] = prior if row.get('when') is not None and prior and prior[1] is None else (number, row.get('when'), row.get('component'))
            elif row['op'] == 'trigger':
                event_context = {key: (spec, None, None) for key, spec in capabilities['triggerContexts'].get(row.get('event'), {}).items()}
                walk(row['steps'], event_context, row.get('event'))
                if row.get('onDeath'): walk(row['onDeath']['steps'], {'effectiveRounds': (number, None, None)}, 'death')
    walk(program['steps'])


def inspect_definition_consumers(definition, capabilities):
    rows, operations = [], []
    def walk(node, path, scope='actor'):
        if isinstance(node, dict):
            if node.get('op') == 'weaponEffect': scope = 'item'
            if node.get('op') in capabilities['operators']:
                spec = capabilities['operators'][node['op']]
                operations.append({'path': path, 'operation': node['op'], 'inputValidation': spec['validation'], 'outputValidation': 'typed' if spec.get('outputs') else 'not-typed'})
            if 'stat' in node and 'value' in node:
                spec = effect_consumer(capabilities, node['stat'], scope)
                rows.append({'path': path, 'stat': node['stat'], 'scope': scope,
                             'status': 'connected' if spec else 'consumer-missing',
                             **({'consumer': spec} if spec else {})})
            for key, child in node.items(): walk(child, path + '.' + key, scope)
        elif isinstance(node, list):
            for index, child in enumerate(node): walk(child, f'{path}[{index}]', scope)
    walk(definition, 'definition')
    return {'status': 'consumer-missing' if any(r['status'] != 'connected' for r in rows) else 'registered-consumers',
            'effects': rows, 'operations': operations, 'limits': ['Consumer registration is not full behavior verification; operation/state/context typing remains partial.']}
