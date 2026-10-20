#!/usr/bin/env python3
"""Inventory -> host-agent semantic decisions -> transactional merge/prune/index rebuild.
No arguments emits the work packet. --plan validates; --apply commits the reviewed packet.
"""
import argparse
from collections import defaultdict
from contextlib import nullcontext
import copy
import json
import os
from pathlib import Path, PurePosixPath
import re
from urllib.parse import quote, unquote
from memory import cli, digest, edit_note, inside, load_notes, locked, note_path, split_note, today, vault
from maintain import validate_lifecycle
from registry import STATE, due, next_state, render_index, scope, snapshot, state
from transactions import apply_batch, read_optional


def text_field(action, key):
    value=action.get(key)
    if not isinstance(value,str) or not value.strip():raise ValueError(f'{key}: nonempty string required')
    if key=='description' and ('\n' in value or '\r' in value):raise ValueError('description must be one line')
    return value


def rewrite_links(text, rel, replacements, dropped, all_paths, aliases=None):
    def destination(value, wiki=False):
        angled=value.startswith('<') and value.endswith('>')
        if angled:value=value[1:-1]
        base, sep, anchor=value.partition('#')
        if not base or re.match(r'[a-zA-Z][\w+.-]*:',base):return None, value
        base=unquote(base)
        if wiki:
            relative=os.path.normpath(str(PurePosixPath(rel).parent/base)).replace('\\','/')
            candidates=sorted(set([p for p in all_paths if p==base or p==base+'.md' or
                                   Path(p).stem==base or Path(p).name==base or
                                   (base.startswith('.') and p in (relative,relative+'.md'))]
                                  + (aliases or {}).get(base,[])))
            if len(candidates)!=1:
                if any(p in dropped for p in candidates):raise ValueError(f'{rel}: ambiguous wiki link {base}')
                return None,value
            resolved=candidates[0]
        else:
            resolved=os.path.normpath(str(PurePosixPath(rel).parent/base)).replace('\\','/')
        if resolved not in dropped:return None,value
        if resolved not in replacements:raise ValueError(f'{rel}: incoming link to dropped note {resolved}')
        target=replacements[resolved]
        output=target[:-3] if wiki else os.path.relpath(target,str(PurePosixPath(rel).parent)).replace('\\','/')
        if not wiki:output=quote(output,safe='/')
        output += sep+anchor if sep else ''
        return target,('<'+output+'>' if angled else output)
    def md(match):
        target,value=destination(match[2])
        return f'{match[1]}{value}{match[3]}' if target else match[0]
    def wiki(match):
        value,sep,label=match[1].partition('|')
        target,new=destination(value,wiki=True)
        return '[['+new+(sep+label if sep else '')+']]' if target else match[0]
    text=re.sub(r'(\]\()(<[^>]+>|[^\s)]+)([^)]*\))',md,text)
    text=re.sub(r'\[\[([^\]]+)\]\]',wiki,text)
    # Reference-style Markdown destinations are also incoming links.
    def reference(match):
        target,value=destination(match[2])
        return match[1]+value+match[3] if target else match[0]
    text=re.sub(r'(?m)^(\s*\[[^\]]+\]:\s*)(\S+)([^\n]*)$',reference,text)
    text=re.sub(r'((?:href|src)\s*=\s*["\'])([^"\']+)(["\'])',md,text,flags=re.I)
    return text


def packet(root,notes):
    groups=defaultdict(list)
    for n in notes:groups[scope(n)].append(n.rel)
    reviewed=state(root).get('reviewed',{})
    return {'snapshot':snapshot(root,notes),'maintenance':due(root,notes),
            'workflow':'Read every source. Decide keep/update/merge/drop; preserve exceptions and evidence. No age-only deletion.',
            'groups':dict(groups),'notes':{n.rel:{'description':n.meta.get('description'),
            'status':n.status,'bytes':len(n.text.encode()),'tags':n.meta.get('tags'),
            'changed_since_review':reviewed.get(n.rel)!=digest(n.text.encode())} for n in notes}}


