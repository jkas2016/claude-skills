#!/usr/bin/env python3
"""Preview/install a bounded memory SessionStart hook in a selected Claude settings file.
Only the exact legacy standalone cat command or this installer's marked hook is replaced.
"""
import argparse
import copy
import json
from pathlib import Path
import shlex
import sys
import uuid
from memory import atomic_write, cli

MARKER = '# llm-wiki-memory-context-v1'
LEGACY = 'if [ -f "$LLM_WIKI_PATH/MEMORY.md" ]; then printf \'## Auto-memory index (from $LLM_WIKI_PATH/MEMORY.md)\\n\\n\'; cat "$LLM_WIKI_PATH/MEMORY.md"; fi'


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--settings', required=True)
    ap.add_argument('--config', help='machine-local pins/project mappings JSON path')
    ap.add_argument('--apply', action='store_true')
    args = ap.parse_args()
    path = Path(args.settings).expanduser().resolve()
    before = path.read_bytes() if path.exists() else None
    data = json.loads(before) if before else {}
    updated = copy.deepcopy(data)
    command = shlex.join([sys.executable, str(Path(__file__).resolve().with_name('context.py')), '--hook'])
    if args.config:
        config = Path(args.config).expanduser().resolve()
        json.loads(config.read_text(encoding='utf-8'))
        command += ' --config ' + shlex.quote(str(config))
    command += ' ' + MARKER
    hook = {'type': 'command', 'command': command, 'timeout': 10}
    groups = updated.setdefault('hooks', {}).setdefault('SessionStart', [])
    recognized, ambiguous = [], []
    for group in groups:
        for old in group.get('hooks', []):
            cmd = old.get('command', '')
            if old.get('type') == 'command' and (cmd == LEGACY or cmd.endswith(' ' + MARKER)):
                recognized.append((group, old))
            elif 'LLM_WIKI_PATH' in cmd and 'MEMORY.md' in cmd or 'context.py' in cmd:
                ambiguous.append(cmd)
    if ambiguous:
        raise ValueError('알 수 없는 memory hook 존재: 자동 교체하지 않음; 먼저 해당 명령 검토')
    for group, old in recognized:
        group['hooks'].remove(old)
    groups[:] = [g for g in groups if g.get('hooks')]
    groups.append({'hooks': [hook]})
    changed = updated != data
    result = {'mode': 'apply' if args.apply else 'dry-run', 'changed': changed,
              'replaced': len(recognized), 'command': command}
    if args.apply and changed:
        if (path.read_bytes() if path.exists() else None) != before:
            raise ValueError('settings 동시 변경')
        if before is not None:
            backup = path.with_name(path.name + '.llm-wiki-' + uuid.uuid4().hex + '.bak')
            atomic_write(backup, before)
            result['backup'] = str(backup)
        atomic_write(path, (json.dumps(updated, ensure_ascii=False, indent=2) + '\n').encode('utf-8'))
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == '__main__':
    cli(main)
