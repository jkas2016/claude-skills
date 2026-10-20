"""Canonical registry, compact index, and consolidation scheduling (no model calls)."""
from collections import defaultdict
import json
from pathlib import Path
import re
from urllib.parse import quote
from memory import digest, inside, today

MARKER = '<!-- llm-wiki-memory:index-v2 -->'
STATE = '.memory-state.json'


def scope(note):
    return f'projects/{note.project}' if note.project else str(note.meta.get('type', 'reference'))


def state(root):
    path = inside(root, STATE)
    value = json.loads(path.read_text(encoding='utf-8')) if path.exists() else {}
    if not isinstance(value, dict) or not isinstance(value.get('writes', 0), int):
        raise ValueError('invalid memory state')
    return value


def snapshot(root, notes):
    result = {n.rel:digest(inside(root,n.rel).read_bytes()) for n in notes}
    for rel in ('MEMORY.md', STATE):
        p=inside(root,rel)
        result[rel]=digest(p.read_bytes()) if p.exists() else None
    return result


def due(root, notes):
    s=state(root)
    index=inside(root,'MEMORY.md')
    index_bytes=index.stat().st_size if index.exists() else 0
    reasons=[]
    if s.get('writes',0)>=10: reasons.append('10 writes since consolidation')
    # Once fully reviewed, a large legitimate corpus is not an endless gate.
    if len(notes)>max(80,s.get('reviewed_count',0)+10): reasons.append('note-count growth')
    if index_bytes>12288: reasons.append('index exceeds 12 KiB')
    if not s.get('last_consolidated') and any(n.status!='active' for n in notes):
        reasons.append('legacy inactive notes need retirement review')
    return {'due':bool(reasons),'reasons':reasons,'writes':s.get('writes',0),
            'last_consolidated':s.get('last_consolidated')}


def html_pointers(index):
    return sorted(set(line for line in index.splitlines() if re.search(r'\]\([^)]*\.html\)',line)))


def render_index(notes, old_index=''):
    active=[n for n in notes if n.status=='active']
    groups=defaultdict(list)
    for n in active:groups[scope(n)].append(n)
    lines=['# MEMORY',MARKER,'',
           '활성 정본 탐색 지도. 전체 목록/원문은 recall.py로 검색한다. 생성 파일이므로 직접 누적하지 않는다.','',
           '## 핵심 기억','']
    core=sorted([n for n in active if not n.project],
                key=lambda n:(n.meta.get('pinned')!='true',n.meta.get('type')!='user',n.rel))[:8]
    for n in core:
        summary=' '.join(str(n.meta.get('index_hook',n.meta.get('description',n.rel))).split())[:100]
        lines.append(f'- [{n.meta.get("name",Path(n.rel).stem)}]({quote(n.rel,safe="/")}) — {summary}')
    lines += ['','## 주제별 탐색','']
    for name,group in sorted(groups.items()):
        # Scope directory, not another generated document. No per-note index growth.
        examples=' / '.join(str(n.meta.get('description','')).replace('\n',' ')[:45]
                            for n in sorted(group,key=lambda n:n.rel)[:2])
        lines.append(f'- [{name}]({quote(name,safe="/")}/) — {len(group)}개 정본: {examples}')
    external=html_pointers(old_index)
    if external:lines += ['','## 별도 분석 자료','']+external
    text='\n'.join(lines).rstrip()+'\n'
    if len(text.encode('utf-8'))>8192:
        raise ValueError('생성 인덱스가 8192 bytes를 초과: 범위/요약을 정리해야 함')
    return text


def next_state(root, notes, consolidated=False):
    old=state(root)
    data={**old,'version':1,'writes':0 if consolidated else old.get('writes',0)+1}
    if consolidated:
        data.update(last_consolidated=today(),reviewed_count=len(notes),
                    reviewed={n.rel:digest(n.text.encode('utf-8')) for n in notes})
    return (json.dumps(data,ensure_ascii=False,indent=2)+'\n').encode('utf-8')
