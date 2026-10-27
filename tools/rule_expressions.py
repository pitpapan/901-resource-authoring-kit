"""Bounded structural/numeric expression checks against the actual JS ABI.

This checks formula shape, arity, literals and conditions. It does not infer
state/context types, validate every operation field, or imply full coverage.
"""
import math


def validate_rule_data(data, capabilities, resource_id):
    def reject(path, message):
        raise ValueError(f'{resource_id}: {path}: {message}')

    def value(node, path, numeric=False):
        if type(node) in (int, float):
            if not math.isfinite(node): reject(path, 'non-finite numeric literal')
            return
        if node is None or type(node) in (str, bool):
            if numeric: reject(path, 'expected numeric expression')
            return
        if not isinstance(node, dict): reject(path, 'expected value expression')
        kinds = set(node) & {'state', 'context', 'choice', 'op'}
        if len(kinds) != 1: reject(path, 'ambiguous or missing value source')
        kind = next(iter(kinds))
        if kind != 'op':
            if not isinstance(node[kind], str) or not node[kind] or set(node) - {kind, 'default'}:
                reject(path, 'invalid value reference')
            if 'default' in node: value(node['default'], path + '.default', numeric)
            return
        spec = capabilities['expressions'].get(node['op'])
        args = node.get('args')
        if not spec or not isinstance(args, list) or set(node) - {'op', 'args'}:
            reject(path, 'unknown expression operation or arguments')
        if len(args) < spec['minimum'] or spec['maximum'] is not None and len(args) > spec['maximum']:
            reject(path, 'invalid expression arity')
        for index, arg in enumerate(args): value(arg, f'{path}.args[{index}]', True)

    def condition(node, path):
        if node is None or type(node) is bool: return
        if not isinstance(node, dict): reject(path, 'expected condition')
        kinds = set(node) & {'all', 'any', 'not', 'pool', 'test'}
        if len(kinds) != 1: reject(path, 'ambiguous or missing condition operator')
        kind = next(iter(kinds))
        if kind != 'test':
            if set(node) != {kind}: reject(path, 'unknown condition fields')
            if kind in ('all', 'any'):
                if not isinstance(node[kind], list): reject(path, 'condition list required')
                for index, item in enumerate(node[kind]): condition(item, f'{path}.{kind}[{index}]')
            elif kind == 'not': condition(node[kind], path + '.not')
            else:
                pool = node[kind]
                if not isinstance(pool, dict) or set(pool) != {'minimum'}: reject(path, 'pool minimum required')
                if type(pool['minimum']) not in (int, float) or not math.isfinite(pool['minimum']) or pool['minimum'] < 0:
                    reject(path, 'invalid pool minimum')
            return
        spec = capabilities['conditions'].get(node['test'])
        if not spec or set(node) != {'test', *spec['required']}: reject(path, 'incomplete or unknown condition test')
        for key in spec['required']:
            if key == 'values':
                if not isinstance(node[key], list) or any(type(x) not in (str, int, float, bool, type(None)) for x in node[key]): reject(path, 'literal values array required')
                for index, item in enumerate(node[key]): value(item, f'{path}.values[{index}]')
            else: value(node[key], path + '.' + key, spec.get('numeric', False))

    def walk(node, path):
        if isinstance(node, list):
            for index, item in enumerate(node): walk(item, f'{path}[{index}]')
        elif isinstance(node, dict):
            if 'args' in node or node.get('op') in capabilities['expressions']:
                value(node, path, True)
                return
            if set(node) & {'state', 'context', 'choice'} and set(node) <= {'state', 'context', 'choice', 'default'}:
                value(node, path)
                return
            if 'stat' in node and 'value' in node: value(node['value'], path + '.value', True)
            # Numeric step fields already consumed as formulas by resource-program.
            if node.get('op') in capabilities['operators']:
                for key in ['amount', 'points', 'weapon', 'penalty', 'cap', 'speed', 'magic', 'range', 'rounds', 'minutes', 'perRound', 'count']:
                    if key in node: value(node[key], path + '.' + key, True)
            for key, child in node.items():
                if key in ('when', 'condition', 'ownership'): condition(child, path + '.' + key)
                else: walk(child, path + '.' + key)

    walk(data, 'rule')
