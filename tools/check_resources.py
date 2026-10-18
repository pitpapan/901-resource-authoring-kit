"""Check curated resource links and the complete imperial spell source mapping."""
from collections import Counter
from functools import lru_cache
import json
from pathlib import Path
import re
from urllib.parse import unquote

from check_library import ROOT, local_link_error

def read(path):
    return path.read_text(encoding='utf-8-sig')

def slug(title):
    return re.sub(r'[^\w\- ]', '', title.lower()).replace(' ', '-')

@lru_cache(maxsize=None)
def anchors(path):
    counts = Counter()
    result = set()
    for title in re.findall(r'^#{1,6} (.+?)\s*$', read(path), re.M):
        base = slug(title)
        n = counts[base]
        result.add(base + (f'-{n}' if n else ''))
        counts[base] += 1
    return result

def main():
    errors = []
    required = ['resources/README.md', 'resources/imperial-mage.md',
                'resources/imperial-mage-notes.md', 'resources/imperial-mage-source.md',
                'resources/imperial-magic/README.md', 'authoring/lessons.md']
    for name in required:
        if not (ROOT/name).is_file():
            errors.append(f'Missing curated material: {name}')

    links = 0
    docs = [*sorted((ROOT/'resources').rglob('*.md')),
            *sorted((ROOT/'authoring').glob('*.md')), ROOT/'README.md', ROOT/'AGENTS.md']
    for doc in docs:
        for target in re.findall(r'\]\(([^)]+)\)', read(doc)):
            if '://' in target:
                continue
            target = unquote(target.strip('<>'))
            path, _, anchor = target.partition('#')
            links += 1
            if path and (problem := local_link_error(doc, path)):
                errors.append(problem)
                continue
            dest = (doc.parent/path).resolve() if path else doc.resolve()
            if dest.is_relative_to(ROOT/'outputs'):
                errors.append(f'Ignored output dependency: {doc.relative_to(ROOT)} -> {target}')
            if anchor and dest.suffix == '.md' and anchor not in anchors(dest):
                errors.append(f'Broken anchor: {doc.relative_to(ROOT)} -> {target}')

    counts = {}
    try:
        magic = ROOT/'resources/imperial-magic'
        audit = magic/'校核'
        inventory = json.loads(read(audit/'原文清单.json'))
        manifest = json.loads(read(audit/'完整覆盖.json'))
        records = manifest['records']
        key = lambda r: (r['source'], r['line'], r['name'])
        expected = Counter(map(key, inventory))
        if any(n != 1 for n in expected.values()) or Counter(map(key, records)) != expected:
            errors.append('Source inventory and complete coverage differ or contain duplicates')
        parts = []
        for filename in ('攻击与附魔-覆盖.json', '变化与防护-覆盖.json', '精神与探知-覆盖.json'):
            parts.extend(json.loads(read(audit/filename)))
        if Counter(json.dumps(r, sort_keys=True, ensure_ascii=False) for r in parts) != Counter(
                json.dumps(r, sort_keys=True, ensure_ascii=False) for r in records):
            errors.append('Chapter coverage differs from complete coverage')
        canonical = {}
        for record in records:
            valid = True
            for field in ('source', 'output'):
                problem = local_link_error(ROOT/'README.md', record[field])
                if problem:
                    errors.append(problem)
                    valid = False
            if not record['output'].startswith('resources/imperial-magic/'):
                errors.append(f'Non-portable output mapping: {record["output"]}')
                valid = False
            if not valid:
                continue
            lines = read(ROOT/record['source']).splitlines()
            line = record['line']
            if not 1 <= line <= len(lines) or lines[line-1].strip() != record['name']:
                errors.append(f'Source name or line changed: {key(record)}')
            if '### '+record['heading'] not in read(ROOT/record['output']).splitlines():
                errors.append(f'Missing spell heading: {record["heading"]}')
            identity = (record['output'], record['heading'])
            if identity not in canonical or canonical[identity]['status'] == 'merged':
                canonical[identity] = record
        index = read(magic/'README.md')
        for record in canonical.values():
            target = Path(record['output']).name+'#'+slug(record['heading'])
            if f']({target})' not in index:
                errors.append(f'Spell missing from reader index: {record["heading"]}')
        legal = [r for r in canonical.values() if r['status'] != 'prohibited']
        recipe_count = len(re.findall(r'^### ', read(magic/'08-炼金配方.md'), re.M))
        counts = {'source_files': len({r['source'] for r in records}),
                  'source_occurrences': len(records), 'unique_spells': len(canonical),
                  'imperial_legal': len(legal), 'prohibited': len(canonical)-len(legal),
                  'legal_by_grade': dict(Counter(r.get('actual_grade', r['grade']) for r in legal)),
                  'supplementary_recipes': recipe_count}
        for field, value in counts.items():
            if manifest.get(field) != value:
                errors.append(f'Coverage statistic differs: {field}: {value}')
    except (OSError, ValueError, KeyError, TypeError) as exc:
        errors.append(f'Cannot verify spell coverage: {exc}')

    print(json.dumps({'markdown_files': len(docs), 'local_links': links, **counts,
                      'errors': errors[:30], 'error_count': len(errors)},
                     ensure_ascii=False, indent=2))
    return bool(errors)

if __name__ == '__main__':
    raise SystemExit(main())
