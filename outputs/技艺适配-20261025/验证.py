#!/usr/bin/env python3
"""Independent static audit. Read-only; no generator imports, network or writes."""
import csv, hashlib, json, re
from pathlib import Path
from urllib.parse import unquote
BASE = Path(__file__).resolve().parent
ROOT = BASE.parents[1]
def rows(name):
    with (BASE/name).open() as f: return list(csv.DictReader(f, delimiter='\t'))
def require(ok, message):
    if not ok: raise AssertionError(message)
def sha(path): return hashlib.sha256(path.read_bytes()).hexdigest()
base = rows('来源基线.tsv'); manifest = rows('源清单.tsv'); coverage = rows('条款覆盖.tsv')
require(len(base)==192 and len(manifest)==192, 'source count')
paths = {x['来源路径'] for x in base}
require(paths=={x['来源路径'] for x in manifest}, 'source set changed')
expected={'J01':13,'J02':6,'J03':5,'J04':30,'J05':14,'J06':14,'J07':21,'J08':13,'J09':16,'J10':1,'J11':2,'J12':6,'J13':51}
require({g:sum(x['组号']==g for x in manifest) for g in expected}==expected,'group counts')
seen=set(); body_text={p:p.read_text() for p in (BASE/'阅读版').glob('*.md')}
require(len(body_text)==142,'reading chapter count')
cache={}
def anchors(path):
    if path not in cache:
        text=path.read_text(); values=set(re.findall(r'<a id="([^"]+)"',text))
        for h in re.findall(r'^#{1,6}\s+(.+)$',text,re.M):
            values.add(h); values.add(re.sub(r'[^\w\-\u3400-\u9fff ]','',h.lower()).replace(' ','-'))
        cache[path]=values
    return cache[path]
for m in manifest:
    p=ROOT/m['来源路径']; require(sha(p)==m['来源SHA256'],'source hash '+str(p))
    expected_lines={i for i,s in enumerate(p.read_text().splitlines(),1) if s.strip()}
    actual=[int(x['原文行']) for x in coverage if x['来源路径']==m['来源路径']]
    require(len(actual)==len(set(actual)) and set(actual)==expected_lines,'line coverage '+str(p))
    for dst in json.loads(m['正文路径']): require((ROOT/dst).is_file(),'manifest destination '+dst)
for c in coverage:
    dst=ROOT/c['正文路径']; require(dst.is_file(),'coverage destination')
    require(c['锚点'] in anchors(dst),'coverage anchor '+str(dst)+'#'+c['锚点'])
    if '原句SHA256' in c:
        source=(ROOT/c['来源路径']).read_text().splitlines()[int(c['原文行'])-1].strip()
        require(hashlib.sha256(source.encode()).hexdigest()==c['原句SHA256'],'line hash')
for n in rows('名称索引.tsv'):
    require(bool(n['名称'].strip()),'empty or whitespace navigation name')
    require(not re.fullmatch(r'[DCBAS]+级[：:（()）\s]*',n['名称']),'grade-only navigation name')
    dst=ROOT/n['正文路径'];require(dst.is_file() and n['锚点'] in anchors(dst),'name anchor '+n['名称'])
official=json.loads((ROOT/'resources/imperial-magic/校核/完整覆盖.json').read_text())['records']
reuse=rows('已采复用.tsv')
require(len(reuse)==len(official)==222,'official occurrence count')
require(len({(x['output'],x['heading']) for x in official})==215,'official unique count')
require(len({x['source'] for x in official})==24,'official source count')
require({(x['名称'],x['来源路径'],int(x['原文行']),x['唯一正文'],x['标题'],x['现行身份']) for x in reuse}=={(x['name'],x['source'],x['line'],x['output'],x['heading'],x['status']) for x in official},'official identity drift')
for c in coverage:
    matches=[x for x in official if x['source']==c['来源路径'] and x['line']<=int(c['原文行'])]
    if matches:
        q=max(matches,key=lambda x:x['line'])
        require(('禁用' in c['处理'])==(q['status']=='prohibited'),'reuse status scope')
require(len(re.findall(r'<a id="术\d+"', (BASE/'阅读版/通用魔法-新增.md').read_text()))==127,'unique new spell count')
for p,text in body_text.items():
    ids=re.findall(r'<a id="([^"]+)"',text)
    require(len(ids)==len(set(ids)),'duplicate stage anchor '+p.name)
    require(not re.search(r'\d\s*(?:点)?(?:通用|躯体|心智)?AP',text,re.I),'old AP '+p.name)
    require(not re.search(r'耐力|体质|决心|沉着|操控|操纵',text),'old attributes '+p.name)
    require(not re.search(r'(?<![A-Za-z])[DCBAS]{1,3}\s*[+＋]\s*\d+',text),'old acquisition price '+p.name)
    require(not re.search(r'见原文|照原效果|原文效果不变',text),'mechanic placeholder '+p.name)
for p in [*body_text, BASE/'共用技艺判定.md',BASE/'README.md',* (BASE/'依赖').glob('*.md')]:
    for link in re.findall(r'\[[^\]]*\]\(([^)]+)\)',p.read_text()):
        if re.match(r'https?:|mailto:|#',link):continue
        file,_,anchor=unquote(link).partition('#');dst=(p.parent/file).resolve()
        require(dst.is_file(),'broken link '+p.name+' '+link)
        if anchor:require(anchor in anchors(dst),'broken link anchor '+link)
common=(BASE/'共用技艺判定.md').read_text();foundation=(BASE/'依赖/基础机制.md').read_text()
for token in ['L(属性)','A(属性)','快医3＋2','反射锁','向下取整','不构成三个互斥','普通输入']:
    require(token in common,'common boundary '+token)
for token in ['攻击＋2DP','总防御','每层','⌊(感知＋力量)÷4⌋','15、20、25','内力心法','武器伤害一半']:
    require(token in foundation or token=='每层' and '逐层' in foundation,'dependency boundary '+token)
require(len(rows('未决集中表.tsv'))==4,'unresolved count')
require(not (BASE/'_build.py').exists() and not (BASE/'_patches.py').exists(),'temporary rule generator remains')
print(json.dumps({'result':'PASS','sources':192,'source_nonempty_lines':len(coverage),'reused_sources':24,'official_occurrences':222,'official_unique':215,'new_source_chapters':141,'new_spell_occurrences':134,'new_spells_unique':127,'reading_files':142,'unresolved_branches':4},ensure_ascii=False))
