# Publication Acceptance Document — Audiovisual Composition Engine (ACE)

**Document ID**: `ACE-ACCEPT-PUB-20261031`  
**Date**: 2026-10-31  
**Milestone**: Milestone 3 (AV3: Integrated Audiovisual Study & Reproducibility)  
**System**: Audiovisual Composition Engine (ACE) Portfolio  
**Status**: APPROVED / VERIFIED PASS  
**Authors**: Worker M3 Study (`worker_m3_study_2`), Explorer Acceptance (`explorer_m3_acceptance`), Explorer Assets (`explorer_m3_assets`)  

---

## 1. Scope & Objective

This document establishes Publication Acceptance for the Audiovisual Composition Engine (ACE) portfolio and integrated study deliverables. Publication acceptance verifies canonical packaging structure, cryptographic checksum manifests (`SHA256SUMS`), dual licensing attribution (AGPL-3.0 / CC-BY-NC-SA-4.0), pinned edition admission receipts, and bit-level TouchDesigner save reproducibility.

---

## 2. Canonical Release Packet Architecture

The published study release bundle is structured according to the standardized archival distribution layout:

```
release-packet-v1.0.0/
├── master/
│   ├── buh-take48-integrated-study.mp4        # VideoToolbox H.264 / AAC 48kHz stereo (1080p multi-view)
│   └── gods-ears-passage-study.mp4            # VideoToolbox H.264 / AAC 48kHz stereo (720p 22s passage)
├── stems/
│   ├── stem-zoom-f6-anchor.wav                # 48kHz 24-bit PCM 5-channel Zoom F6 recording
│   ├── stem-delibes-score.wav                 # 48kHz 16-bit PCM Delibes orchestral score master
│   ├── stem-dialogue-candidate.wav            # 24kHz 16-bit PCM God's Ears dialogue stem
│   ├── stem-foley-movement.m4a                # 48kHz AAC procedural movement foley
│   └── stem-foley-glass.m4a                   # 48kHz AAC procedural glass contact foley
├── project-saves/
│   ├── audiovisual-material-workspace.11.toe # TouchDesigner Build 2025.33230 working save
│   ├── audiovisual-sampler-01.toe            # Baseline git-tracked sampler save
│   ├── modular-tox/                          # 24 modular .tox network operators
│   └── tables/
│       ├── table_attention.tsv               # 10 attention beats timing table
│       ├── table_crops.tsv                   # 5 performer crop coordinates
│       ├── table_accents.tsv                 # 7 sparse sound accent envelopes
│       └── table_words.tsv                   # 5 expressive text cues
├── metadata/
│   ├── buh-take48-integrated-study.reproducibility-manifest.json
│   ├── gods-ears-passage-study.reproducibility-manifest.json
│   ├── edition-receipt.json                  # Pinned admission receipt (ADMISSION_SHA256)
│   ├── sensory-accessibility.vtt             # WebVTT captions (reading speed <= 18 cps)
│   └── hardware-spec.json                    # Toolchain and Apple Silicon encoder profile
├── licensing/
│   ├── LICENSE-SOFTWARE                      # GNU Affero General Public License v3.0 (AGPL-3.0)
│   ├── LICENSE-ARTWORK                       # Creative Commons CC-BY-NC-SA-4.0
│   └── ATTRIBUTION.md                        # Provenance and performer credits
├── docs/
│   ├── artistic-acceptance-2026-10-31.md     # Acceptance signoff document
│   ├── physical-device-acceptance-2026-10-31.md # Acceptance signoff document
│   ├── custody-acceptance-2026-10-31.md      # Acceptance signoff document
│   ├── publication-acceptance-2026-10-31.md  # Acceptance signoff document
│   └── TEST_READY.md                         # Unified E2E test suite signoff
└── SHA256SUMS                                # Cryptographic manifest of all bundle items
```

---

## 3. Cryptographic Checksum Manifest (`SHA256SUMS`)

Every artifact within the release packet is cataloged in `SHA256SUMS` using standard GNU coreutils format:
```
<sha256_hex_digest_lowercase>  <relative_filepath>
```
Verification command:
```bash
shasum -a 256 -c SHA256SUMS
```
Must evaluate every entry and return exit code 0.

---

## 4. Dual Licensing & Edition Admission Attribution

### 4.1 Dual Licensing Model

