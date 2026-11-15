# Status pages are generated, not hand-written

The files in [`docs/status/`](status/) are generated, not hand-written. Hand-written status pages went stale and carried errors that a verifier found three times (the 2026-11-14 map, the 2026-11-15 page and its corrections page). The numbers on a status page (heads, merge commits, run ids, conclusions, step counts, issue states) come from live GitHub state; a person or agent writes none of them.

`tools/status_snapshot.py` (Python standard library and the `gh` CLI only) does two separate things:

1. **Collect** a snapshot of each tracked repository: the default-branch head and the pull request that produced it; pull requests merged since a date, each with its merge commit; open pull requests; the latest default-branch run of each workflow with its executed-step count; open issue counts and issues updated since the date; and the checks that were red, unable to start, cancelled or still pending on each merged pull request's final head at the moment it merged.
2. **Render** the page from the snapshot alone. A fixed snapshot always renders to byte-identical output.

## Commands

```sh
# live: collect, keep the snapshot, render the page
python3 tools/status_snapshot.py --since 2026-11-13 --date 2026-11-15 \
    --snapshot-out docs/status/2026-11-15.snapshot.json --out docs/status/2026-11-15.md

# offline: re-render a stored snapshot (no network)
python3 tools/status_snapshot.py --from-snapshot docs/status/2026-11-15.snapshot.json --out docs/status/2026-11-15.md

# fail with exit 1 if a page differs from its snapshot's rendering (a hand edit)
python3 tools/status_snapshot.py --from-snapshot docs/status/2026-11-15.snapshot.json --out docs/status/2026-11-15.md --check
```

Exit codes: 0 success, 1 `--check` drift, 2 refusal. The unit tests also fail when any committed page differs from its snapshot, so a hand edit cannot merge.

To correct a page, fix the tool or take a new dated snapshot; never edit the generated file. A page is a record of one moment (`captured_at`), so a later change produces a new dated page, not an edit of the old one.

## What the tool refuses

- **Unresolved citations.** The collector resolves every merge commit against the repository and checks it is an ancestor of the default branch; the renderer refuses any snapshot whose pull request, head or merge commit is not marked resolved, is not hexadecimal, or cites a pull request absent from the merged list.
- **Zero-step runs read as passes.** A run or check whose jobs executed zero steps is `cannot-start` (or `no-steps` / `skipped` when its recorded conclusion was success or skipped), never `pass`. The renderer recomputes each verdict from the recorded steps and refuses a snapshot that contradicts it. A step counts as executed when it completed with a conclusion other than `skipped`.
- **Truncated lists.** A list that reaches its fetch limit stops the run instead of silently dropping entries.
- **Public-surface leaks.** A repository is listed in full only when the manifest marks it public (`"private": false`) and GitHub reports it public. A restricted repository is listed by name only when its manifest record carries `"status_listing": "name-only"`; otherwise it is omitted and only a count appears. Commit identifiers are stored as 12-character prefixes (the public-surface validator reads 40-character pins as source bindings) and shown as 7. Titles are escaped for tables, restricted repository names in titles are replaced, and the finished page is checked with `identity_contract.surface_facts`.

## Red-at-merge section

For every merged pull request the final head's check runs are read. A check is reported when, at the pull request's merge time, it had concluded `failure`, `timed_out`, `action_required` or `startup_failure` with executed steps (`red`), concluded the same with zero executed steps (`cannot-start`, startup noise that is recorded with its run id but is not a failing test), had been cancelled, or had not finished (`pending`). Checks from external apps expose no steps and show `not observable`. The section states plainly when there are none.

## Limits

A snapshot says what GitHub reported when it was taken. It does not include local gate results, review-thread dispositions, or anything about restricted repositories, and it claims no acceptance of any work.
