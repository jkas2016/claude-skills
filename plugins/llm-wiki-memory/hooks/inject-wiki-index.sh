#!/usr/bin/env bash
# Use the plugin source beside this script, even when invoked through a symlink.
set -euo pipefail

export LLM_WIKI_PATH="${LLM_WIKI_PATH:-$HOME/Library/Mobile Documents/iCloud~md~obsidian/Documents/LLM-Wiki}"
event="${1:-SessionStart}"
hook_dir="$(dirname "$0")"
source_path="$(python3 -c 'from pathlib import Path; import sys; print(Path(sys.argv[1]).resolve())' "$0")"

args=(--hook)
if [[ -z "${LLM_WIKI_CONFIG:-}" && -f "$hook_dir/wiki-context.json" ]]; then
  args+=(--config "$hook_dir/wiki-context.json")
fi

context="$(python3 "$(dirname "$source_path")/../skills/llm-wiki-memory/scripts/context.py" "${args[@]}")"
if [[ -z "$context" ]]; then
  printf '{}\n'
else
  printf '%s' "$context" | jq -Rs --arg event "$event" '{hookSpecificOutput: {hookEventName: $event, additionalContext: .}}'
fi
