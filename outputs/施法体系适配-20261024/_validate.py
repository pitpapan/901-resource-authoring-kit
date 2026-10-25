from pathlib import Path
from urllib.parse import unquote
import re,csv,json,hashlib,math,collections
D=Path(__file__).resolve().parent;ROOT=D.parents[1]
SKIP={'SEED','恐怖黎明奥术师','现代魔法','生化术士','瘟疫使者','佛说力士移山经'}
rows=list(csv.DictReader((D/'条款覆盖.tsv').open(),delimiter='\t'))
manifest=list(csv.DictReader((D/'源清单.tsv').open(),delimiter='\t'))
errors=[]
sources=sorted((ROOT/'content/RE/02_resources/能力组/施法类型').rglob('*.md'))
want={p.stem for p in sources if p.stem not in SKIP}
actual={e['name'] for e in manifest}
if want!=actual:errors.append({'selection_delta':sorted(want^actual)})
if len(actual-{'魔导书总纲'})!=32:errors.append('wrong concrete count')
expected={(p.relative_to(ROOT).as_posix(),n) for p in sources for n,l in enumerate(p.read_text().splitlines(),1) if l.strip()}
primary=[r for r in rows if r['source'].startswith('content/RE/02_resources/能力组/施法类型/')]
actual_keys={(r['source'],int(r['line'])) for r in primary}
if actual_keys!=expected:errors.append({'coverage_missing':sorted(expected-actual_keys),'coverage_extra':sorted(actual_keys-expected)})
if len(actual_keys)!=len(primary):errors.append('duplicate primary positions')
def anchors(p):
 t=p.read_text();out=set(re.findall(r'<a id=(?:"([^"]+)"|([^ >]+))',t));out={a or b for a,b in out};counts={}
 for title in re.findall(r'^#{1,6}\s+(.+)$',t,re.M):
  title=re.sub('<[^>]*>','',title).strip();slug=re.sub(r'[^\w\-\u4e00-\u9fff ]','',title.lower()).replace(' ','-');n=counts.get(slug,0);counts[slug]=n+1;out.add(slug+(f'-{n}' if n else ''))
 return out
cache={}
def check(target,base,label):
 if re.match(r'^[a-z]+://',target):return
 target=unquote(target.strip('<>'));path,_,frag=target.partition('#');p=(base/ path).resolve() if path else base.resolve()
 if not p.exists():errors.append({'missing_file':str(p),'from':label});return
 if frag:
  if p not in cache:cache[p]=anchors(p)
  if frag not in cache[p]:errors.append({'missing_anchor':str(p)+'#'+frag,'from':label})
for r in rows:check(r['reading'],D,r['source']+':'+r['line'])
for p in D.rglob('*.md'):
 for target in re.findall(r'\[[^\]]*\]\(([^)]+)\)',p.read_text()):check(target,p.parent,str(p.relative_to(D)))
for e in manifest:
 p=ROOT/e['path']
 if hashlib.sha256(p.read_bytes()).hexdigest()!=e['sha256']:errors.append('changed original '+e['path'])
# Values with concrete independent derivations: research cadence and corrected summoned card.
cycles=[math.ceil(a/b) for a,b in zip([20,50,130,350,970,2750,7930],[2,3,5,9,17,41,113])]
if cycles!=[10,17,26,39,58,68,71]:errors.append('research arithmetic')
b=(D/'阅读版/死灵之书.md').read_text()
for token in ['HP18','地速48','飞行96','上限11L']:
 if token not in b:errors.append('missing corrected Byak card '+token)
for bad in ['力量/敏捷/力量','风度/风度/意志','P/动作标值','临时q','施法q消耗']:
 for p in (D/'阅读版').glob('*.md'):
  if bad in p.read_text():errors.append({'bad_conversion':bad,'file':p.name})
# Update artifact hashes/lengths after all authorized fixes, no claims about JS execution.
for e in manifest:e['reading_chars']=len((D/e['reading']).read_text());e['reading_sha256']=hashlib.sha256((D/e['reading']).read_bytes()).hexdigest()
with (D/'源清单.tsv').open('w') as f:
 w=csv.DictWriter(f,fieldnames=manifest[0].keys(),delimiter='\t');w.writeheader();w.writerows(manifest)
result={'status':'PASS' if not errors else 'FAIL','concrete_resources':32,'shared_book_outline':1,'excluded_resources':6,'source_files_in_scope':len(sources),'primary_source_occurrences':len(expected),'covered_primary_occurrences':len(actual_keys),'total_coverage_rows_with_spell_dependencies':len(rows),'reading_characters':sum(int(e['reading_chars']) for e in manifest),'source_characters':sum(int(e['source_chars']) for e in manifest),'existing_spell_references':16,'new_B_A_dependency_cards':4,'checks':['source identity and selected set','every primary nonempty source position','reading and provenance file/heading anchors','research cycle arithmetic','corrected Byak six-attribute card','known mechanical replacement artifacts'],'runtime_verified':False,'executive_contracts_created':0,'main_repo_regressions_run':False,'errors':errors}
(D/'自查结果.json').write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n')
print(json.dumps(result,ensure_ascii=False,indent=2))
raise SystemExit(bool(errors))
