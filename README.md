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
| `llm-wiki-memory` | Routes auto-memory save/recall to your own Obsidian vault so every machine shares notes. | `python3` (stdlib) | `export LLM_WIKI_PATH=<your-vault-path>` before use. If unset, the skill stops and tells you. |

## Licensing

- Repository license: **Apache-2.0** (see `LICENSE`). `deep-code-review` bundles assets ported from OpenCodeReview (Apache-2.0); see its `references/NOTICE`.
- `llm-wiki-memory` is **MIT** (declared in its `plugin.json`).

## Secrets policy

🔒 Never commit tokens, API keys, credential files, or personal absolute paths. Reference machine-specific locations only through environment variables (e.g. `$LLM_WIKI_PATH`) or placeholders (e.g. `<your-vault-path>`).
