#!/usr/bin/env bash
# ==============================================================================
# build_release_packet.sh — Audiovisual Composition Engine (ACE) v1.0.0
# ==============================================================================
# Constructs canonical release-packet-v1.0.0 on /Volumes/Scratch/study-export/
# with exact 6 subdirectories, full licenses, materialized media copies, tables, and SHA256SUMS.
# ==============================================================================
set -euo pipefail

REPO_ROOT="/Users/4jp/Workspace/audiovisual-composition-system"
SCRATCH_DIR="/Volumes/Scratch/study-export"
PACKET_DIR="${SCRATCH_DIR}/release-packet-v1.0.0"

ADMISSION_SHA256="6c41ab26b70e5a80de053ae397917f5dad34c14a33c0efd6a07dae7f940838e7"
REQUIRED_TOX_COUNT=24

# Copy (never link) every artifact so the packet is self-contained when restored elsewhere.
# A missing source aborts the build instead of leaving a dangling entry.
place() {
    local src="$1" dest="$2"
    if [[ ! -f "${src}" ]]; then
        echo "ERROR: required release artifact missing: ${src}" >&2
        exit 1
    fi
    rm -f "${dest}"
    cp -fL "${src}" "${dest}"
}

echo "=== Constructing Canonical Release Packet at ${PACKET_DIR} ==="

# 1. Initialize the 6 subdirectories
mkdir -p "${PACKET_DIR}/master"
mkdir -p "${PACKET_DIR}/stems"
mkdir -p "${PACKET_DIR}/project-saves/modular-tox"
mkdir -p "${PACKET_DIR}/project-saves/tables"
mkdir -p "${PACKET_DIR}/metadata"
mkdir -p "${PACKET_DIR}/licensing"
mkdir -p "${PACKET_DIR}/docs"

# 2. Populate master/
place "${SCRATCH_DIR}/buh-take48-integrated-study.mp4" "${PACKET_DIR}/master/buh-take48-integrated-study.mp4"
place "${SCRATCH_DIR}/gods-ears-passage-study.mp4" "${PACKET_DIR}/master/gods-ears-passage-study.mp4"

# 3. Populate stems/
place "/Volumes/Ingress/backwards-up-hill/2022FEB-F6/220218_012.WAV" "${PACKET_DIR}/stems/stem-zoom-f6-anchor.wav"
place "${REPO_ROOT}/the-thing-without-a-name/.work/music/competition/delibes-master.wav" "${PACKET_DIR}/stems/stem-delibes-score.wav"
place "${REPO_ROOT}/god-here/corpus/Project archive/Hosted previews/Five realities/fx/assets/dialogue-candidate.wav" "${PACKET_DIR}/stems/stem-dialogue-candidate.wav"
place "${REPO_ROOT}/god-here/corpus/Project archive/Hosted previews/Five realities/media/foley-movement.m4a" "${PACKET_DIR}/stems/stem-foley-movement.m4a"
place "${REPO_ROOT}/god-here/corpus/Project archive/Hosted previews/Five realities/media/foley-glass.m4a" "${PACKET_DIR}/stems/stem-foley-glass.m4a"

# 4. Populate project-saves/
place "${REPO_ROOT}/.agents/god-here/native-session/audiovisual-material-workspace.11.toe" "${PACKET_DIR}/project-saves/audiovisual-material-workspace.11.toe"
place "${REPO_ROOT}/audiovisual-sampler-01.toe" "${PACKET_DIR}/project-saves/audiovisual-sampler-01.toe"

# Populate modular-tox/ (the publication spec requires at least the 24 modular operators)
tox_count=0
shopt -s nullglob
for tox in "${REPO_ROOT}/.agents/god-here/"*.tox; do
    place "${tox}" "${PACKET_DIR}/project-saves/modular-tox/$(basename "${tox}")"
    tox_count=$((tox_count + 1))
done
shopt -u nullglob
if (( tox_count < REQUIRED_TOX_COUNT )); then
    echo "ERROR: modular operator inventory incomplete: ${tox_count} < ${REQUIRED_TOX_COUNT}" >&2
    exit 1
fi

