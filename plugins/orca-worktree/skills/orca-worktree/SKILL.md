---
name: orca-worktree
description: Creates isolated Orca worktrees from a freshly fetched remote branch. Use when the user asks to create an isolated Git worktree or says "격리 워크트리 만들어줘", "격리워크트리 만들어줘", or "Orca에 워크트리 만들어줘".
---

Run the bundled [wt-create](scripts/wt-create) using its path relative to this skill:

```bash
bash <skill-directory>/scripts/wt-create <registered-repo-path> <new-branch> [remote-base-branch]
```

Use the requested repository, or the current repository if the request names none. When inside a linked worktree, pass the registered original repository path.
The new branch name and the remote base are independent. Omit the remote base to use `origin/master`. For an explicit base such as `origin/release/a`, pass `release/a`.
Use the Orca CLI workflow for stacked worktrees, remote hosts, or agent handoffs.
Report the created path, branch, and base commit from the command output. If it fails, report the error and check Orca for a created worktree before retrying.

The script requires Bash, Git with `fetch --porcelain`, the Orca CLI, and `jq` for the Orca response. It initializes each pinned submodule, including nested modules. It borrows objects from the corresponding original module when available and fetches only the pinned snapshot at depth 1 when the pin is missing. Keep the original module's borrowed objects available for the lifetime of the worktree. Each worktree still needs space for the checked-out files.

Keep repo-defined setup hooks compatible with this flow. A hook that initializes submodules itself can fetch history before the script starts sharing objects. If initialization fails, the script exits nonzero, reports the retained worktree and failing pin, and leaves the created checkout available for inspection.

To verify all pins even when the original repository has no submodule registration, run `git -c submodule.active=. submodule status --recursive` inside the new worktree. The script keeps the original repository's submodule configuration intact.
