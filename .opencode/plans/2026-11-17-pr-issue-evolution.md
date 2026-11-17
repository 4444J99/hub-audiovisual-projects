# PR / Issue Evolution Report — `audiovisual-composition-system`

**Date:** 2026-11-17  
**Stream:** B (PR / Issue Evolution) of the Autonomous Ecosystem Retirement & Enrichment plan  
**Method:** full remote inventory via `gh` (all states), heuristic supersession detection, local git/oss evidence. Machine-readable evidence: `.opencode/plans/stream-b/2026-11-17-pr-issue-data.json`  
**Staging run:** `09_Engineering/custody-staging/run-20261117-104235-session-retirement/`

> Supersession links below are **evidence-backed candidates**, not licensed merges. No remote PR was closed and no history was rewritten by this pass. Destructive actions are listed as ready-to-run commands for the owner or the orchestration stream.

## 1. Repository state

| Field | Value |
|---|---|
| Local path | `/Volumes/Archive4T/Projects/audiovisual-composition-system` |
| GitHub remote | `4444J99/hub-audiovisual-projects` |
| Upstream archived | no |
| Default branch (remote) | main |
| Local branch | `main` |
| Dirty files | 0 |
| Linked worktrees | 1 (canonical checkout) |
| Last commit | 2026-11-17T10:40:22 — fix(silent-browser): add Firefox media.volume_scale pref (#42) (#47) |
| Plan surfaces | none |

### Rename / ownership evolution

- Current canonical remote: `4444J99/hub-audiovisual-projects` — remote renamed `audiovisual-composition-system` → `hub-audiovisual-projects`; contains nested repos `the-thing-without-a-name`, `god-here`.
- Old `owner/repo#N` references still resolve through GitHub's redirect, but new cross-references should use the current slug so the link survives a future transfer.

## 2. PR inventory

| Metric | Count |
|---|---|
| PRs (all states) | 41 |
| Merged | 36 |
| Open | 0 |
| Closed unmerged | 5 |

Closed-unmerged classification:

| Class | Count |
|---|---|
| closed without successor | 5 |

## 3. Evolution decisions (old → new)

_No supersession links detected: no closed-unmerged PR in this repo has a traced successor._

## 4. Items marked archived

- **36 merged PRs** — resolved, no action; history is the archive.
- **5 PRs closed without a traced successor** — archived as abandoned. Titles are retained in the evidence file in case a later re-cut needs the original scope.

## 5. Open PR triage

_No open PRs._
## 6. Issues

| Metric | Count |
|---|---|
| Issues (all states) | 6 |
| Open | 2 |
| Open and idle > 45 days | 0 |

## 7. Follow-up flags

- Remote renamed to `hub-audiovisual-projects`. Local checkout also hosts nested repos (`the-thing-without-a-name`, `god-here`) that are separate remotes.
- Old PR references keyed on `audiovisual-composition-system#N` will still resolve through the GitHub rename redirect, but new cross-refs should use the new slug.

## 8. Provenance and limits

- PR/issue inventory: `gh pr list`/`gh issue list --state all` for `4444J99/hub-audiovisual-projects`, captured 2026-11-17.
- Supersession classes: explicit `supersedes #N` in title; dependency retry (same package + directory, newer bump merged); rewrite series (identical title stem, later PR merged); producer retirement (Limen/Jules branch, no successor); otherwise abandoned.
- Heuristic limit: a title-stem match can link two genuinely different changes. Treat §3 as a review queue, not as settled provenance.
- No remote mutation was performed: no PR closed, no issue closed, no branch deleted.
