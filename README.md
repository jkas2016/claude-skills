# claude-skills

A [Claude Code plugin marketplace](https://code.claude.com/docs/en/plugin-marketplaces) bundling self-authored skills as individually installable plugins.

## Install

```text
/plugin marketplace add jkas2016/claude-skills
/plugin install deep-code-review@claude-skills
/plugin install llm-wiki-memory@claude-skills
/plugin install managing-pc-disk@claude-skills
```

(Public marketplace — no authentication required to add.)

## Plugins

| Plugin | What it does | Runtime | Setup required |
|---|---|---|---|
| `deep-code-review` | Whole-repo deep code audit using language rule sets ported from OpenCodeReview (Apache-2.0). Host-session, read-only — no API key. | `python3` (stdlib), `git` | None. Run `/deep-code-review` from a git repo root (no argument → current directory). |
| `llm-wiki-memory` | Shared Obsidian memory with bounded search/context, canonical updates, consolidation/pruning, and a rebuilt index. | Python 3.10+ (stdlib) | Set `LLM_WIKI_PATH`; optionally configure the bounded SessionStart hook using the [maintenance guide](plugins/llm-wiki-memory/skills/llm-wiki-memory/references/maintenance.md). |
| `managing-pc-disk` | Inspect macOS disk usage and reclaim space from old logs, Docker and Colima, and developer caches with approval. | macOS, Bash, Python 3 | Run `/managing-pc-disk:managing-pc-disk`. Docker and Colima are needed for their respective cleanup steps. |

Memory 0.4 searches summaries by default (8 results / 8192 UTF-8 bytes). Use `recall.py --read PATH` for full notes within the same byte budget. SessionStart context is capped at 4096 bytes. Use `save.py --check` to preview the canonical target and related notes, and use `usage.py --report` to review reads, exposures, and retirement candidates. Consolidation supports merge, drop, compression, and archive. Active notes require a review decision. Archived originals may be purged after 60 days without a read. The newest 20 committed backups remain recoverable. See the [consolidation workflow](plugins/llm-wiki-memory/skills/llm-wiki-memory/references/consolidation.md).

Run memory integration tests with `python3 -m unittest discover -s plugins/llm-wiki-memory/tests -v`.

## Licensing

- Repository license: **Apache-2.0** (see `LICENSE`) — covers the plugins. `deep-code-review` bundles assets ported from OpenCodeReview (Apache-2.0); see its `references/NOTICE`.

## Secrets policy

🔒 Never commit tokens, API keys, credential files, or personal absolute paths. Reference machine-specific locations only through environment variables (e.g. `$LLM_WIKI_PATH`) or placeholders (e.g. `<your-vault-path>`).
