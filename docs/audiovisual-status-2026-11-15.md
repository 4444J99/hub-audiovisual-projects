# Audiovisual estate status — 2026-11-15

A dated sibling of [the 2026-11-14 status map](audiovisual-status-2026-11-14.md), which is kept unchanged. It records what merged on the public audiovisual repositories after that page was written, the repository heads on 2026-11-15, the permanent silence rule for browser checks, and what has still never run. It is a snapshot, not a certification. Public facts only: every example named below is synthetic, no film material, transcripts or private repository contents are described, and the restricted implementations in the [project catalog](project-catalog.md) are out of scope. "Merged" means the pull request is merged on that repository's `main` (checked with `gh pr view`); "passes" means the stated command exited 0 on a stated date on one workstation.

## Heads on 2026-11-15

| Repository | `main` head | Hosted result on that head |
|---|---|---|
| [hub-audiovisual-projects](https://github.com/4444J99/hub-audiovisual-projects) | `59c3cc5` (#38) | Verify composition system: success |
| [tool-audiovisual-postproduction](https://github.com/4444J99/tool-audiovisual-postproduction) | `712ecc2` (#175) | Verify production system: no conclusion yet when read (still running). The previous head `b031eef` (#174) is success |
| [tool-video-loop-compositor](https://github.com/4444J99/tool-video-loop-compositor) | `f4abaa9` (#119) | Only Current State Projection runs appear on `main` (success and skipped); the verification workflows run on branches, as on 2026-11-14 |
| [timed-text-navigation-loop](https://github.com/4444J99/timed-text-navigation-loop) | `88b6a79` (#77) | Verify historical edition and Publish historical edition: success |

The 2026-11-14 page lists postproduction at `fa59f2d` (#158) and the compositor at `5cef46f` (#109); both moved. This page does not re-run the local gates; the 2026-11-14 local results stand as a record of that day only.

## Postproduction: delivery, captions, burn-in, QC (#168 to #170, #175)

The hash-chained synthetic pipeline (#147, from set spec to colour plan) gained four stages. Every stage is verified by re-derivation from the sealed artefacts, not by trusting recorded numbers, and every fixture is synthetic.

- **#168 loudness delivery stage.** Between room-tone fill and the final ledger: measure the filled dialogue (BS.1770-4), apply one linear gain to a declared delivery spec (EBU R128 by default, other presets or a spec file by option), write the file, read it back and measure it, and hash input and output. A spec the audio cannot meet is refused, not sealed (the streaming preset would need +12.6 dB and push true peak to -0.7 dBTP). It builds on the meter, delivery check and gain planner of #162.
- **#169 caption timing.** Word cues in seconds become SRT and WebVTT on an exact frame grid (24, 25, 24000/1001; rounded decimals refused), with sentence, pause and clause splitting, balanced one- or two-line breaks, minimum gap, minimum duration and maximum characters per second. What the words leave no room to meet is reported (exit 2), never hidden. The writer parses its own files back and requires them to equal the cues; `check` judges any SRT or VTT.
- **#170 burn-in.** Cues drawn onto synthetic 8-bit luma frames with an embedded 5x7 bitmap font and integer arithmetic (the installed ffmpeg has no `subtitles` or `drawtext` filter, so there is no ffmpeg burn path). Frames are hash-chained into the pipeline manifest, and `verify` re-renders every frame from the caption file and parameters and names the first differing byte. Unrenderable input (no glyph, a cue past the last frame, overlapping cues, text wider than the frame) is refused rather than drawn as a box.
- **#175 delivery QC.** A final `qc` stage reads only the sealed artefacts and writes a deterministic report of 15 named checks, re-derived byte for byte on `verify`: captions against measured dialogue spans, reading rate, cues inside the edit and burned frames against a caption-less render; one exact timebase across plan, ledger, colour plan, captions and burn-in; and the delivered file re-measured against the recorded spec. `run` refuses to seal a failing chain. The PR discloses that on a clean chain caption placement and the dialogue check share a detector at its default, so the clean pass is close to tautological; independence shows only under tamper.

Review state, as written in the pull request bodies: Codex returned a usage-limit failure on #175, so none of the bots reviewed it, and no review threads exist on it. Its local suite showed two failing installed-wheel packaging tests, stated to be identical on a clean `main` checkout. The post-merge hosted run for #175 had not concluded when this page was written (see the table above).

Also merged since the 2026-11-14 page: #149 (refuse reserved WebSocket opcodes in the FX bridge), #154 (fail once with the remedy when `node_modules` is missing), #155 to #165 (TouchDesigner network: latency and Reverse/Stutter, set-spec v1.1 shapes, Routing, Exchange, Queue/Overflow, Typography and Granular picture chains each checked against the workbench's own draw calls, and the Routing voice against its audio engine), #159 (branch and push rules), #162 (loudness), #166 (record that the TouchDesigner work has not run in-app) and #167 (close review debt from earlier PRs).

## Speech-score engine

The speech-score engine repository is private, so this public page records only that it exists and had work merged on 2026-11-15; its contents and pull requests are described in its own repository.

## Loop compositor: the retry helper (#114, #116, #118, #119)

The 2026-11-14 page recorded one render child killed by signal 15 under a full local run. [Issue 113](https://github.com/4444J99/tool-video-loop-compositor/issues/113) diagnosed it as a SIGTERM sent from outside the repository (nothing in `src`, `tools` or `tests` sends one), and the fix is a retry helper with the migration completed in four slices:

- **#114** adds `simvltanea/subprocess_retry.run`. A child that dies of SIGTERM is run once more; any other exit, including other signals and ordinary failures, is returned unchanged and never retried; a child signalled on every attempt fails with a message naming SIGTERM as coming from outside. Eight regression tests, one of which reproduces the bare `-15`.
- **#116** routes the browser tests' node and ffmpeg children through it and adds a lint for new bare children. **#118** does the render, lab and proxy children and makes the lint resolve chained names and `args=`. **#119** converts the remaining `tools/` test children, and the lint allowlist is now empty. The notes record the SIGTERM sender as unconfirmed.

Also merged: #112 (harden two flaky browser tests), #117 (re-attempt a deferred loop-mode handoff, bounded) and #109 (judge held-source native gaps on the recent signal). Open on 2026-11-15: #110 (name the authored range in the compiler refusal) and #121 (silence rule, below). Correction to the 2026-11-14 page, which listed #106 (versioned seeded roll) as open: #106 is merged. Issue 113 is closed.

## hole-loop: rendition export and its verifier (#72, #75)

#72 added a deterministic audiovisual rendition export for the Six Encounters work: a seeded run is driven through the real `RouteSession` and written as an H.264/AAC file, a cue-track WAV and a receipt carrying SHA-256 of the raw frame stream and the cue track, with an ffprobe readback. It is a schematic rendition of the route words, not a capture of the browser artwork, and claims no acceptance. It closes [issue 71](https://github.com/4444J99/timed-text-navigation-loop/issues/71), where the C3 `audiovisualTrackExported` flag had defaulted to true with no code behind it.

#75 adds `verify-rendition.cjs`, an independent replay verifier: it re-derives the timeline, frame-stream hash, cue list and WAV bytes from the receipt's seed, probes the MP4, decodes every frame and compares luma PSNR against the replay (the PR records 36.7 dB worst case for the exact seed and 5.5 dB for another seed, against a floor of 30), and decodes the AAC to check tones inside cue windows and silence outside. Nine new tests include tamper cases. It checks the mechanics only.

## Silence rule and mute configuration

No check in these repositories may produce audible sound on the host. Chromium runs get `--mute-audio`; WebKit has no such flag, so a page init script pins media elements to `muted = true` and `volume = 0` and routes realtime audio contexts through a gain-0 sink, with the contract proven on silent fixtures and a lint that fails on any launch bypassing the helper. The mechanism is documented in [silent-browsers.md](silent-browsers.md) and has landed in three repositories as a pair of pull requests (silent launch helper, init script and lint; then nested shadow roots and the `MediaElementAudioSourceNode` constructor):

| Repository | Pull requests | State |
|---|---|---|
| hub-audiovisual-projects | #36, #38 | merged |
| tool-audiovisual-postproduction | #172, #174 | merged |
| timed-text-navigation-loop | #74, #77 | merged |
| tool-video-loop-compositor | #121 | open, not merged |

The compositor's browser tests, which are the largest audio-capable surface, therefore do not yet carry the permanent silence helper on `main`.

## Still never run

None of the TouchDesigner work (network generator, OSC bridge, rack module, and the refinements listed above) has run in the real TouchDesigner application. It is verified structurally and numerically only: spec validation, a fake operator tree, a CPython module run, and parameter-name checks against the application's reference. The first in-app check for the owner is the "First in-app check for the owner" section of `docs/FX-TOUCHDESIGNER.md` in tool-audiovisual-postproduction; the hub's own record is its PR #31. The application is installed on the workstation but was not launched for this page. Headless Blender covers only the set builder.

## Boundaries

This page asserts no artistic, device, delivery or custody acceptance for any work and describes no restricted repository. Each repository's own documents remain the owner of its claims.
