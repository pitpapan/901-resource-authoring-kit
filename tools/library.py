"""Import, index and search the local source library; Python standard library only.

Existing Markdown is preserved. HTML collisions fail rather than overwrite.
Passages and tags are retrieval hints, never an automatic rules interpretation.
"""
from pathlib import Path
from html.parser import HTMLParser
from urllib.parse import unquote, quote
from collections import Counter
import argparse
import hashlib
import json
import re
import shutil
from datetime import datetime, timezone

ROOT = Path(__file__).resolve().parents[1]
BLOCKS = {'p', 'div', 'br', 'tr', 'li', 'h1', 'h2', 'h3', 'h4'}
LEGACY = ('等待有缘人重置', '已经有人承包重置', '出于版本变迁而被移除', '施工区')
TAGS = {
    '攻击': ('攻击', '命中', '伤害'), '防护': ('防御', '格挡', '护甲', '盔甲', '吸收', '抗力'),
    '协作': ('盟友', '友军', '队友', '掩护', '协助'), '机动': ('移动', '冲锋', '速度', '骑乘'),
    '额外攻击': ('额外攻击', '多次攻击', '第二次攻击', '多重攻击', '连击'),
    '能量循环': ('能量', '恢复', '剑气', '消耗'), '侦察': ('侦查', '侦察', '调查', '感知', '隐匿'),
    '抵抗': ('豁免', '强韧', '反射', '抵抗', '状态点'), '治疗': ('治疗', '急救', '医学'),
    '社交': ('交涉', '社交', '风度', '威吓', '说服'), '预算': ('特性', '定价', '支线'),
    '动作': ('AP', '动作', '反射式', '反应'), '成长': ('进阶', '前提', '先决', '等级'),
}
ALIASES = {'称号': '能力组', '训练': '能力组', '技能': '技艺', '护卫': '掩护', '侦察': '侦查'}

