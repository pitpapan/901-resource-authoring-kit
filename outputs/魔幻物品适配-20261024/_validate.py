#!/usr/bin/env python3
"""Read-only artifact checks; only writes 自查结果.json in this output directory."""
from pathlib import Path
import collections,csv,hashlib,json,re,sys,unicodedata
from urllib.parse import unquote
B=Path(__file__).resolve().parent;R=B.parent.parent
issues=[];checks={}
def need(ok,message):
 if not ok:issues.append(message)
def read_tsv(name):
 p=B/name
 if not p.exists():issues.append('missing '+name);return []
 return list(csv.DictReader(p.open(),delimiter='\t'))
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def norm(s):return re.sub(r'[^\w]','',unicodedata.normalize('NFKC',s).lower())
def slug(s):
 s=re.sub('<[^>]+>','',s);s=s.replace('`','').replace('*','').strip().lower().replace(' ','-')
 return re.sub(r'[^\w\-\u4e00-\u9fff]','',s)
A={}
def anchors(p):
 if p not in A:
  t=p.read_text();ns=re.findall(r'<a\s+id=[\"\']?([^\"\' >]+)',t)
  ns += [slug(h) for h in re.findall(r'^#{1,6}\s+(.+)$',t,re.M)]
  A[p]=set(ns)
 return A[p]
def link(target,base,where):
 if target.startswith(('http:','https:','mailto:','data:')):return
 target=target.strip('<>');parts=target.split('#',1);rel=unquote(parts[0]);p=(base/rel).resolve() if rel else basefile
 need(p.exists(),f'{where}: missing {target}')
 if p.exists() and len(parts)>1 and parts[1]:
  need(p.suffix=='.md',f'{where}: non-md anchor {target}')
  if p.suffix=='.md':need(unquote(parts[1]) in anchors(p),f'{where}: missing anchor {target}')
M=read_tsv('源清单.tsv');N=read_tsv('名称索引.tsv');C=read_tsv('条款覆盖.tsv');D=read_tsv('依赖清单.tsv');U=read_tsv('未决.tsv');O=read_tsv('旧派生与属性证据.tsv')
expected={str(p.relative_to(R)) for p in (R/'content/RE/02_resources/物品/魔幻物品').rglob('*.md')}
expected|={str(p.relative_to(R)) for p in (R/'content/RE/02_resources/物品/物品改造/非科技改造').glob('魔幻*.md')}
need(len(expected)==38,'expected source glob no longer 38');need(len(M)==38,'manifest row count !=38');need({m['source'] for m in M}==expected,'source set differs from authorized glob')
need(len({m['source'] for m in M})==len(M),'duplicate manifest source');need(len({m['reading'] for m in M})==38,'duplicate/missing reading file');need([m['id'] for m in M]==[f'SRC{i:02}' for i in range(1,39)],'source IDs not SRC01..38')
positions=set();source_lines={};total_chars=0;reading_chars=0
for m in M:
 s=R/m['source'];p=B/m['reading'];need(s.exists() and p.exists(),'missing manifest file '+m['source'])
 if not s.exists() or not p.exists():continue
 source_lines[m['source']]=s.read_text().splitlines();t=p.read_text()
 need(sha(s)==m['source_sha256'],'source hash changed '+m['source']);need(sha(p)==m['reading_sha256'],'reading hash stale '+m['reading'])
 need(m['state']=='精修候选','unrefined manifest '+m['reading']);need(not re.search('待本章精读|待精读|机械转换初稿|待精修',t),'unrefined header '+m['reading']);need('候选阅读版' in t,'missing identity '+m['reading'])
 need(int(m['source_chars'])==len(s.read_text()),'source char count '+m['source']);need(int(m['reading_chars'])==len(t),'reading char count '+m['reading']);need(int(m['source_nonempty'])==sum(bool(l.strip()) for l in source_lines[m['source']]),'source nonempty count '+m['source'])
 need(int(m['detected_names'])==sum(n['source']==m['source'] for n in N),'name count mismatch '+m['source'])
 total_chars+=len(s.read_text());reading_chars+=len(t)
 for i,l in enumerate(source_lines[m['source']],1):
  if l.strip():positions.add((m['source'],i))
 need(not re.search(r'力量/敏捷/力量|风度/风度/意志|不生成q|上限动作标值',t),'corrupt replacement '+m['reading'])
 got={(c['source'],int(c['line'])) for c in C}
need(len(C)==len(got),'duplicate coverage source position');need(got==positions,'coverage does not match all nonempty source lines');need(len(C)==8759,'coverage count differs from known 8759')
allowed={'来源元信息','版式省略','背景省略','旧派生移核算','九属性合并','共享字段合并','已适配-共享字段合并','已适配','授权替换XP'}
for c in C:
 need(c['state'] in allowed,'unknown coverage state '+c['state']);link(c['reading'],B,'coverage '+c['source']+':'+c['line'])
