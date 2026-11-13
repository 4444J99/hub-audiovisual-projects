"""One-shot Textport readback. No node edits, cooking, saving, or media reads.

Run inside the already-open TouchDesigner session, using the command provided
with this file. Findings stay in this workspace's ignored .agents directory.
"""


def inspect_session(td):
    import json
    import os
    from datetime import datetime, timezone
    from pathlib import Path

    workspace = Path("/Users/4jp/Workspace/audiovisual-composition-system")
    authorized_projects = {
        (workspace / "audiovisual-sampler-01.toe").resolve(),
        (workspace / ".agents/god-here/native-session/audiovisual-material-workspace.11.toe").resolve(),
    }
    actual = (Path(td.project.folder) / td.project.name).resolve()
    if actual not in authorized_projects:
        authorized_str = ", ".join(str(p) for p in sorted(authorized_projects))
        raise RuntimeError(
            f"Inspection refused: open project {actual} is not in authorized workspace projects: {authorized_str}"
        )

    root = td.op("/")
    dirty_before = root.dirty
    excluded = {"/sys", "/ui", "/local"}
    roots = [node for node in root.children if node.path not in excluded]
    nodes, pending = [], list(roots)
    while pending:
        node = pending.pop()
        nodes.append(node)
        if node.isCOMP:
            pending.extend(node.children)

    report = {
        "captured_utc": datetime.now(timezone.utc).isoformat(),
        "project": {"path": str(actual), "version": str(td.app.version),
                    "build": str(td.app.build), "dirty_before": dirty_before},
        "scope": {"roots": [node.path for node in roots],
                  "excluded_system_roots": sorted(excluded),
                  "node_count": len(nodes)},
        "networks": [{"path": node.path, "type": node.OPType,
                      "children": len(node.children)} for node in nodes if node.isCOMP],
        "sources": [], "audio_routing": [], "missing_media": [],
        "errors": [], "inspection_issues": [],
        "playback": "Not tested; a read-only snapshot does not prove playback.",
    }

    def parameters(node, names):
        values = {}
        for name in names:
            par = getattr(node.par, name, None)
            if par is None:
                continue
            # Reading constant values avoids executing user expressions or exports.
            if str(par.mode).split(".")[-1].upper() != "CONSTANT":
                values[name] = {"mode": str(par.mode), "status": "not evaluated"}
                report["inspection_issues"].append(
                    {"path": node.path, "parameter": name,
                     "reason": "Dynamic parameter left unevaluated to preserve session."})
                continue
            values[name] = par.val
        return values

    for node in sorted(nodes, key=lambda item: item.path):
        kind = node.OPType
        source = (node.isTOP and (not node.inputs or kind == "moviefileinTOP"))
        audio = node.isCHOP
        if source or audio:
            names = ("file", "play", "playmode", "speed", "active", "volume",
                     "device", "driver", "outputs", "moviefileintop", "chops")
            values = parameters(node, names)
            entry = {"path": node.path, "type": kind, "parameters": values,
                     "inputs": [item.path for item in node.inputs],
                     "outputs": [item.path for item in node.outputs]}
            if source:
                report["sources"].append(entry)
            if audio:
                report["audio_routing"].append(entry)
            # Only check file-source paths, never output targets or media contents.
            if kind in {"moviefileinTOP", "audiofileinCHOP", "audioplayCHOP"}:
                media = values.get("file")
                if isinstance(media, str) and media:
                    expanded = td.tdu.expandPath(media)
                    if "://" in expanded:
                        entry["media"] = {"path": expanded, "status": "URL not accessed"}
                    else:
                        path = Path(expanded).expanduser()
                        if not path.is_absolute():
                            path = Path(td.project.folder) / path
                        exists = path.exists()
                        entry["media"] = {"path": str(path), "exists": exists}
                        if not exists:
                            report["missing_media"].append(
                                {"node": node.path, "path": str(path)})
                elif media == "":
                    entry["media"] = {"status": "No file assigned"}
        for method in ("errors", "warnings", "scriptErrors"):
            message = getattr(node, method)(recurse=False)
            if message:
                report["errors"].append(
                    {"path": node.path, "kind": method, "message": message})

    report["project"]["dirty_after"] = root.dirty
    report["status"] = "complete" if not report["inspection_issues"] else "partial"
    destination = workspace / ".agents" / "touchdesigner-inspection"
    destination.mkdir(mode=0o700, parents=True, exist_ok=True)
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S%fZ")
    output = destination / ("session-" + stamp + ".json")
    fd = os.open(str(output), os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    with os.fdopen(fd, "w", encoding="utf-8") as handle:
        json.dump(report, handle, indent=2)
        handle.write("\n")
    print("TouchDesigner session inspection written to " + str(output))


CANONICAL_TOE_TARGETS = [
    {
        "id": "working_save",
        "name": "Working Composition Save (God's Ears 85–107s passage)",
        "rel_path": ".agents/god-here/native-session/audiovisual-material-workspace.11.toe",
        "manifest_rel_path": ".agents/god-here/native-session/CURRENT.json",
        "expected_bytes": 1261236,
        "expected_sha256": "73cbbe769020d0120498e1397a96af36d1e4cac1e1c57c5bd6564daf007230b4",
    },
    {
        "id": "baseline_sampler",
        "name": "Committed Baseline Sampler Save",
        "rel_path": "audiovisual-sampler-01.toe",
        "manifest_rel_path": None,
        "expected_bytes": 1300588,
        "expected_sha256": "6f09458738712f29a38570a41855e9547e626da7b31cc28b60a634cd5aa4a1a3",
    },
]


def verify_offline_toe_files(workspace_root=None, app_path=None, verbose=True):
    """Genuinely verifies canonical .toe saves offline without GUI execution.

    Validates file existence, exact byte size, cryptographic SHA-256 digest,
    manifest cross-referencing (CURRENT.json), binary header parsing via toeexpand -b,
    and build concordance against TouchDesigner Info.plist (CFBundleShortVersionString).
    """
    import hashlib
    import json
    import os
    import plistlib
    import subprocess
    from pathlib import Path

    if workspace_root is None:
        workspace_root = Path("/Users/4jp/Workspace/audiovisual-composition-system")
    else:
        workspace_root = Path(workspace_root)

    if app_path is None:
        app_path = Path(os.environ.get("TOUCHDESIGNER_APP", "/Applications/TouchDesigner.app"))
    else:
        app_path = Path(app_path)

    plist_path = app_path / "Contents/Info.plist"
    if not plist_path.is_file():
        raise FileNotFoundError(f"TouchDesigner Info.plist missing at {plist_path}")

    with open(plist_path, "rb") as fp:
        plist_data = plistlib.load(fp)
    host_version = plist_data.get("CFBundleShortVersionString")
    if not host_version:
        raise ValueError(f"CFBundleShortVersionString not found in {plist_path}")

    toeexpand_bin = app_path / "Contents/MacOS/toeexpand"
    if not toeexpand_bin.is_file():
        raise FileNotFoundError(f"toeexpand binary missing at {toeexpand_bin}")
    if not os.access(toeexpand_bin, os.X_OK):
        raise PermissionError(f"toeexpand binary not executable at {toeexpand_bin}")

    if verbose:
        print("==================================================================")
        print("TouchDesigner Offline Save & Build Concordance Verification")
        print("==================================================================")
        print(f"Host TouchDesigner App: {app_path}")
        print(f"Host Build (CFBundleShortVersionString): {host_version}")
        print(f"toeexpand Binary: {toeexpand_bin}\n")

    verified_count = 0
    for target in CANONICAL_TOE_TARGETS:
        p = workspace_root / target["rel_path"]
        name = target["name"]
        exp_bytes = target["expected_bytes"]
        exp_sha = target["expected_sha256"]

        if verbose:
            print(f"Target: {name}")
            print(f"  Path: {p}")

        if not p.is_file():
            raise FileNotFoundError(f"Canonical TOE file missing: {p}")

        size = p.stat().st_size
        if size != exp_bytes:
            raise ValueError(f"Size mismatch for {p}: got {size} bytes, expected {exp_bytes}")
        if verbose:
            print(f"  Size: {size:,} bytes (OK)")

        actual_sha256 = hashlib.sha256(p.read_bytes()).hexdigest()
        if actual_sha256 != exp_sha:
            raise ValueError(f"SHA-256 mismatch for {p}: got {actual_sha256}, expected {exp_sha}")
        if verbose:
            print(f"  SHA-256: {actual_sha256} (MATCH)")

        if target.get("manifest_rel_path"):
            mp = workspace_root / target["manifest_rel_path"]
            if not mp.is_file():
                raise FileNotFoundError(f"Governing manifest missing: {mp}")
            with open(mp, "r", encoding="utf-8") as mfp:
                mdata = json.load(mfp)
            if mdata.get("sha256") != actual_sha256:
                raise ValueError(f"Manifest sha256 mismatch in {mp}: {mdata.get('sha256')} != {actual_sha256}")
            if mdata.get("bytes") != size:
                raise ValueError(f"Manifest bytes mismatch in {mp}: {mdata.get('bytes')} != {size}")
            if verbose:
                print(f"  Manifest Authority: {mp.name} (MATCH)")

        # Run toeexpand -b (Note: exits with code 1 upon successful header display)
        proc = subprocess.run([str(toeexpand_bin), "-b", str(p)], capture_output=True, text=True)
        if proc.stderr.strip():
            raise RuntimeError(f"toeexpand reported error for {p}: {proc.stderr.strip()}")

        header = {}
        for line in proc.stdout.strip().splitlines():
            parts = line.split(None, 1)
            if len(parts) == 2:
                header[parts[0].lower()] = parts[1].strip()

        toe_build = header.get("build")
        if not toe_build:
            raise ValueError(f"Could not parse build version from toeexpand output:\n{proc.stdout}")

        if toe_build != host_version:
            raise ValueError(f"Build skew detected for {p}: toe build {toe_build} != host build {host_version}")

        if verbose:
            header_summary = ", ".join(f"{k} {v}" for k, v in header.items())
            print(f"  toeexpand Header: {header_summary}")
            print(f"  Build Concordance: {toe_build} == {host_version} (ZERO SKEW)\n")

        verified_count += 1

    if verbose:
        print("==================================================================")
        print(f"VERDICT: ALL TOUCHDESIGNER SAVES & BUILD CONCORDANCE VERIFIED ({verified_count}/{len(CANONICAL_TOE_TARGETS)})")
        print("==================================================================")
    return True


if __name__ == "__main__":
    import sys
    # Handle help
    if "--help" in sys.argv or "-h" in sys.argv:
        print("Usage:")
        print("  python inspect_touchdesigner_session.py --probe-only   # Offline TOE header & build verification")
        print("  python inspect_touchdesigner_session.py                # Run inside TouchDesigner session (Textport)")
        sys.exit(0)

    # Offline probe mode (invoked by E2E runner Scenario 5 or command line)
    if "--probe-only" in sys.argv or "--offline" in sys.argv or "--verify-offline" in sys.argv:
        try:
            verify_offline_toe_files()
            sys.exit(0)
        except Exception as exc:
            print(f"ERROR: TouchDesigner offline inspection failed: {exc}", file=sys.stderr)
            sys.exit(1)

    # Interactive session mode (requires running inside TouchDesigner's Python environment)
    try:
        td = __import__("td")
    except ImportError:
        print(
            "ERROR: 'td' module not found. Interactive session inspection must be run inside "
            "TouchDesigner's Python Textport.\nFor offline file and build verification, run with --probe-only.",
            file=sys.stderr,
        )
        sys.exit(2)

    inspect_session(td)
