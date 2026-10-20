#!/usr/bin/env python3
"""Bounded SessionStart context. Optional local JSON config supplies pins and cwd mappings."""
import argparse
import json
import os
from pathlib import Path
import sys
from memory import budget, cli, emit, load_notes, vault
from registry import due, state


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--hook', action='store_true', help='read SessionStart JSON stdin; unset vault is a no-op')
    ap.add_argument('--config', default=os.environ.get('LLM_WIKI_CONFIG'))
    ap.add_argument('--cwd')
    ap.add_argument('--max-bytes', type=budget, default=4096)
    args = ap.parse_args()
    event = json.load(sys.stdin) if args.hook else {}
    try:
        root = vault()
    except ValueError:
        if args.hook:
            return
        raise
    config = json.loads(Path(args.config).read_text(encoding='utf-8')) if args.config else {}
    cwd = Path(args.cwd or event.get('cwd') or os.getcwd()).resolve()
    mappings = config.get('projects', {})
    if not isinstance(mappings, dict) or not isinstance(config.get('pinned', []), list):
        raise ValueError('config: projects 객체와 pinned 목록 필요')
    matching = [(Path(p).expanduser().resolve(), name) for p, name in mappings.items()
                if cwd.is_relative_to(Path(p).expanduser().resolve())]
    project = max(matching, key=lambda pair: len(pair[0].parts))[1] if matching else None
    redirects = state(root).get('redirects', {})
    pins = [redirects.get(p, p) for p in config.get('pinned', [])]
    all_notes = load_notes(root)
    notes = [n for n in all_notes if n.status == 'active']
    selected = [n for n in notes if (not n.project or n.project == project) and
                (n.rel in pins or n.meta.get('pinned') == 'true' or (project and n.project == project))]
    selected.sort(key=lambda n: (0 if n.rel in pins or n.meta.get('pinned') == 'true' else 1, n.rel))
    recall = Path(__file__).resolve().with_name('recall.py')
    text = (f'## LLM Wiki memory (selected summaries; project={project or "unmapped"})\n'
            f'Before applying a rule, read its source. Search relevant memories with:\n'
            f'python3 "{recall}" KEYWORDS [--project NAME]; use --read PATH for full text.\n'
            'Other memories remain searchable; summaries are not the complete vault.\n')
    if due(root, all_notes)['due']:
        text += ('Memory consolidation is due. Before creating another memory, read this plugin SKILL.md and run '
                 'consolidate.py; review/merge/prune stored notes and rebuild MEMORY.md.\n')
    if not selected:
        text += 'No pinned/current-project memories configured; use targeted recall.\n'
    text += ''.join(n.summary() for n in selected)
    emit(text, args.max_bytes, whole_lines=True)


if __name__ == '__main__':
    cli(main)
