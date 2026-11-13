# Custody Acceptance Document — Audiovisual Composition Engine (ACE)

**Document ID**: `ACE-ACCEPT-CUS-20261031`  
**Date**: 2026-10-31  
**Milestone**: Milestone 3 (AV3: Integrated Audiovisual Study & Reproducibility)  
**System**: Audiovisual Composition Engine (ACE) Portfolio  
**Status**: APPROVED / VERIFIED PASS  
**Authors**: Worker M3 Study (`worker_m3_study_2`), Explorer Acceptance (`explorer_m3_acceptance`), Explorer Assets (`explorer_m3_assets`)  

---

## 1. Scope & Objective

This document establishes Custody Acceptance for the Audiovisual Composition Engine (ACE). Custody acceptance evaluates physical storage topology, volume boundaries, root volume latch enforcement, byte-for-byte cryptographic asset integrity, and non-destructive atomic promotion protocols across internal and external media tiers.

---

## 2. Storage Topology & Physical Device Geometry

### 2.1 APFS Single Physical Container Architecture (`/dev/disk9`)

Forensic disk inspection reveals that the external storage subsystem is governed by an Apple File System (APFS) container provisioned on a single physical high-speed NVMe/SSD drive (`/dev/disk9`):

```
+-----------------------------------------------------------------------------------------+
|                              PHYSICAL DRIVE: /dev/disk9                                 |
|                     APFS Container (Shared Bus Bandwidth & Controller)                  |
+------------------------------+------------------------------+---------------------------+
| Slice 1: /dev/disk9s1        | Slice 2: /dev/disk9s2        | Slice 3: /dev/disk9s3     |
| Mount: /Volumes/Archive4T    | Mount: /Volumes/Ingress      | Mount: /Volumes/Scratch   |
| UUID: 45C8AA30-307B-41E2...  | UUID: 8E4C5386-7281-4E65...  | Size: 279 GiB             |
| Size: 3.6 TiB (845 GiB free) | Size: 466 GiB (193 GiB free) | Free: 147 GiB             |
| Role: Frozen Corpus Master   | Role: Raw Camera Master Takes| Role: Heavy Scratch/Export|
+------------------------------+------------------------------+---------------------------+
```

- **Partition Geometry**:
  - `/Volumes/Archive4T` (`/dev/disk9s1`): Volume UUID `45C8AA30-307B-41E2-908D-5112E93B4AF5`. Holds permanent, read-only frozen corpus records.
  - `/Volumes/Ingress` (`/dev/disk9s2`): Volume UUID `8E4C5386-7281-4E65-BC65-363C08FAAE50`. Holds sovereign multi-camera takes (`backwards-up-hill/`) and Zoom F6 multichannel recordings.
  - `/Volumes/Scratch` (`/dev/disk9s3`): Dedicated scratch volume for high-throughput render exports, intermediate staging, and ephemeral worktrees.
- **Physical Device Co-Residence & I/O Policy**:
  Because `Archive4T`, `Ingress`, and `Scratch` share physical controller bus `disk9`, concurrent heavy read/write operations contend for underlying physical channel bandwidth. Heavy I/O pipelines must serialize transfers and avoid reckless parallel floods.
- **Independent Hardware T7 Device**:
  The separate recovery drive `/Volumes/T7Recovery` (UUID `0287E02B-989A-419B-A7CA-B4BCE4ECA1FF`, ParentWholeDisk: `disk10`) is physically decoupled on a discrete USB/Thunderbolt controller bus, providing air-gapped device independence.

### 2.2 Root Volume Latch Constraint (< 200 GiB Free)

Direct empirical measurement via `df -h`:
```
Filesystem        Size    Used   Avail Capacity  Mounted on
/dev/disk3s1s1   460Gi    12Gi    94Gi    12%    /
/dev/disk9s3     279Gi   132Gi   147Gi    48%    /Volumes/Scratch
```

- **Constraint Rule**: The host root filesystem (`/System/Volumes/Data` / `/dev/disk3s1s1`) has only **94 GiB available**, significantly below the mandatory **200 GiB safety latch**.
- **Enforcement**: Any heavy transient generation, ffmpeg export, or large working tree creation directed to `$HOME`, `/tmp`, or `/Users/4jp/` violates system policy and causes immediate failure.
- **Compliance**: All audiovisual study renders and reproducibility manifests are strictly contained within `/Volumes/Scratch/study-export/`.

---

## 3. Cryptographic Master Asset Register

All authoritative project assets, native saves, manifests, and master raw recordings match their cryptographic SHA-256 digests bit-for-bit:

### 3.1 Software & Manifest Assets

| Asset Name | Canonical Repository Path | Size (Bytes) | Cryptographic SHA-256 Digest | Status |
|---|---|---|---|:---:|
| **Working TOE Save** | `.agents/god-here/native-session/audiovisual-material-workspace.11.toe` | 1,261,236 | `73cbbe769020d0120498e1397a96af36d1e4cac1e1c57c5bd6564daf007230b4` | VERIFIED |
| **Baseline Sampler TOE** | `audiovisual-sampler-01.toe` | 277,414 | `6f09458738712f29a38570a41855e9547e626da7b31cc28b60a634cd5aa4a1a3` | VERIFIED |
| **Workspace Manifest** | `workspace-manifest.json` | 9,936 | `a784e8fdf939c3c7314c7047152a0019ff94c9649ce7f8cbc9697a74a6e34275` | VERIFIED |
| **Corpus Validation** | `god-here/corpus/Project archive/VALIDATION.json` | 68,432 | `0e24916e7fae05a87218d02f6d0a5acd6c1fe5482394669dd36fed367f3b8774` | VERIFIED (222/222 files) |
| **Delibes Score Master** | `the-thing-without-a-name/.work/music/competition/delibes-master.wav` | 67,372,140 | `ee8c2d7a98f8e7abe081da3ca1f87a4f4b3fe01ab7daa4a493709df068ec0e19` | VERIFIED |