need([n['id'] for n in N]==[f'Q{i:04}' for i in range(1,len(N)+1)],'name IDs not contiguous')
for n in N:
 need(n['source'] in expected,'index source not authorized '+n['source']);need(n['name'].strip()==n['name'] and bool(n['name']),'blank/spaced name '+n['id']);need('。' not in n['name'] and '\n' not in n['name'] and len(n['name'])<=60,'sentence masquerades as name '+n['id'])
 need(n['kind'] in ('物品/变体检索','升级/组件/卡内效果','共用规则/分类'),'index kind '+n['id'])
 if n['source'] in source_lines:need(1<=int(n['line'])<=len(source_lines[n['source']]),'index bad source line '+n['id'])
 link(n['reading'],B,'index '+n['id'])
 if n['name'] in {Path(m['source']).stem for m in M}:need(n['kind']=='共用规则/分类','chapter title classified as item '+n['id'])
for d in D:
 p=R/d['path'];need(p.exists(),'missing dependency '+d['path'])
 if p.exists():need(sha(p)==d['sha256'],'dependency hash stale '+d['path'])
for u in U:
 p=R/u['source'];need(p.exists(),'unresolved source missing '+u['id']);need(u['kind'] in ('缺参','语义冲突'),'nonsemantic issue in unresolved '+u['id']);need(bool(u['gap'] and u['impact'] and u['recommendation']),'incomplete unresolved '+u['id']);link(u['reading'],B,'unresolved '+u['id'])
 if p.exists():
  ls=p.read_text().splitlines();need(1<=int(u['start'])<=int(u['end'])<=len(ls),'unresolved line range '+u['id'])
  for ln,quote in re.findall(r'(\d+)行：(.+?)(?= / \d+行：|$)',u['quote']):
   need(norm(quote) in norm(ls[int(ln)-1]),'unresolved excerpt differs from raw source '+u['id'])
for o in O:
 need(o['source'] in source_lines,'legacy source not manifest')
 if o['source'] in source_lines:need(o['original']==source_lines[o['source']][int(o['line'])-1],'legacy source quote mismatch')
# Links in human-facing Markdown, including exact current resources anchors.
for basefile in B.rglob('*.md'):
 for target in re.findall(r'(?<!!)\[[^\]]*\]\(([^)\n]+)\)',basefile.read_text()):link(target,basefile.parent,str(basefile.relative_to(B)))
need(set(m['reading'] for m in M)=={str(p.relative_to(B)) for p in (B/'阅读版').glob('*.md')},'unmanifested reading file')
# Small semantic sentinels for the conversions actually edited; not an execution/balance suite.
def has(file,parts):
 t=(B/file).read_text()
 for part in parts:need(part in t,'missing final clause '+file+': '+part)
has('阅读版/武器-B级武器.md',['仅用本剑作攻击时再+12增强DP','不额外发XP'])
has('阅读版/DOTA物品-二阶合成.md',['本完整冒险余下时间内本人智力相关检定+4增强DP','原额外XP已由此替换','你不能对本轮回队的成员及其衍生物','若能力发动失败'])
has('阅读版/奇物-D级奇物.md',['+3/6/12增强DP','独立来源','万灵挂饰','持续1轮'])
has('阅读版/职阶卡-1星卡牌.md',['脚的天生武器攻击+3内在DP','不再发每篇章3XP'])
has('阅读版/职阶卡-3星卡牌.md',['容量23','容量24（底4+20）'])
has('阅读版/武器-D级武器.md',['330＋2×61＋2×12＝476','普通天生攻击184DP','上限125','移动再+40（447米）'])
has('阅读版/非科技改造-魔幻材质类改造.md',['耀钢','瑟伦木','金晶','日炎真铁'])
has('共用物品判定.md',['全社交＝风度/意志','2/4/6/8AP'])
for wanted in ('银枪','邪刃','闪耀之弓','闪耀之剑','泰拉刃','种子弯刀','无头骑士剑','波涌之刃','光知将军'):
 need(any(norm(n['name'])==norm(wanted) for n in N),'missing named item '+wanted)
checks.update(source_files=len(M),refined_reading_chapters=sum(m['state']=='精修候选' for m in M),source_chars=total_chars,reading_chars=reading_chars,coverage_nonempty_positions=len(C),indexed_search_entries=len(N),index_categories=dict(collections.Counter(n['kind'] for n in N)),dependency_files=len(D),unresolved_source_issues=len(U),legacy_evidence_rows=len(O),authorized_xp_replacements=sum(c['state']=='授权替换XP' for c in C),source_set_exact={m['source'] for m in M}==expected,coverage_exact=got==positions)
checks['targeted_arithmetic']={'pala_mental_base':(6+6)//4,'pala_3star_capacity':(6+6)//4+20,'cuchulainn_capacity':(6+11)//4+20,'avatar_hp':330+2*61+2*12,'avatar_move':61+16+330+40,'avatar_attack':61+15+49+11+48,'avatar_cap':61+15+49,'dota_lightning_total_targets':1+7}
need(checks['targeted_arithmetic']=={'pala_mental_base':3,'pala_3star_capacity':23,'cuchulainn_capacity':24,'avatar_hp':476,'avatar_move':447,'avatar_attack':184,'avatar_cap':125,'dota_lightning_total_targets':8},'targeted arithmetic mismatch')
result={'status':'FAIL' if issues else 'PASS','scope':'静态交付完整性与针对性数值/条款核验；不是语义完备证明、模型实战或JS执行验证','checks':checks,'errors':issues}
(B/'自查结果.json').write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n')
print(json.dumps(result,ensure_ascii=False,indent=2));sys.exit(bool(issues))