def dump(path, obj):
    path.write_text(json.dumps(obj, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')

def records(path):
    return [json.loads(l) for l in path.read_text(encoding='utf-8-sig').splitlines() if l.strip()]

def save_records(path, rows):
    path.write_text(''.join(json.dumps(r, ensure_ascii=False) + '\n' for r in rows), encoding='utf-8')

class Toc(HTMLParser):
    def __init__(self):
        super().__init__()
        self.parents, self.last, self.obj, self.entries = [], [], None, []

    def handle_starttag(self, tag, attrs):
        a = dict(attrs)
        if tag == 'ul':
            self.parents.append(self.last[:])
        elif tag == 'object' and a.get('type') == 'text/sitemap':
            self.obj = {}
        elif tag == 'param' and self.obj is not None:
            self.obj[a.get('name', '').lower()] = a.get('value', '')

    def handle_endtag(self, tag):
        if tag == 'ul' and self.parents:
            self.parents.pop()
        elif tag == 'object' and self.obj is not None:
            name = self.obj.get('name', '')
            self.last = (self.parents[-1] if self.parents else []) + [name]
            local = unquote(self.obj.get('local', '')).replace('\\', '/').split('#')[0]
            if local:
                self.entries.append({'local': local, 'title': name, 'toc': self.last[:]})
            self.obj = None

class Body(HTMLParser):
    def __init__(self, whole=False):
        super().__init__(convert_charrefs=True)
        self.active, self.depth, self.parts, self.skip = whole, 0, [], 0

    def handle_starttag(self, tag, attrs):
        a = dict(attrs)
        if a.get('id') == 'winchm_template_content':
            self.active, self.depth = True, 1
            return
        if not self.active:
            return
        if tag == 'div' and self.depth:
            self.depth += 1
        if tag in ('script', 'style', 'head'):
            self.skip += 1
        if self.skip:
            return
        if tag in BLOCKS:
            self.parts.append('\n')
        if tag in ('td', 'th'):
            self.parts.append(' | ')
        if tag == 'img':
            self.parts.append('[图像：' + a.get('src', '') + '；见原始 HTML]')

    def handle_endtag(self, tag):
        if not self.active:
            return
        if tag in ('script', 'style', 'head') and self.skip:
            self.skip -= 1
        if tag == 'div' and self.depth:
            self.depth -= 1
            if self.depth == 0:
                self.active = False
        if tag in BLOCKS:
            self.parts.append('\n')

    def handle_data(self, data):
        if self.active and not self.skip:
            self.parts.append(data.replace('\r', '').replace('\n', ' '))

    def text(self):
        return '\n'.join(line for x in ''.join(self.parts).splitlines()
                         if (line := re.sub(r'[ \t\xa0]+', ' ', x).strip()))

def classify(book, toc, stem):
    status = next((x for x in LEGACY if any(x in t for t in toc)), None)
    if book == 'PHB':
        return 'rules', 'PHB基线原文', f'content/PHB/01_rules/{stem}.md'
    if status:
        kind, folder, rest = 'misc', '05_misc', toc[2:-1]
    elif '资源相关' in toc:
        kind, folder, rest = 'resources', '02_resources', toc[toc.index('资源相关')+1:-1]
    elif any('怪物图鉴' in t for t in toc):
        kind, folder, rest = 'bestiary', '03_bestiary', toc[2:-1]
    elif '特性列表' in toc:
        kind, folder, rest = 'traits', '04_traits', toc[toc.index('特性列表')+1:-1]
    elif '规则相关' in toc:
        kind, folder, rest = 'rules', '01_rules', toc[2:-1]
    elif any(t in ('序言', '关于本书') for t in toc):
        kind, folder, rest = 'meta', '00_meta', toc[1:-1]
    else:
        kind, folder, rest = 'misc', '05_misc', toc[1:-1]
    path = '/'.join(['content', book, folder, *rest, stem + '.md'])
    return kind, status or ('现行目录原文' if kind == 'resources' else '原文参考'), path

def import_sources(args):
    old = records(ROOT/'catalog.jsonl')
    by_source = {r['source_html']: r for r in old}
    missing, archive_info = [], []
    for book, source in [('RE', args.re), ('PHB', args.phb)]:
        base = Path(source).resolve()
        toc = Toc()
        toc.feed(next(base.glob('*.hhc')).read_text(encoding='gb18030'))
        by_local = {}
        for ent in toc.entries:
            by_local.setdefault(ent['local'], ent)
            if not (base/ent['local']).exists():
                missing.append({'book': book, **ent})
        for src in sorted(base.rglob('*')):
            if not src.is_file():
                continue
            relative = src.relative_to(base).as_posix()
            target = ROOT/'source_html'/book/relative
            data = src.read_bytes()
            if target.exists() and target.read_bytes() != data:
                raise ValueError(f'Refusing to overwrite different source: {target}')
            target.parent.mkdir(parents=True, exist_ok=True)
            if not target.exists():
                shutil.copy2(src, target)
            if src.suffix.lower() not in ('.htm', '.html'):
                continue
            key = target.relative_to(ROOT).as_posix()
            ent = by_local.get(relative, {'title': src.stem, 'toc': []})
            kind, status, new_md = classify(book, ent['toc'], src.stem)
            if key in by_source:
                row = by_source[key]
            else:
                html = data.decode('gb18030')
                body = Body(whole='winchm_template_content' not in html)
                body.feed(html)
                md = ROOT/new_md
                md.parent.mkdir(parents=True, exist_ok=True)
                import os
                link = quote(Path(os.path.relpath(target, md.parent)).as_posix(), safe='/')
                text = (f'# {ent["title"]}\n\n> 原书：`{book}`｜原始页面：`{book}/{relative}`｜[原始 HTML]({link})\n'
                        f'> 原目录：{" → ".join(ent["toc"])}\n\n{body.text()}\n')
                if md.exists():
                    raise ValueError(f'Refusing to overwrite untracked Markdown: {md}')
                md.write_text(text, encoding='utf-8')
                row = {'book': book, 'title': ent['title'], 'kind': kind, 'md_path': new_md,
                       'source_html': key, 'source_file': f'{book}/{relative}',
                       'toc_path': ' → '.join(ent['toc']), 'classification_basis': '原书 HHC 目录',
                       'in_original_toc': relative in by_local, 'original_tables': html.lower().count('<table'),
                       'source_characters': len(body.text()), 'conversion': 'plain-text-blocks-v1; tables flattened; raw HTML retained'}
                by_source[key] = row
            row.update({'version': 'RE v1.03先行版' if book == 'RE' else 'PHB v0.3',
                        'source_status': status, 'adoption_status': 'SOURCE_ONLY',
                        'html_sha256': hashlib.sha256(data).hexdigest(), 'html_bytes': len(data),
                        'source_archive': 'source_archives/RE_v1.03.chm' if book == 'RE' else 'source_archives/PHB_v0.3.chm'})
            md_bytes = (ROOT/row['md_path']).read_bytes()
            row.update(markdown_bytes=len(md_bytes), markdown_line_count=len(md_bytes.decode('utf-8-sig').splitlines()),
                       markdown_sha256=hashlib.sha256(md_bytes).hexdigest())
        archive = ROOT/'source_archives'/('RE_v1.03.chm' if book == 'RE' else 'PHB_v0.3.chm')
        archive_info.append({'book': book, 'file': archive.relative_to(ROOT).as_posix(),
                             'sha256': hashlib.sha256(archive.read_bytes()).hexdigest(), 'bytes': archive.stat().st_size})
    rows = sorted(by_source.values(), key=lambda r: (r['book'], r['md_path']))
    save_records(ROOT/'catalog.jsonl', rows)
    fields = ['book', 'version', 'kind', 'title', 'source_status', 'adoption_status', 'md_path', 'source_html', 'toc_path']
    (ROOT/'catalog.tsv').write_text('\t'.join(fields)+'\n'+''.join('\t'.join(str(r.get(f, '')).replace('\t',' ') for f in fields)+'\n' for r in rows), encoding='utf-8')
    dump(ROOT/'source_archives'/'provenance.json', {'rebuilt_at_utc': datetime.now(timezone.utc).isoformat(), 'archives': archive_info,
        'source_collection': 'PHB v0.3 / RE v1.03先行版 CHM；原件随库保存', 'missing_toc_targets': missing,
        'note': '完整指这些版本的实际文件完整收录，不补造原 CHM 已缺失的目标。'})
    build_index(rows)
    print(json.dumps({'pages': len(rows), 'kinds': dict(Counter(r['kind'] for r in rows)), 'missing_toc_targets': len(missing)}, ensure_ascii=False))

def build_index(rows=None):
    rows = rows or records(ROOT/'catalog.jsonl')
    passages = []
    for r in rows:
        lines = (ROOT/r['md_path']).read_text(encoding='utf-8-sig').splitlines()
        start = 5 if len(lines) > 5 else 0
        while start < len(lines):
            end, length = start, 0
            while end < len(lines) and end-start < 24 and (length < 1100 or end == start):
                length += len(lines[end]); end += 1
            text = '\n'.join(lines[start:end])
            if text.strip():
                passages.append({'id': r['md_path']+f':{start+1}', 'book': r['book'], 'kind': r['kind'],
                    'title': r['title'], 'md_path': r['md_path'], 'start': start+1, 'end': end,
                    'source_status': r.get('source_status', '原文参考'), 'toc_path': r['toc_path'],
                    'tags': [tag for tag, words in TAGS.items() if any(w in text for w in words)],
                    'text': text})
            if end == len(lines):
                break
            start = max(start+1, end-2)
    save_records(ROOT/'passages.jsonl', passages)
    names = {'resources':'资源', 'traits':'特性', 'bestiary':'怪物图鉴', 'misc':'旧版、待重置与其他杂项', 'rules':'核心规则机制', 'meta':'版本说明与序言'}
    for kind, title in names.items():
        selected = [r for r in rows if r['kind'] == kind]
        out = [f'# {title}索引', '', f'共 {len(selected)} 页。来源收录不等于 901 采用；检索片段请使用 `tools/library.py search`。', '']
        for r in selected:
            out.append(f'- [{r["title"]}](../{quote(r["md_path"], safe="/")}) — {r["book"]}｜{r.get("source_status", "原文参考")}｜{r["toc_path"]}')
        (ROOT/'indices'/f'{kind}.md').write_text('\n'.join(out)+'\n', encoding='utf-8')
    print(json.dumps({'indexed_pages': len(rows), 'passages': len(passages)}, ensure_ascii=False))

def search(args):
    terms = args.query
    hits = []
    for p in records(ROOT/'passages.jsonl'):
        if not args.include_legacy and any(x in p['source_status'] for x in LEGACY):
            continue
        if args.kind and p['kind'] != args.kind:
            continue
        if args.tag and args.tag not in p['tags']:
            continue
        hay = p['text'] + '\n' + p['title'] + '\n' + p['toc_path']
        if not all(t in hay or ALIASES.get(t, t) in hay for t in terms):
            continue
        score = sum(min(p['text'].count(t), 5) + 8*(t in p['title']) + 100*(t == p['title']) for t in terms)
        hits.append((score, p))
    hits.sort(key=lambda pair: (-pair[0], pair[1]['md_path'], pair[1]['start']))
    result = []
    for score, p in hits[:args.limit]:
        key = next((t for t in terms if t in p['text'] and t not in p['title']),
                   next((t for t in terms if t in p['text']), ''))
        pos = max(0, p['text'].find(key)-50) if key else 0
        result.append({k: p[k] for k in ('id', 'title', 'kind', 'source_status', 'tags')} | {'excerpt': p['text'][pos:pos+args.chars], 'end': p['end']})
    print(json.dumps({'matches': len(hits), 'returned': len(result), 'results': result}, ensure_ascii=False, indent=2))

def read(args):
    p = (ROOT/args.path).resolve()
    if not p.is_relative_to(ROOT/'content'):
        raise ValueError('Read only paths under content/')
    lines = p.read_text(encoding='utf-8-sig').splitlines()
    end = min(len(lines), args.start+args.lines-1)
    print('\n'.join(f'{i+1}: {lines[i]}' for i in range(args.start-1, end)))

def cards(args):
    """Select authored cards without loading all examples into model context."""
    folder = ROOT/'authoring'
    grouped = {}
    for cid in dict.fromkeys(args.ids):
        if not re.fullmatch(r'(CR|TB|T|S)-\d{2}', cid):
            raise ValueError(f'Invalid card ID: {cid}')
        name = 'samples.md' if cid.startswith('S-') else 'common_rules.md' if cid.startswith('CR-') else 'traits.md'
        grouped.setdefault(name, []).append(cid)
    outputs = []
    for name, ids in grouped.items():
        content = (folder/name).read_text(encoding='utf-8')
        preface = '\n'.join(content.splitlines()[:4])
        chunks = []
        for cid in ids:
            if name == 'samples.md':
                match = re.search(r'^### '+re.escape(cid)+r'\b.*?(?=^### |^\*\*旧例|\Z)', content, re.M|re.S)
            else:
                match = re.search(r'^\| '+re.escape(cid)+r'\b[^\n]*', content, re.M)
            if not match:
                raise ValueError(f'Unknown card: {cid}')
            chunks.append(match.group().strip())
        outputs.append(f'来源：authoring/{name}\n{preface}\n\n'+'\n\n'.join(chunks))
    print('\n\n'.join(outputs))

def main():
    ap = argparse.ArgumentParser(description=__doc__)
    sub = ap.add_subparsers(dest='command', required=True)
    imp = sub.add_parser('import'); imp.add_argument('--re', required=True); imp.add_argument('--phb', required=True)
    sub.add_parser('index')
    sp = sub.add_parser('search'); sp.add_argument('query', nargs='*'); sp.add_argument('--kind', choices=['resources','traits','rules','meta','misc','bestiary'])
    sp.add_argument('--tag', choices=list(TAGS)); sp.add_argument('--include-legacy', action='store_true')
    sp.add_argument('--limit', type=int, default=5); sp.add_argument('--chars', type=int, default=220)
    rp = sub.add_parser('read'); rp.add_argument('path'); rp.add_argument('--start', type=int, default=1); rp.add_argument('--lines', type=int, default=40)
    cp = sub.add_parser('cards'); cp.add_argument('ids', nargs='+')
    args = ap.parse_args()
    if args.command == 'import': import_sources(args)
    elif args.command == 'index': build_index()
    elif args.command == 'search':
        args.limit = max(1, min(args.limit, 20)); args.chars = max(80, min(args.chars, 600)); search(args)
    elif args.command == 'read':
        args.start = max(1,args.start); args.lines = max(1,min(args.lines,160)); read(args)
    elif args.command == 'cards': cards(args)

if __name__ == '__main__':
    main()