# Populate tables/
# Attention timings are authored score ticks (contiguous, 1183 total), not 30 fps video frames:
# the 85-107 s passage is 660 video frames, so no frame-rate conversion is applied here.
cat << 'EOF' > "${PACKET_DIR}/project-saves/tables/table_attention.tsv"
beat_index	beat_name	start_tick	duration_ticks	thematic_role
1	Listen	0	34	Initial sensory calibration; focus on subtle acoustic cues
2	Inbox	34	146	Engagement with technological / conversational demand
3	Turn away	180	101	Aversion and physical repositioning across optical axis
4	Reply	281	90	Vocalized response and counter-gesture
5	Absent	371	194	Disconnection; performer opacity falls back to ambient trace
6	Return	565	74	Sudden re-entry into conversational foreground
7	Out	639	104	Spatial divergence and directional gaze shift
8	Question	743	60	Inquisitive pause; suspension of motion
9	Correction	803	295	Protracted adjustment and spatial recalibration
10	Challenge	1098	85	Climax; confronting the gaze and final resolution
EOF

cat << 'EOF' > "${PACKET_DIR}/project-saves/tables/table_crops.tsv"
performer_id	name	crop_x	crop_y	crop_width	crop_height	framing_mode
1	Mark	0.120	0.200	0.350	0.600	proportional
2	Enrique	0.450	0.180	0.320	0.580	proportional
3	Hunter	0.700	0.220	0.280	0.550	proportional
4	Dan	0.300	0.350	0.250	0.450	occluded_trace
5	Chris	0.580	0.320	0.260	0.480	proportional
EOF

cat << 'EOF' > "${PACKET_DIR}/project-saves/tables/table_accents.tsv"
accent_id	transient_type	source_time_sec	fade_attack_ms	fade_decay_ms	dc_offset_free
1	glass_clink_01	85.450	15	25	true
2	sip_contact_01	87.120	10	20	true
3	movement_rustle	89.300	20	30	true
4	glass_clink_02	93.850	15	25	true
5	performer_shift	97.200	25	35	true
6	vocal_intake	101.100	10	15	true
7	glass_setdown	105.800	15	25	true
EOF

cat << 'EOF' > "${PACKET_DIR}/project-saves/tables/table_words.tsv"
word_id	text_cue	start_sec	duration_sec	fade_in_sec	fade_out_sec
1	INBOX	86.130	1.200	0.150	0.150
2	OUT	91.000	1.200	0.150	0.150
3	HOW	95.000	1.200	0.150	0.150
4	WHAT	100.000	1.200	0.150	0.150
5	HOW?	104.500	1.200	0.150	0.150
EOF

# 5. Populate metadata/
place "${SCRATCH_DIR}/buh-take48-integrated-study.reproducibility-manifest.json" "${PACKET_DIR}/metadata/buh-take48-integrated-study.reproducibility-manifest.json"
place "${SCRATCH_DIR}/gods-ears-passage-study.reproducibility-manifest.json" "${PACKET_DIR}/metadata/gods-ears-passage-study.reproducibility-manifest.json"
place "${REPO_ROOT}/docs/evidence/2026-10-10-tmb-spatial-composition/edition-receipt.json" "${PACKET_DIR}/metadata/edition-receipt.json"

# Enforce the pinned admission receipt digest before anything is checksummed.
receipt_sha="$(shasum -a 256 "${PACKET_DIR}/metadata/edition-receipt.json" | awk '{print $1}')"
if [[ "${receipt_sha}" != "${ADMISSION_SHA256}" ]]; then
    echo "ERROR: admission receipt digest ${receipt_sha} != pinned ${ADMISSION_SHA256}" >&2
    exit 1
fi

cat << 'EOF' > "${PACKET_DIR}/metadata/sensory-accessibility.vtt"
WEBVTT

1
00:00:01.130 --> 00:00:02.330
INBOX

2
00:00:06.000 --> 00:00:07.200
OUT

3
00:00:10.000 --> 00:00:11.200
HOW

4
00:00:15.000 --> 00:00:16.200
WHAT

5
00:00:19.500 --> 00:00:20.700
HOW?
EOF

