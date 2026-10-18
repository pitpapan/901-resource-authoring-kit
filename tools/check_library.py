"""Read-only integrity and self-containment check for the portable 901 kit."""
from pathlib import Path
import hashlib
import json
import re
import os
from functools import lru_cache
from urllib.parse import unquote

ROOT = Path(__file__).resolve().parents[1]

@lru_cache(maxsize=None)
def directory_names(path):
    return {p.name for p in path.iterdir()}

def local_link_error(doc, target):
    """Require package-local paths and exact filename case, including on Windows."""
    if re.match(r'^[A-Za-z]:[/\\]', target) or Path(target).is_absolute():
        return f'Absolute local link: {doc.relative_to(ROOT)} -> {target}'
    lexical = Path(os.path.abspath(doc.parent/target))
    resolved = lexical.resolve()
    if not resolved.is_relative_to(ROOT):
        return f'Link escapes package: {doc.relative_to(ROOT)} -> {target}'
    if not resolved.exists():
        return f'Broken link: {doc.relative_to(ROOT)} -> {target}'
    current = ROOT
    for part in lexical.relative_to(ROOT).parts:
        if part not in directory_names(current):
            return f'Filename case mismatch: {doc.relative_to(ROOT)} -> {target}'
        current = current/part
    return None

def main():
    errors = []
    required = ['AGENTS.md', 'README.md', 'authoring/README.md', 'authoring/guide.md',
                'authoring/common_rules.md', 'authoring/traits.md', 'authoring/samples.md',
                'authoring/brief-template.md', 'authoring/lessons.md', 'resources/README.md',
                'resources/imperial-mage.md', 'resources/imperial-magic/README.md', 'rules/README.md',
                'rules/901-core-rules-v0.1.md', 'rules/901-open-decisions.md']
    for path in required:
        if not (ROOT/path).is_file():
            errors.append(f'Missing standalone material: {path}')
    rows = [json.loads(x) for x in (ROOT / 'catalog.jsonl').read_text(encoding='utf-8-sig').splitlines()]
    counts = {b: sum(r['book'] == b for r in rows) for b in ('PHB', 'RE')}
    if counts != {'PHB': 16, 'RE': 964}:
        errors.append(f'Incomplete snapshot: {counts}; expected PHB 16 / RE 964')
    for key in ('md_path', 'source_html'):
        if len({r[key] for r in rows}) != len(rows):
            errors.append(f'Duplicate {key}')
    for r in rows:
        src, md = ROOT / r['source_html'], ROOT / r['md_path']
        if not src.is_file() or not md.is_file():
            errors.append(f'Missing source/content: {r["title"]}')
        elif hashlib.sha256(src.read_bytes()).hexdigest() != r['html_sha256']:
            errors.append(f'Source hash changed: {r["source_html"]}')
        elif md.stat().st_size < 100:
            errors.append(f'Empty conversion: {r["md_path"]}')
        elif r.get('markdown_sha256') and hashlib.sha256(md.read_bytes()).hexdigest() != r['markdown_sha256']:
            errors.append(f'Markdown differs from catalog: {r["md_path"]}')
    provenance = ROOT/'source_archives'/'provenance.json'
    if not provenance.exists():
        errors.append('Missing archive provenance')
    else:
        for a in json.loads(provenance.read_text(encoding='utf-8'))['archives']:
            archive = ROOT/a['file']
            if not archive.exists() or hashlib.sha256(archive.read_bytes()).hexdigest() != a['sha256']:
                errors.append(f'Archive missing/changed: {a["file"]}')
    for name in ('resources', 'traits', 'bestiary', 'misc', 'mechanisms'):
        if not (ROOT / 'indices' / f'{name}.md').is_file():
            errors.append(f'Missing index: {name}')
    docs = [*sorted(ROOT.glob('*.md')), *sorted((ROOT/'indices').glob('*.md')),
            *sorted((ROOT/'authoring').glob('*.md')), *sorted((ROOT/'rules').rglob('*.md')),
            *sorted((ROOT/'examples').rglob('*.md')), *sorted((ROOT/'resources').rglob('*.md'))]
    for doc in docs:
        for link in re.findall(r'\]\(([^)]+)\)', doc.read_text(encoding='utf-8-sig')):
            if '://' in link or link.startswith('#'):
                continue
            target = unquote(link.split('#')[0]).strip('<>')
            if target and (problem := local_link_error(doc, target)):
                errors.append(problem)
    passages = ROOT/'passages.jsonl'
    if not passages.exists():
        errors.append('Missing passage index')
    else:
        covered = set()
        contents = {r['md_path']: (ROOT/r['md_path']).read_text(encoding='utf-8-sig').splitlines() for r in rows}
        for line in passages.read_text(encoding='utf-8').splitlines():
            p = json.loads(line)
            covered.add(p['md_path'])
            actual = '\n'.join(contents[p['md_path']][p['start']-1:p['end']])
            if actual != p['text']:
                errors.append(f'Stale passage: {p["id"]}')
        blank = {r['md_path'] for r in rows if r.get('source_characters') == 0
                 and not any(x.strip() for x in contents[r['md_path']][5:])}
        if covered != set(contents) - blank:
            errors.append(f'Passage coverage mismatch: {len(covered)} / {len(contents)-len(blank)} nonempty pages')
    print(json.dumps({'pages': len(rows), 'books': counts,
        'empty_source_pages': [r['md_path'] for r in rows if r.get('source_characters') == 0],
        'errors': errors[:30], 'error_count': len(errors)}, ensure_ascii=False, indent=2))
    return bool(errors)

if __name__ == '__main__':
    raise SystemExit(main())
