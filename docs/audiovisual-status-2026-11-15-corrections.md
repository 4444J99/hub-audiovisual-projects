# Audiovisual estate status — 2026-11-15 corrections

A dated sibling of [the 2026-11-15 status page](audiovisual-status-2026-11-15.md), which is kept unchanged as the record of what it said when it merged. A verifier read that page against live repository state and found the errors below. This page supersedes the 2026-11-15 page wherever the two disagree. Public facts only: no film material, transcripts or private repository contents are described. Every pull request number, head and run id below was read with `gh` on 2026-11-15 at write time; "merged" means merged on that repository's `main`.

## 1. Red hosted checks that the 2026-11-15 page omitted

The 2026-11-15 page describes the compositor pull requests #109, #114, #118, #119 and #121 without saying that each carried a red hosted check on its head when it merged (or, for #121, when it was last recorded). They did. The table is the plain record.

| Pull request | Head | State | Failing hosted check | Run id | Failing step |
|---|---|---|---|---|---|
| [#109](https://github.com/4444J99/tool-video-loop-compositor/pull/109) | `352df47` | merged | `test` | 43664919393 | Run Full Test Suite |
| [#114](https://github.com/4444J99/tool-video-loop-compositor/pull/114) | `29b26dd` | merged | `test` | 43683392376 | Run Full Test Suite |
| [#118](https://github.com/4444J99/tool-video-loop-compositor/pull/118) | `ecc5ac9` | merged | `sustained-playback` | 43703043724 | Prove sustained playback and native audio |
| [#119](https://github.com/4444J99/tool-video-loop-compositor/pull/119) | `0e0429b` | merged | `sustained-playback` | 43715818127 | Prove sustained playback and native audio |
| [#121](https://github.com/4444J99/tool-video-loop-compositor/pull/121) | `9411d7c` | merged | `sustained-playback` | 43722666733 | Prove sustained playback and native audio |

Each of those runs executed its steps, so none is startup noise. The other checks on the same heads (`wheel-smoke`, Cloudflare Pages, semgrep, and `test` on #118, #119 and #121) passed. The merged state of these pull requests therefore does not mean their hosted checks were green, and the 2026-11-15 page's account of them (retry helper, silence helper) rests on local gates plus the reviews it names, not on a green hosted run. #110 (still open) shows the same `sustained-playback` failure, run 43642249004; #112, #116 and #117 show no red check.

The gate is being root-caused under [issue 115](https://github.com/4444J99/tool-video-loop-compositor/issues/115), which is open. Its comments distinguish at least two classes: a cancelled blob request classified as an unexpected resource error (the `noErrors` class, related to issue 89), and a deferred loop-mode handoff (the part #117 changed). The issue states that the `noErrors` symptom and the seek-cohort arms stay red on `sustained-playback` and lists runs 43722666733, 43710893824 and 43702981423. No cause is claimed here beyond what the issue records, and no fix has landed for the `noErrors` class.

## 2. Corrections to the heads table and states

Read on 2026-11-15 at write time. The 2026-11-15 table is stale; this one replaces it.

| Repository | `main` head | Hosted result on that head |
|---|---|---|
| hub-audiovisual-projects | `d6ac9c7` (#39) | Verify composition system: success, run 43726014942 |
| tool-audiovisual-postproduction | `53bab60` (#176) | Verify production system: in progress, run 43730925214; combined checks and Python package in progress |
| tool-video-loop-compositor | `97070de` (#121) | `sustained-playback` success, `wheel-smoke` and Cloudflare Pages success, `test` in progress; Current State Projection runs are mostly skipped (one success, run 43728644795) |
| timed-text-navigation-loop | `292984a` (#88) | Verify historical edition success (run 43728892350) and Publish historical edition success (run 43728983970) |

Specific corrections:

- **Postproduction `712ecc2` (#175).** The 2026-11-15 page said its `main` run had no conclusion yet. That run, 43725424891 (Verify production system), is success. `main` has since moved to `53bab60` (#176).
- **Compositor #121.** The 2026-11-15 page and its silence-rule table called it open. It merged on 2026-11-15 at 14:52 UTC (merge commit `97070de`). The compositor's browser tests therefore now carry the silent launch helper on `main`, and the sentence saying they did not is withdrawn. Its head was red on `sustained-playback` when it merged: run 43722666733 (attempt 1, never re-run) concluded failure at 14:29 UTC, 23 minutes before the 14:52 UTC merge (section 1). #110 remains open.
- **Compositor head.** `f4abaa9` (#119) is no longer the head; `97070de` is.
- **Loop-text repository.** `88b6a79` (#77) is no longer the head; `292984a` (#88, string-aware comment stripping in the silent launch lint, fail-closed) is.
- **Hub.** `59c3cc5` (#38) is no longer the head; `d6ac9c7` (#39, the 2026-11-15 page itself) is.

The 2026-11-15 page's silence-rule table is otherwise unchanged: hub #36 and #38, postproduction #172 and #174, timed-text-navigation-loop #74 and #77 are merged. Postproduction [issue 186](https://github.com/4444J99/tool-audiovisual-postproduction/issues/186) is open and records a residual: the silent init script cannot reach media inside a closed declarative shadow root under WebKit.

## 3. Where the TouchDesigner guide lives

The 2026-11-15 page pointed at `docs/FX-TOUCHDESIGNER.md` as if it were in this hub. It is not here. The file is `docs/FX-TOUCHDESIGNER.md` in [tool-audiovisual-postproduction](https://github.com/4444J99/tool-audiovisual-postproduction/blob/main/docs/FX-TOUCHDESIGNER.md) (confirmed present on that repository's `main` and absent from this one). Its "First in-app check for the owner" section is the first in-app step, and nothing about TouchDesigner having never run in the real application has changed.

## 4. Additions

- **Postproduction [#176](https://github.com/4444J99/tool-audiovisual-postproduction/pull/176) (merged, `main` merge commit `53bab60`, head `843701e`).** A one-command synthetic short-film demo: it runs the sealed synthetic chain (set spec through delivery QC), verifies it, and muxes the burned frames and delivered dialogue into a small mp4, with a hash file and a QC report. Its pull request states that outputs are byte-identical across two runs. A later verification found that the chain and QC hashes are not reproducible, so that claim must not be relied on; the defect is reported as found and is being fixed, and this page records no fixed state. It was merged with Codex returning a usage-limit failure and Sourcery returning a rate-limit notice on its head, so neither bot reviewed it. All inputs are synthetic.
- **Speech-score repository, pull request #37.** A private repository's pull request 37 merged on 2026-11-15. This public page says only that it exists; nothing about its subject or contents is described here.

## 5. Boundaries

This page asserts no artistic, device, delivery or custody acceptance, describes no restricted repository, and does not re-run the local gates of the pages it corrects. The 2026-11-14 and 2026-11-15 pages are not rewritten.