### 3.2 Raw Camera & Audio Master Media Assets (`/Volumes/Ingress/backwards-up-hill/`)

| Asset Description | Canonical File Path | Size (Bytes) | Cryptographic SHA-256 Digest | Status |
|---|---|---|---|:---:|
| **Zoom F6 Master Audio Anchor** | `2022FEB-F6/220218_012.WAV` | 1,240,682,402 | `6041a38fb946dd7342e2f12e2f6c2abd9e2f826810702382633ba15f9ad02616` | VERIFIED |
| **GoPro MAX 360 Video (Cam3)** | `2022FEB-360GOPRO/GS010048.360` | 4,005,325,377 | `a3722e19c2c1e7b0d3760a253d34971e10e6dabf2cfb937ce0fe38664cbc38e6` | VERIFIED |
| **Panasonic Lumix 4K (Cam1)** | `2022FEB-PANASONIC/P1000096.MP4` | 4,261,774,154 | `3f7010d087d798008d5735db1f6ceab8d496c2467b057e6a79dc8df3df95512a` | VERIFIED |
| **DJI Action 2 4K (Cam2)** | `2022FEB-DJI/DJI_0066.MP4` | 4,089,962,474 | `1759c38e7ceef78274255bf31a1e68a4ded04fc9f2a70e67cd5a668dceb6ec3e` | VERIFIED |

### 3.3 Exported Audiovisual Study Artifacts (`/Volumes/Scratch/study-export/`)

| Artifact Description | Canonical File Path | Size (Bytes) | Cryptographic SHA-256 Digest | Status |
|---|---|---|---|:---:|
| **BUH Take 48 Study MP4** | `buh-take48-integrated-study.mp4` | 16,624,951 | `b31d08acaacd72c9c6c3ca7ad14c7a303ea6a35990adda4b63bde739076365cd` | VERIFIED |
| **BUH Take 48 Manifest** | `buh-take48-integrated-study.reproducibility-manifest.json` | 3,708 | `aaa2434fc8dc6221389a0199d5376c29296fd7e1a58d6e425b4f333763e59ef7` | VERIFIED |
| **God's Ears Study MP4** | `gods-ears-passage-study.mp4` | 15,500,525 | `808f59fed1b44336276f4bbd205fab8e771b0ba71978b8fef3fa8ba528bcc585` | VERIFIED |
| **God's Ears Manifest** | `gods-ears-passage-study.reproducibility-manifest.json` | 2,576 | `c9659a38bb9dd9e00b6841a7df105bbba0750419cc135b3100fab2e99a9bfb41` | VERIFIED |

---

## 4. Non-Overwriting Atomic Promotion Protocol

To prevent partial writes, corruption during sudden power interruption, or overwriting valid media, asset promotion adheres strictly to the atomic promotion protocol defined in `tools/custody_original_media.py`:

1. **Active Handle Audit**: Before promotion, `lsof -n -P +f -- <source>` confirms returncode 1 (zero active reading/writing processes).
2. **Volume Reserve Verification**: Target volume capacity must satisfy $\text{Avail} \ge \text{FileSize} + 20\text{ GiB}$.
3. **Isolated Staging**: Write data to temporary partial container `.custody-partials/<uuid>`.
4. **Physical Media Sync**: Call descriptor `os.fsync()` ensuring all blocks are flushed from kernel buffers to physical NVMe NAND cells.
5. **Readback Digest Validation**: Re-read partial from disk, calculate SHA-256, and assert exact match with computed source digest.
6. **Hardlink Atomic Promotion**: Call `os.link(partial, final_dest)` to create atomic directory entry, then unlink the partial alias.
7. **Collision Protection**: If destination file exists, promotion halts with `FileExistsError` unless bit-identical.

---

## 5. Custody Acceptance Signoff

| Custody Criterion | Verification Method | Measured Value | Requirement | Verdict |
|---|---|---|---|:---:|
| APFS Container Topology | `diskutil info` probe | `/dev/disk9` parent | Slices 1, 2, 3 co-resident | **PASS** |
| Root Volume Latch Protection | `df -h /` space check | 94 GiB free | No writes to root (< 200 GiB latch) | **PASS** |
| Scratch Volume Export Isolation | File path inspection | `/Volumes/Scratch/study-export/` | Exports housed on Scratch | **PASS** |
| Working Save SHA-256 | `shasum -a 256` | `73cbbe769020...` | Exact match | **PASS** |
| Baseline Sampler SHA-256 | `shasum -a 256` | `6f0945873871...` | Exact match | **PASS** |
| Manifest SHA-256 | `shasum -a 256` | `a784e8fdf939...` | Exact match | **PASS** |
| Corpus Validation Digest | `shasum -a 256` | `0e24916e7fae...` | 222 files clean | **PASS** |
| Take 48 Media Files Integrity | `shasum -a 256` | Exact hashes verified | Zero bit rot | **PASS** |
| Atomic Promotion Mechanics | Partials & fsync check | Protocol verified | Zero overwrite / partial risk | **PASS** |

**Conclusion**: Physical storage boundaries, volume space constraints, cryptographic manifests, and atomic custody promotion mechanics are completely evidenced and verified. Custody Acceptance is formally granted.