The ACE portfolio operates under an explicit dual licensing boundary:
1. **Software Implementation (AGPL-3.0)**:
   - Covers all Python modules (`amp/`), Node.js engines (`engine/`), shell orchestration scripts, test runners (`run_all_e2e_tests.sh`), and verification harnesses.
   - Enforces reciprocity and open reproducibility for all computational infrastructure.
2. **Audiovisual Composition & Artwork (CC-BY-NC-SA-4.0)**:
   - Covers all rendered video studies, audio stems, multichannel field recordings, performer crops, and TouchDesigner `.toe` / `.tox` compositional network architectures.
   - Grants attribution, non-commercial sharing, and derivative rights under identical terms.

### 4.2 Pinned Edition Admission Receipt

System admission requires cryptographic verification of the pinned admission receipt:
- **Receipt Canonical Location**:
  `docs/evidence/2026-10-10-tmb-spatial-composition/edition-receipt.json`
- **Pinned Cryptographic Hash**:
  ```python
  ADMISSION_SHA256 = "6c41ab26b70e5a80de053ae397917f5dad34c14a33c0efd6a07dae7f940838e7"
  ```
- **Immutability Contract**:
  Verified in `time-moment-brief/tests/test_transport_gate.py:test_atomic_admission`. Any mutation, tampering, or missing receipt immediately blocks playback qualification with exit code 1.

---

## 5. TouchDesigner Save Reproducibility Contract

### 5.1 Host Build Alignment

- **Required Application Build**: Derivative TouchDesigner `2025.33230` (macOS Apple Silicon arm64).
- **Installed Runtime Verification**:
  ```bash
  defaults read /Applications/TouchDesigner.app/Contents/Info.plist CFBundleShortVersionString
  # Output: 2025.33230
  ```
- **Save File Header Verification**:
  Inspected via `tools/inspect_touchdesigner_session.py`, executing offline `toeexpand -b` header probe on both `.toe` files, confirming zero build skew against `Info.plist` `CFBundleShortVersionString` (`2025.33230`) and matching manifest digests.

### 5.2 Deterministic Network Replay

When `audiovisual-material-workspace.11.toe` is opened in TouchDesigner 2025.33230 with disk-bound `tables/` and `stems/`:
1. Playing from $t=85.0\text{s}$ to $t=107.0\text{s}$ deterministically evaluates all 10 attention beats with 0 cook errors.
2. The Audio Device Out peak matches $0.691441$ within $\pm 0.001\text{ dBFS}$.
3. Non-destructive textport inspection via `tools/inspect_touchdesigner_session.py` operates in read-only mode with zero file dirtying.

---

## 6. Publication Acceptance Signoff

| Publication Criterion | Verification Method | Measured Value | Standard / Requirement | Verdict |
|---|---|---|---|:---:|
| Release Packet Layout | Directory structure audit | 6 subdirectories present | Conforms to release spec (`/Volumes/Scratch/study-export/release-packet-v1.0.0/`) | **PASS** |
| Cryptographic Manifest | `shasum -a 256 -c` | All files verified | Zero mismatches, exit 0 (verified in Tier 4 Scenario 7) | **PASS** |
| Software License Present | License file inspection | `LICENSE-SOFTWARE` | AGPL-3.0 text complete | **PASS** |
| Artwork License Present | License file inspection | `LICENSE-ARTWORK` | CC-BY-NC-SA-4.0 text complete | **PASS** |
| Admission Receipt SHA-256 | Bit-level sha256 comparison | `6c41ab26b70e...` | Exact match with pinned constant | **PASS** |
| TouchDesigner Build Match | Host application probe | `2025.33230` | Matches save file build | **PASS** |
| Working Save SHA-256 | `shasum -a 256` | `73cbbe769020...` | Exact match | **PASS** |
| Sampler Baseline SHA-256 | `shasum -a 256` | `6f0945873871...` | Exact match | **PASS** |
| Non-destructive TD Inspection | Offline toeexpand header probe & session inspection contract | Build 2025.33230 matched (zero build skew), hashes & sizes verified | Both canonical .toe saves verified | **PASS** |

**Conclusion**: All publication packaging standards, checksum manifests, licensing declarations, admission pinning, and TouchDesigner reproducibility contracts have been verified. Publication Acceptance is formally granted.
