# Audiovisual estate status — 2026-11-14

An evidence-bound map of the public audiovisual repositories: what is on `main`, what ran locally on 2026-11-14, what each repository's own documents say is next, and what is open. It is a snapshot, not a certification. Public facts only: no film material, transcripts or private repository contents are described, and the two restricted implementations in the [project catalog](project-catalog.md) are out of scope. "Passes" means the stated command exited 0 on this date on one workstation; it is not an acceptance claim for any artwork, listening result or device.

## How this was gathered

Each public repository was cloned fresh at its `main` head, its documented gate was run bare, and its exit status and test counts were read from the command's own output. Hosted results come from `gh run list`. Where a command did not finish or could not start, the table says so.

## Map

| Repository | Role | `main` head | Hosted result | Local gate, 2026-11-14 |
|---|---|---|---|---|
| [hub-audiovisual-projects](https://github.com/4444J99/hub-audiovisual-projects) | Membership, names, relationships and migration contract for 15 projects | `a62aed8` (#29) | Verify composition system: success on `main` (2026-11-13) | `workspace_layout.py check --catalog-only` PASS (15 projects, 6 repository references, 54 generated files); `unittest discover -s tools/tests` 78 tests OK; `node --test tools/tests/test_verify_tmb_composition.cjs` 14 pass, 0 fail |
| [tool-audiovisual-postproduction](https://github.com/4444J99/tool-audiovisual-postproduction) | Directable postproduction (`amp`): audio, colour and layers, shot planning, FX workbench, TouchDesigner network, Blender set builder | `fa59f2d` (#158) | Verify production system: success on `main` (2026-11-15 UTC) | `python -m unittest discover -s tests`: 679 tests, 4 failures; `-s tests/studies`: 391 tests, 1 error. All 5 are environmental: four `test_packaging` installed-wheel tests (the throwaway wheel environment has no `scipy`, and the FX pack needs `@napi-rs/canvas`) and the `test_reference_review` class setup (`@napi-rs/canvas` not installed; the repository's own #154 makes that fail once with the remedy). The Node suites were not run. CI installs those dependencies and passes. Not green on this workstation as configured |
| [tool-video-loop-compositor](https://github.com/4444J99/tool-video-loop-compositor) | N independently clocked loops, Studio, native Mac app | `5cef46f` (#109) | `main` shows only Current State Projection runs (skipped, one success); CI Verification, Package Verification and macOS WebKit playback run on branches | `PYTHONPATH=src python3 -m unittest discover -s tests`: 1846 tests, 2 failures, 34 errors, 44 skipped in 355 s. All 34 errors are `ModuleNotFoundError: playwright` and one failure is `No module named pytest`: both are declared in the `verification` extra and were not installed here. The other failure, `test_style_maxima_never_expose_background` (12 loops, 640x360), was a render subprocess killed by signal 15; not reproduced or diagnosed. Not green on this workstation |
| [timed-text-navigation-loop](https://github.com/4444J99/timed-text-navigation-loop) | hole-loop browser edition | `2f6f420` (#70) | Verify and Publish historical edition: success (2026-11-06) | `python3 scripts/verify.py` exit 0 (source, markup, timers, dependency closure, route graph; 0 runtime external dependencies). Browser execution (`npm run test:browser`, needs Playwright) was not run |

The hub's `main` had a failed hosted run on 2026-11-06 and a green one on 2026-11-13.

## What exists on `main`

**Hub.** One authored manifest (`workspace-manifest.json`, schema 2.1.0) drives the generated project catalog, directory views and the editor workspace. Validators cover manifest consistency, preservation rules, repository visibility (`verify_repository_access.py`), source-led continuation records, offline TouchDesigner session inspection (`inspect_touchdesigner_session.py`) and a TMB spatial composition acceptance guard. #29 homed the TouchDesigner session verification and release packet.

**Postproduction.** Merged since 2026-11-13: #133 touch and MIDI control surface, #135 OSC bridge to TouchDesigner, #136 reverse-angle planning with an observed-pixel ledger, #137 layout geometry, #138 synthetic asset pack and TouchDesigner simulator, #139 shot plan validator, edit ledger and animatic, #140 colour grade chains and layered compositing validator, #141 TouchDesigner network generator, #142 and #156 set-spec validator and headless Blender scene builder (v1.1 adds axis cylinders, cone, sphere, torus and stairs), #143 room-tone extraction and gap fill, #144, #148, #150, #155, #157 and #158 TouchDesigner network refinements (resolved parameters, rule mirroring, Freeze/Hold, latency, Reverse and Stutter, routing checked against the workbench's draw calls), #145 actor-coverage matrix, #147 hash-chained synthetic pipeline from set spec to colour plan. Its README states the generated TouchDesigner network is "Not yet built in a real TouchDesigner."

**Loop compositor.** Studio, composition workspace, evolving playback, a native Mac app over the user's Photos videos with per-clip sound (#101), hand-authored mosaics for 8 to 12 loops (#104), native-seam proof from frame callbacks (#100), and a gate that judges held-source native gaps on the recent signal (#109). Open pull requests: #106 (versioned seeded roll) and #110 (name the authored range in the JS compiler refusal).

**hole-loop.** The 2017 LOOPHOLE static site with a source-integrity verifier, a browser verifier, and the Six Encounters C0 to C6 validators (Waves 3 to 8). Its [roadmap](https://github.com/4444J99/timed-text-navigation-loop/blob/main/docs/ROADMAP.md) points at the C0 to C6 issue track (issue 2).

## What the repositories say is next

- **Postproduction:** open issue 151 (TouchDesigner stateful and sample-rate effects); the GHERE-AI program issues 63 to 69 and 113 (qualification harness, model admission, bounded live performance); the README's own limit that the TouchDesigner network is unbuilt in a real TouchDesigner. `docs/GOD-HERE-FINISH-LINE.md` keeps owner listening review, final mattes, reconstructed shots, browser-local data migration and physical devices open.
- **Loop compositor:** issue 85 (Studio loading stalls and compilation blocks the UI), issue 89 (continuous playback and bio-acoustic ecosystem, draft PR 88) and issue 71 (owner decisions pending).
- **Hub:** issue 12 (resume the approved portfolio plan through native admission). `docs/workstream-continuation.md` keeps original-media custody, source-led local bindings and desktop versus headset/XR acceptance open.

## Gaps found

1. **No portable loudness measurement.** Level work in postproduction (room stretch, direction audio, room refinement) shells out to FFmpeg or hard-codes targets; there was no tested BS.1770 / EBU R128 meter, delivery check or gain planner. Addressed by `tools/loudness.py` in tool-audiovisual-postproduction (separate pull request).
2. **Loop compositor gate needs its `verification` extra to mean anything.** Without Playwright and pytest installed, 35 of 1846 tests fail or error before judging the code, so a bare local run is red for environmental reasons that look like code failures. One genuine-looking render failure under load (signal 15) is undiagnosed.
3. **TouchDesigner network has no real-application proof.** Generation and simulation are tested; the repository says it was not built in TouchDesigner.
4. **Status was spread across four READMEs.** This page lines up heads, gates and next steps; refresh it when a head moves.

## Boundaries

This page asserts no artistic, device, delivery or custody acceptance for any work and describes no restricted repository. Each repository's own documents remain the owner of its claims.
