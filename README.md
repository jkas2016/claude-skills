# claude-skills

A [Claude Code plugin marketplace](https://code.claude.com/docs/en/plugin-marketplaces) bundling self-authored skills as individually installable plugins.

## Install

```text
/plugin marketplace add jkas2016/claude-skills
/plugin install deep-code-review@claude-skills
/plugin install llm-wiki-memory@claude-skills
```

(Public marketplace — no authentication required to add.)

## Plugins

| Plugin | What it does | Runtime | Setup required |
|---|---|---|---|
| `deep-code-review` | Whole-repo deep code audit using language rule sets ported from OpenCodeReview (Apache-2.0). Host-session, read-only — no API key. | `python3` (stdlib), `git` | None. Run `/deep-code-review` from a git repo root (no argument → current directory). |
| `llm-wiki-memory` | Shared Obsidian memory with bounded search/context, canonical updates, consolidation/pruning, and a rebuilt index. | Python 3.10+ (stdlib) | Set `LLM_WIKI_PATH`; optionally configure the bounded SessionStart hook using the [maintenance guide](plugins/llm-wiki-memory/skills/llm-wiki-memory/references/maintenance.md). |

Memory 0.3 searches summaries by default (8 results / 8192 UTF-8 bytes). Read full notes explicitly with `recall.py --read PATH`; the same byte budget applies. SessionStart context is capped at 4096 bytes. Existing seven-field notes remain compatible; lifecycle state is optional. Repeated concept keys update existing notes. Save counters/size thresholds require host-agent consolidation before further growth. Merge/drop physically remove old notes and regenerate MEMORY.md; the newest 20 committed backups remain recoverable. Hooks signal maintenance but do not perform deletion. See the [consolidation workflow](plugins/llm-wiki-memory/skills/llm-wiki-memory/references/consolidation.md).

Run memory integration tests with `python3 -m unittest discover -s plugins/llm-wiki-memory/tests -v`.

## Licensing

- Repository license: **Apache-2.0** (see `LICENSE`) — covers both plugins. `deep-code-review` bundles assets ported from OpenCodeReview (Apache-2.0); see its `references/NOTICE`.

## Secrets policy

🔒 Never commit tokens, API keys, credential files, or personal absolute paths. Reference machine-specific locations only through environment variables (e.g. `$LLM_WIKI_PATH`) or placeholders (e.g. `<your-vault-path>`).