def prepare(root,plan):
    notes=load_notes(root)
    current=snapshot(root,notes)
    if plan.get('snapshot')!=current:raise ValueError('stale/incomplete snapshot; rescan and review changes')
    original={n.rel:n for n in notes};result=copy.deepcopy(original)
    aliases=defaultdict(list)
    for n in notes:
        values=n.meta.get('aliases',[])
        if isinstance(values,str):
            values=[x.strip().strip("'\"") for x in values.strip('[]').split(',') if x.strip()]
        for value in values:aliases[value].append(n.rel)
    actions=plan.get('actions')
    if not isinstance(actions,list):raise ValueError('actions list required')
    covered=set();removed=set();replacements={};summary=[]
    for action in actions:
        if not isinstance(action,dict) or set(action)-{'op','reason','path','target','sources','body','description','evidence'}:
            raise ValueError('invalid action fields')
        reason=text_field(action,'reason')
        op=action.get('op')
        if op not in ('keep','update','merge','drop'):raise ValueError('unknown consolidation operation')
        target=action.get('target') if op=='merge' else action.get('path')
        sources=action.get('sources',[]) if op=='merge' else []
        if op=='merge' and (not isinstance(sources,list) or not sources):raise ValueError('merge requires source paths')
        paths=[target]+sources
        for p in paths:note_path(root,p)
        if len(set(paths))!=len(paths) or any(p not in original or p in covered for p in paths):
            raise ValueError('duplicate/unknown action path')
        covered.update(paths)
        if op=='drop':
            text_field(action,'evidence')
            del result[target];removed.add(target)
        elif op in ('merge','update'):
            body=text_field(action,'body');description=text_field(action,'description')
            n=result[target]
            fields={'description':description,'index_hook':description,'updated':today()}
            if op=='merge':
                if any(original[p].project!=n.project or original[p].meta.get('type')!=n.meta.get('type') for p in sources):
                    raise ValueError('merge must preserve project and type scope')
                fields.update(status='active',superseded_by=None)
                keys=set()
                for p in paths:
                    m=original[p].meta
                    if m.get('memory_key'):keys.add(m['memory_key'])
                    keys.update(m.get('memory_keys',[]))
                if keys:fields['memory_keys']=sorted(keys)
                if any(original[p].meta.get('pinned')=='true' for p in paths):fields['pinned']=True
                for p in sources:
                    del result[p];removed.add(p);replacements[p]=target
            n.text=edit_note(n.text,fields,body)
            _,n.meta,n.body=split_note(n.text)
        summary.append({'op':op,'paths':paths,'reason':reason})
    if covered!=set(original):raise ValueError('every snapshot note needs a keep/update/merge/drop decision')
    for rel,n in result.items():
        body=rewrite_links(n.body,rel,replacements,removed,set(original),aliases)
        fields={}
        if n.meta.get('superseded_by') in replacements:
            fields['superseded_by']=replacements[n.meta['superseded_by']]
        if body!=n.body or fields:
            fields['updated']=today()
            n.text=edit_note(n.text,fields,body);_,n.meta,n.body=split_note(n.text)
    validate_lifecycle(list(result.values()))
    # Non-note root documents and HTML are not silently edited. Refuse dangling references.
    external=[p for p in root.glob('*.md') if p.name!='MEMORY.md']
    external.extend(root.glob('*.html'))
    for dirname in ('user','feedback','project','reference','projects'):
        external.extend(inside(root,dirname).rglob('*.html'))
        external.extend(p for p in inside(root,dirname).rglob('*.md') if p.relative_to(root).as_posix() not in original)
    for p in external:
        rel=p.relative_to(root).as_posix();text=inside(root,rel).read_text(encoding='utf-8')
        updated=rewrite_links(text,rel,replacements,removed,set(original),aliases)
        if updated!=text:raise ValueError(f'{rel}: external incoming link must be updated first')
    old_index=read_optional(inside(root,'MEMORY.md'))
    if (digest(old_index) if old_index is not None else None)!=current['MEMORY.md']:
        raise ValueError('index changed during planning')
    index=render_index(list(result.values()),(old_index or b'').decode())
    batch=[]
    for rel,n in original.items():
        before=inside(root,rel).read_bytes()
        if digest(before)!=current[rel]:raise ValueError(f'{rel}: changed during planning')
        after=(before if result[rel].text==n.text else result[rel].text.encode()) if rel in result else None
        if before!=after:batch.append((rel,before,after))
    if old_index!=index.encode():batch.append(('MEMORY.md',old_index,index.encode()))
    state_data=json.loads(next_state(root,list(result.values()),consolidated=True))
    redirects=state(root).get('redirects',{})
    for old,target in list(redirects.items()):
        if target in removed:redirects[old]=replacements.get(target)
    redirects.update({old:replacements.get(old) for old in removed})
    state_data['redirects']=redirects
    old_state=read_optional(inside(root,STATE))
    if (digest(old_state) if old_state is not None else None)!=current[STATE]:
        raise ValueError('state changed during planning')
    batch.append((STATE,old_state,(json.dumps(state_data,ensure_ascii=False,indent=2)+'\n').encode()))
    return batch,{'actions':summary,'notes_before':len(original),'notes_after':len(result),
                  'deleted':sorted(removed),'rewritten':[rel for rel,_,after in batch if after is not None],
                  'index_before_bytes':len(old_index or b''),'index_after_bytes':len(index.encode()),
                  'index_preview':index}


def main():
    ap=argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--plan')
    ap.add_argument('--apply',action='store_true')
    args=ap.parse_args();root=vault()
    if args.apply and not args.plan:ap.error('--apply requires --plan')
    if not args.plan:
        print(json.dumps(packet(root,load_notes(root)),ensure_ascii=False,indent=2));return
    with locked(root) if args.apply else nullcontext():
        plan=json.loads(Path(args.plan).read_text(encoding='utf-8'))
        batch,result=prepare(root,plan)
        result['mode']='apply' if args.apply else 'dry-run'
        if args.apply:result['backup']=apply_batch(root,batch)
        print(json.dumps(result,ensure_ascii=False,indent=2))


if __name__=='__main__':cli(main)
