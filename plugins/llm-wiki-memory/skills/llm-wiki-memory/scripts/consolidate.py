#!/usr/bin/env python3
"""Inventory -> host-agent semantic decisions -> transactional merge/prune/index rebuild.
No arguments emits the work packet. --plan validates; --apply commits the reviewed packet.
"""
import argparse
from collections import defaultdict
from contextlib import nullcontext
import copy
from datetime import datetime, timedelta, timezone
import json
import os
from pathlib import Path, PurePosixPath
import re
import sys
from urllib.parse import quote, unquote
from memory import cli, digest, edit_note, inside, load_archives, load_notes, locked, note_path, split_note, today, vault
from maintain import validate_lifecycle
from registry import STATE, due, next_state, render_index, scope, snapshot, state
from transactions import apply_batch, read_optional
from usage import NoteUsage, compact, summary as usage_summary


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


def note_date(value):
    if not isinstance(value, str):
        return None
    try:
        time = datetime.fromisoformat(value.replace('Z', '+00:00'))
    except ValueError:
        return None
    return time.replace(tzinfo=timezone.utc) if time.tzinfo is None else time.astimezone(timezone.utc)


def retirement_candidates(notes, usage, kept, now):
    if usage.tracking_since is None:
        return {}
    cutoff = now - timedelta(days=30)
    candidates = {}
    for note in notes:
        if note.status != 'active' or note.meta.get('pinned') == 'true' or note.meta.get('type') == 'user':
            continue
        kept_at = note_date(kept.get(note.rel))
        if kept_at is not None and kept_at >= cutoff:
            continue
        stats = usage.notes.get(note.rel, NoteUsage())
        created = note_date(note.meta.get('created')) or usage.tracking_since
        baseline = stats.last_read or max(usage.tracking_since, created)
        if baseline < cutoff:
            candidates[note.rel] = {'reads_total': stats.reads_total, 'exposed_30d': stats.exposed_30d,
                                    'last_read': stats.last_read.isoformat() if stats.last_read else None,
                                    'baseline': baseline.isoformat()}
    return candidates


def purge_schedule(archives, usage):
    schedule = {}
    for note in archives:
        archived_at = note_date(note.meta.get('archived_at'))
        if archived_at is not None:
            last_read = usage.notes.get(note.rel, NoteUsage()).last_read
            schedule[note.rel] = max(archived_at, last_read or archived_at) + timedelta(days=60)
    return schedule


def purge_candidates(archives, usage, now):
    return sorted(rel for rel, deadline in purge_schedule(archives, usage).items() if deadline < now)


def packet(root,notes):
    groups=defaultdict(list)
    for n in notes:groups[scope(n)].append(n.rel)
    reviewed=state(root).get('reviewed',{})
    archives = load_archives(root)
    now = datetime.now(timezone.utc)
    usage = usage_summary(root, now)
    kept = state(root).get('retention_kept', {})
    return {'snapshot':snapshot(root,notes + archives),'maintenance':due(root,notes),
            'retirement_candidates': retirement_candidates(notes, usage, kept, now),
            'workflow':'Read every source. Decide keep/update/merge/drop/compress/archive. Active notes are never deleted by age alone. Approved archive files may be purged after 60 days without a read.',
            'groups':dict(groups),'notes':{n.rel:{'description':n.meta.get('description'),
            'status':n.status,'bytes':len(n.text.encode()),'tags':n.meta.get('tags'),
            'changed_since_review':reviewed.get(n.rel)!=digest(n.text.encode())} for n in notes}}


