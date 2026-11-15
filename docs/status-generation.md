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

- **Unresolved citations.** The collector resolves every merge commit against the repository and checks it is an ancestor of the default branch; the renderer refuses any snapshot whose pull request, head or merge commit is not marked resolved or is not hexadecimal, and any red-at-merge fact that does not match the merged pull request it cites (number, head and merge time).
- **Zero-step runs read as passes.** A run or check whose jobs executed zero steps is `cannot-start` (or `no-steps` / `skipped` when its recorded conclusion was success or skipped), never `pass`. The renderer recomputes each verdict from the recorded steps and refuses a snapshot that contradicts it. A step counts as executed when it is one of the workflow's own steps and completed with a conclusion other than `skipped`; GitHub's bookkeeping steps (`Set up job`, `Complete job`, `Post ...`) do not count, so a job whose real steps were all skipped, or that died during setup, has zero.
- **Truncated lists.** A pull request or issue list that reaches its fetch limit stops the run instead of silently dropping entries; job and check-run lists are read across all pages and the run stops if the count read differs from the count GitHub reports. Hosted CI looks at the newest 100 default-branch runs, latest per workflow id. Workflows whose latest run is on an older head are named under the table with their last verdict, so a red one stays visible; a workflow idle for longer than the 100-run window is not listed. The snapshot records when collection started and finished, because the reads are sequential and a head can move in between; heads, runs and checks are each read at one moment inside that interval.
- **Public-surface leaks.** A repository is listed in full only when the manifest marks it public (`"private": false`) and GitHub reports it public. A restricted repository is listed by name only when its manifest record carries `"status_listing": "name-only"` (the only accepted value; `identity_contract` ignores the field in the frozen private baseline and the exemption applies to files under `docs/status/` only and covers only the bare repository name (its key, local path and origin aliases stay restricted); the mark is accepted on restricted repositories only, so no other document may name it, and a page there is exempt only if it begins with the generator's marker line (its `.snapshot.json` beside it shares the exemption); every page must also have a snapshot that renders to it, which a unit test enforces); otherwise it is omitted and only a count appears. Restricted names are replaced in titles, workflow names and check names at collection time, so a stored snapshot never contains them. Commit identifiers are stored as 12-character prefixes (the public-surface validator reads 40-character pins as source bindings) and shown as 7. Free text is escaped for markdown, and the finished page is checked with `identity_contract.surface_facts` against the current manifest (an old page that now names a newly restricted repository is refused, by design).

## Red-at-merge section

For every merged pull request the final head's check runs are read. A check is reported when, at the pull request's merge time, it had concluded `failure`, `timed_out`, `action_required` or `startup_failure` with executed steps (`red`), concluded the same with zero executed steps (`cannot-start`, startup noise that is recorded with its run id but is not a failing test), had been cancelled, or whose latest attempt had not finished at merge time (`late` or `pending`). `late` marks a latest attempt that finished after the merge time (a slow check or a later re-run), `pending` one still unfinished when the snapshot was read. A step count of `not observed` means the steps were not read (an external check that exposes none, or a check that had not finished or had not failed). The section states plainly when there are none.

## Limits

GitHub keeps only the latest attempt of a check: a check re-run after a merge is read as that attempt, so `pending` means the latest attempt had not finished at the merge time, not that no earlier attempt failed. Marking a private repository `name-only` is a publication decision: review that manifest edit as one (it is ignored by the frozen private-relationship hash on purpose, so the mark is the review). If a later manifest change restricts a name already published in a dated page, the page is refused by the renderer and the unit tests; withdraw it (`git rm` of the page and snapshot) through review rather than editing it. A snapshot says what GitHub reported when it was taken. It does not include local gate results, review-thread dispositions, or anything about restricted repositories, and it claims no acceptance of any work.
