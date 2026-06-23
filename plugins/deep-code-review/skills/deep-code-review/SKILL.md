---
name: deep-code-review
description: >
  Deep, whole-repository code audit using language-specific rule sets (ported from
  OpenCodeReview). Reviews every reviewable file under the current working directory
  (or a given path) file-by-file, in depth — NOT just the git diff. Use when the user
  asks for a full/thorough/deep code review, a repo audit, or a quality pass over a
  whole codebase or directory, as opposed to reviewing recent changes. Runs entirely
  in the host session (no API key). Distinct from diff/branch review.
license: Apache-2.0
---

# deep-code-review

Whole-repo deep code review. Complementary to diff-based review (which reviews
CHANGES): this audits the WHOLE codebase (or a path) file-by-file against
language-specific rules. Read-only — it never edits code.

This skill's base directory is shown as "Base directory for this skill" when it
loads; call it `$SKILL_DIR` below.

## When to use
- "deep/thorough code review", "audit this repo", "review the whole codebase / this directory".
- NOT for a diff/PR/branch — use a diff reviewer for changes.

## Input
`/deep-code-review [path]`
- **No path → review the current working directory (cwd).** Primary pattern: the user
  opens Claude Code at the git repo root and invokes with no argument → whole repo.
- A path scopes the review to that subtree.

## Procedure

1. **Select files (deterministic).**
   ```bash
   python3 "$SKILL_DIR/scripts/select_files.py" [path]
   ```
   Prints JSON `{total, by_rule, files:[{file, rule_doc}]}` (repo-root-relative paths).
   - Exit code 2 → tell the user "Not inside a git repository." Stop.
   - `total == 0` → "No reviewable files found." Stop.

2. **Size gate.** Report `total` and the languages in `by_rule`.
   - If `total > 40`: warn that this dispatches ~`total` review subagents (token cost),
     list the largest directories, and ask whether to proceed or narrow the path. Wait
     for the user.
   - Otherwise proceed.

3. **Review — fan out in waves of 8.** For each file dispatch one general-purpose
   subagent. Build its prompt from `$SKILL_DIR/references/reviewer-prompt.md`,
   substituting `{{FILE}}` and `{{RULE_DOC_CONTENT}}` (the contents of
   `$SKILL_DIR/references/rule_docs/<rule_doc>.md` for that file), and append
   `$SKILL_DIR/references/TOOL_MAPPING.md`. Dispatch at most 8 concurrently; finish a
   wave before starting the next. Each subagent returns a JSON array of findings.
   A subagent that fails or returns invalid JSON → record "review incomplete: <file>"
   and continue. If the response contains prose before or after the array, extract the
   JSON by taking the substring from the first `[` to the last `]`; if no valid array
   can be extracted, treat it as invalid JSON.

4. **Filter false positives.** Concatenate all findings into one JSON array (index =
   position). Fill `$SKILL_DIR/references/review-filter-prompt.md`'s `{{FINDINGS_JSON}}`
   and run it as one general-purpose subagent. Remove the `drop` indices it returns.
   If the response contains prose, extract the JSON object from the first `{` to the
   last `}`; if it cannot be parsed, drop nothing and proceed with all findings.

5. **Report.** Present Markdown:
   - Header: files reviewed, files incomplete, counts by severity.
   - Findings grouped Critical → Important → Minor, each `path:line — category — finding`
     then the suggestion.
   - One-line overall assessment.
   Offer to write the report to a file or render HTML if the user asks.

## Notes
- Read-only. Acting on findings is the user's call (optionally pair with a fix workflow
  or a diff reviewer).
- Auth: runs in the host session — no API key, no provider config.
- Rules are data under `references/`; changing review behavior is a config edit.
