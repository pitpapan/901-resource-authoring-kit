"""Shared source bindings for the magic bundle candidate contracts."""
from pathlib import Path
import csv, hashlib, json, re

BASE = Path(__file__).resolve().parents[1]
ROOT = BASE.parents[1]
VERSION = '2026-10-25.magic.1'
EXCLUDED = {'SEED','恐怖黎明奥术师','现代魔法','生化术士','瘟疫使者','佛说力士移山经'}
GRADES = ['D','C','B','A','S','SSS','九S','二十七S']

def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()

def digest(value):
    return hashlib.sha256(json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(',',':')).encode()).hexdigest()

def encoded(value):
    return json.dumps(value, ensure_ascii=False, sort_keys=True, indent=2)+'\n'

def manifest():
    with (BASE/'源清单.tsv').open() as f:
        return list(csv.DictReader(f, delimiter='\t'))

def source_id(name):
    return 'candidate-901-magic-bundle-'+hashlib.sha256(name.encode()).hexdigest()[:16]

def shared_dependencies():
    files=[ROOT/'rules/901-core-rules-v0.1.md', ROOT/'resources/execution/resource.schema.json',
           BASE/'共用901判定.md', BASE/'来源与核算.md', BASE/'未决项.md']
    files += sorted((BASE/'依赖').glob('*.md'))
    return [{'path':p.relative_to(ROOT).as_posix(),'sha256':sha(p)} for p in files]

def sections(path):
    """Every nonempty heading body is bound; tables stay intact, never guessed into effects."""
    lines=path.read_text().splitlines(keepends=True)
    headings=[(i,re.match(r'^(#{1,6})\s+(.+?)\s*$',line)) for i,line in enumerate(lines) if re.match(r'^#{1,6}\s',line)]
    rows=[];seen={}
    for n,(start,m) in enumerate(headings):
        end=headings[n+1][0] if n+1<len(headings) else len(lines)
        body=''.join(lines[start:end])
        payload=[l for l in lines[start+1:end] if l.strip() and not l.startswith(('[共用判定]','**','用途：'))]
        if not payload: continue
        heading=m[2];seen[heading]=seen.get(heading,0)+1
        uid='clause-'+hashlib.sha256((heading+'#'+str(seen[heading])).encode()).hexdigest()[:12]
        rows.append({'id':uid,'heading':heading,'reading':{'startLine':start+1,'endLine':end,'sha256':hashlib.sha256(body.encode()).hexdigest()},'body':body})
    return rows

def labels(body):
    out={}
    for line in body.splitlines():
        if ' | ' not in line and not re.match(r'^(领域|学习原价|施放|能耗|成分|射程|目标|范围|持续|冷却|P)：',line):continue
        for part in line.split(' | '):
            match=re.match(r'^([^：]{1,12})：(.*)$',part.strip())
            if match:out[match[1]]=match[2]
    return out

def legacy_prices(text):
    """Parse only literal branch+points prices. No assumed base price for a blank heading."""
    result=[]
    for m in re.finditer(r'(?<![A-Z])(二十七S|九S|SSS|[DCBAS])(?:级[:：]?\s*|\s*)\+\s*(\d+)',text):
        grade,points=m[1],int(m[2]);weight=3**GRADES.index(grade)
        row={'grade':grade,'legacyPoints':points,'branchWeight':weight,'candidateXP':5*weight+(points+99)//100,'adoptionStatus':'candidate','basis':'来源与核算.md#xp报价与预算分账'}
        if row not in result:result.append(row)
    if not result:
        explicit=re.fullmatch(r'\s*(\d+)\s*XP\s*',text,re.I)
        if explicit:result.append({'explicitXP':int(explicit[1]),'basis':'explicit-source-xp','adoptionStatus':'candidate'})
        plain=re.fullmatch(r'\s*(\d+)\s*',text)
        if plain:result.append({'grade':'ungraded','legacyPoints':int(plain[1]),'candidateXP':(int(plain[1])+99)//100,'basis':'candidate-branchless-learning-price','adoptionStatus':'candidate'})
    return result

def action_descriptors(body):
    rows=[]
    # Fixed q is an action's price, not an AP pool. Preserve the particular occurrence.
    for n,line in enumerate(body.splitlines(),1):
        for m in re.finditer(r'(?:\[q=|\(q|动作标值)(\d+)\]?(?:\))?',line):
            prefix=line[max(0,m.start()-8):m.start()]
            mode='reflex' if re.search(r'反射[^，。；]*$',prefix) else 'ordinary'
            rows.append({'kind':'fixed-action-price','q':int(m[1]),'mode':mode,'relativeLine':n,'execution':'declaration-only'})
    return rows

def build_unit(row):
    fields=labels(row['body']);body=row['body']
    return {'id':row['id'],'name':row['heading'],'reading':row['reading'],
        'learning':{'prices':legacy_prices(fields['学习原价']) if '学习原价' in fields else legacy_prices(row['heading']),'entryDoesNotGrantChildTechniques':True},
        'declaredFields':fields,'actionPrices':action_descriptors(body),
        'requiresIndependentLearning':bool(fields.get('学习原价') or legacy_prices(row['heading'])),
        'sourceBoundConditions':[{'relativeLine':i,'kind':kind} for i,line in enumerate(body.splitlines(),1)
            for kind,pattern in [('prerequisite',r'前提|必须|须有|只有'),('exclusion',r'不能|不包括|不得|无需'),('cost',r'消耗|支付|占用'),('upgrade',r'进化|提升|取代|替换'),('duration',r'持续|直到|结束'),('trigger',r'每当|当你|当角色|若|如果')]
            if re.search(pattern,line)],
        'implementationGaps':['clause-full-semantics-and-consumer-integration'],'unresolvedRuleIds':[]}
