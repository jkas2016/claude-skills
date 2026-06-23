# Tool name mapping — OpenCodeReview rule docs → Claude Code

The ported rule docs (references/rule_docs/) were written for the `ocr` agent and
name its tools. Translate while following them:

| Rule doc says     | Use in Claude Code |
|-------------------|--------------------|
| `code_search`     | Grep (ripgrep)     |
| `file_read`       | Read               |
| `file_find`       | Glob               |
| `file_read_diff`  | N/A — this is whole-file review, not diff-based; ignore |

The rules describe WHAT to look for; HOW is Claude Code's tools.