def prepare(root,plan):
    notes=load_notes(root)
    archives = load_archives(root)
    current = snapshot(root, notes + archives)
    now = datetime.now(timezone.utc)
    usage = usage_summary(root, now)
    kept = dict(state(root).get('retention_kept', {}))
    retirees = retirement_candidates(notes, usage, kept, now)
    purge = purge_candidates(archives, usage, now)
    archive_batch = []
    archived = set()
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
        if op not in ('keep','update','merge','drop','compress','archive'):raise ValueError('unknown consolidation operation')
        target=action.get('target') if op=='merge' else action.get('path')
        sources=action.get('sources',[]) if op=='merge' else []
        if op=='merge' and (not isinstance(sources,list) or not sources):raise ValueError('merge requires source paths')
        paths=[target]+sources
        for p in paths:note_path(root,p)
        if len(set(paths))!=len(paths) or any(p not in original or p in covered for p in paths):
            raise ValueError('duplicate/unknown action path')
        covered.update(paths)
        if op == 'keep' and target in retirees:
            kept[target] = now.isoformat()
        if op in ('compress', 'archive'):
            n = original[target]
            if op == 'archive':
                if n.meta.get('pinned') == 'true':
                    raise ValueError(f'{target}: pinned note cannot be archived')
                archive_rel = f'_archive/{target}'
                del result[target]
                removed.add(target)
                archived.add(target)
            else:
                archive_rel = f'_archive/{target[:-3]}.full-{today().replace("-", "")}.md'
                body = text_field(action, 'body')
                description = text_field(action, 'description')
                current_note = result[target]
                current_note.text = edit_note(n.text, {'description': description, 'index_hook': description,
                                                         'updated': today(), 'full_text': archive_rel}, body)
                _, current_note.meta, current_note.body = split_note(current_note.text)
            if note_path(root, archive_rel).exists():
                raise ValueError(f'ARCHIVED_EXISTS: {archive_rel}')
            archive_text = edit_note(n.text, {'status': 'archived', 'archived_at': now.isoformat(),
                                             'archived_from': target, 'superseded_by': None})
            archive_batch.append((archive_rel, None, archive_text.encode('utf-8')))
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
    if covered!=set(original):raise ValueError('every snapshot note needs a keep/update/merge/drop/compress/archive decision')
    for rel,n in result.items():
        body=rewrite_links(n.body,rel,replacements,removed,set(original),aliases)
        fields={}
        if n.meta.get('full_text') in purge:
            fields['full_text'] = None
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
    for source, target in replacements.items():
        source_usage = usage.notes.get(source)
        if source_usage is None:
            continue
        target_usage = usage.notes.setdefault(target, NoteUsage())
        target_usage.reads_30d += source_usage.reads_30d
        if source_usage.last_read and (not target_usage.last_read or source_usage.last_read > target_usage.last_read):
            target_usage.last_read = source_usage.last_read
    index=render_index(list(result.values()),(old_index or b'').decode(), usage.notes)
    batch=[]
    for rel,n in original.items():
        before=inside(root,rel).read_bytes()
        if digest(before)!=current[rel]:raise ValueError(f'{rel}: changed during planning')
        after=(before if result[rel].text==n.text else result[rel].text.encode()) if rel in result else None
        if before!=after:batch.append((rel,before,after))
    for rel in purge:
        before = note_path(root, rel).read_bytes()
        if digest(before) != current[rel]:
            raise ValueError(f'{rel}: changed during planning')
        archive_batch.append((rel, before, None))
    batch.extend(archive_batch)
    if old_index!=index.encode():batch.append(('MEMORY.md',old_index,index.encode()))
    state_data=json.loads(next_state(root,list(result.values()),consolidated=True))
    redirects=state(root).get('redirects',{})
    for old,target in list(redirects.items()):
        if target in removed - archived:redirects[old]=replacements.get(target)
    redirects.update({old:replacements.get(old) for old in removed - archived})
    state_data['redirects']=redirects
    state_data['retention_kept'] = {rel: time for rel, time in kept.items() if rel in result}
    old_state=read_optional(inside(root,STATE))
    if (digest(old_state) if old_state is not None else None)!=current[STATE]:
        raise ValueError('state changed during planning')
    batch.append((STATE,old_state,(json.dumps(state_data,ensure_ascii=False,indent=2)+'\n').encode()))
    return batch,{'actions':summary,'notes_before':len(original),'notes_after':len(result),
                  'deleted':sorted(removed - archived),'purge':purge,'rewritten':[rel for rel,_,after in batch if after is not None],
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
        if args.apply:
            result['backup'] = apply_batch(root, batch)
            try:
                compact(root, datetime.now(timezone.utc))
            except (OSError, ValueError, TypeError, KeyError) as exc:
                print(f'usage compaction failed: {exc}', file=sys.stderr)
        print(json.dumps(result,ensure_ascii=False,indent=2))


if __name__=='__main__':cli(main)