cat << 'EOF' > "${PACKET_DIR}/metadata/hardware-spec.json"
{
  "host_hardware": {
    "architecture": "arm64",
    "chipset": "Apple Silicon",
    "platform": "macOS (Darwin)",
    "storage_geometry": {
      "physical_container": "/dev/disk9",
      "scratch_mount": "/Volumes/Scratch",
      "ingress_mount": "/Volumes/Ingress",
      "archive_mount": "/Volumes/Archive4T"
    }
  },
  "toolchain": {
    "ffmpeg": "9.0.2",
    "video_hardware_encoder": "h264_videotoolbox",
    "audio_encoder": "aac (LC)",
    "touchdesigner_build": "2025.33230",
    "python": "3.14",
    "node": "v20"
  }
}
EOF

# 6. Populate licensing/
cp "/Users/4jp/Workspace/library/shelves/organvm-ii-poiesis/alchemical-synthesizer/LICENSES/AGPL-3.0-or-later.txt" "${PACKET_DIR}/licensing/LICENSE-SOFTWARE"

# Fetch full verbatim CC-BY-NC-SA-4.0 legal text
license_tmp="$(mktemp)"
trap 'rm -f "${license_tmp}"' EXIT
curl --fail --show-error --silent --location \
    https://creativecommons.org/licenses/by-nc-sa/4.0/legalcode.txt -o "${license_tmp}"
if ! grep -q "Attribution-NonCommercial-ShareAlike 4.0 International" "${license_tmp}"; then
    echo "ERROR: downloaded artwork license does not contain the CC BY-NC-SA 4.0 legal text" >&2
    exit 1
fi
install -m 0644 "${license_tmp}" "${PACKET_DIR}/licensing/LICENSE-ARTWORK"

cat << 'EOF' > "${PACKET_DIR}/licensing/ATTRIBUTION.md"
# Audiovisual Composition Engine (ACE) — Archival Release Attribution

## Engineering & Artistic Direction
- **System**: Audiovisual Composition Engine (ACE) Portfolio
- **Lead Direction**: Anthony James Padavano / ORGANVM
- **Coordinating Repository**: `audiovisual-composition-system`

## Asset Provenance & Credits
- **Backwards-Up-Hill (BUH Take 48)**:
  * Multichannel field recordings and camera capture: February 2022.
  * Sensors: Lumix G100 / Panasonic GH5 (Cam1), DJI Action 2 (Cam2), GoPro MAX 360 (Cam3), Zoom F6 5-channel 32-bit float audio.
- **God's Ears Passage (85.0s–107.0s)**:
  * Performers: Mark, Enrique, Hunter, Dan, Chris.
  * Score and choreography: TouchDesigner 2025.33230 network.
- **Delibes Orchestral Score Master**:
  * Original composition: Léo Delibes. Master recording preserved in `the-thing-without-a-name`.

## Dual Licensing
- **Software**: GNU Affero General Public License v3.0 (AGPL-3.0).
- **Artwork & Media**: Creative Commons Attribution-NonCommercial-ShareAlike 4.0 (CC-BY-NC-SA-4.0).
EOF

# 7. Populate docs/ (6th Subdirectory)
place "${REPO_ROOT}/docs/acceptance/artistic-acceptance-2026-10-31.md" "${PACKET_DIR}/docs/artistic-acceptance-2026-10-31.md"
place "${REPO_ROOT}/docs/acceptance/physical-device-acceptance-2026-10-31.md" "${PACKET_DIR}/docs/physical-device-acceptance-2026-10-31.md"
place "${REPO_ROOT}/docs/acceptance/custody-acceptance-2026-10-31.md" "${PACKET_DIR}/docs/custody-acceptance-2026-10-31.md"
place "${REPO_ROOT}/docs/acceptance/publication-acceptance-2026-10-31.md" "${PACKET_DIR}/docs/publication-acceptance-2026-10-31.md"
place "${REPO_ROOT}/TEST_READY.md" "${PACKET_DIR}/docs/TEST_READY.md"

# 8. Generate SHA256SUMS Manifest
echo "Generating SHA256SUMS manifest..."
cd "${PACKET_DIR}"
rm -f SHA256SUMS
find . -type f ! -name "SHA256SUMS" ! -name ".DS_Store" -print0 | LC_ALL=C sort -z | xargs -0 shasum -a 256 | sed 's|  \./|  |' > SHA256SUMS

echo "Verifying SHA256SUMS manifest..."
shasum -a 256 -c SHA256SUMS

echo "=== Canonical Release Packet Successfully Constructed & Verified ==="
