import importlib.util
from pathlib import Path
import sys
import tempfile
import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

MODULE_PATH = Path(__file__).resolve().parents[1] / "inspect_touchdesigner_session.py"
SPEC = importlib.util.spec_from_file_location("inspect_touchdesigner_session", MODULE_PATH)
inspect_mod = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(inspect_mod)

verify_offline_toe_files = inspect_mod.verify_offline_toe_files
inspect_session = inspect_mod.inspect_session


def test_verify_offline_toe_files_passes_on_live_repository():
    """Verify that live repository canonical .toe files pass full offline verification."""
    assert verify_offline_toe_files(verbose=False) is True


def test_verify_offline_toe_files_fails_on_missing_file():
    """Verify that missing TOE file raises FileNotFoundError."""
    with tempfile.TemporaryDirectory() as tmpdir:
        with pytest.raises(FileNotFoundError):
            verify_offline_toe_files(workspace_root=Path(tmpdir), verbose=False)


def test_verify_offline_toe_files_fails_on_corrupt_size():
    """Verify that file size mismatch raises ValueError."""
    with tempfile.TemporaryDirectory() as tmpdir:
        root = Path(tmpdir)
        target = root / ".agents/god-here/native-session/audiovisual-material-workspace.11.toe"
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(b"dummy corrupted content")
        with pytest.raises(ValueError, match="Size mismatch"):
            verify_offline_toe_files(workspace_root=root, verbose=False)


def test_verify_offline_toe_files_fails_on_corrupt_hash():
    """Verify that file hash mismatch raises ValueError when size matches."""
    with tempfile.TemporaryDirectory() as tmpdir:
        root = Path(tmpdir)
        target = root / ".agents/god-here/native-session/audiovisual-material-workspace.11.toe"
        target.parent.mkdir(parents=True, exist_ok=True)
        # Create a file of exact expected size (1,261,236 bytes) but wrong content
        target.write_bytes(b"0" * 1261236)
        with pytest.raises(ValueError, match="SHA-256 mismatch"):
            verify_offline_toe_files(workspace_root=root, verbose=False)


def test_inspect_session_refuses_unauthorized_project():
    """Verify that inspect_session raises RuntimeError for unauthorized project paths."""
    class MockProject:
        folder = "/unauthorized/path"
        name = "rogue.toe"

    class MockTD:
        project = MockProject()

    with pytest.raises(RuntimeError, match="Inspection refused: open project"):
        inspect_session(MockTD())


def test_inspect_session_validates_authorized_project_path():
    """Verify that inspect_session recognizes authorized project paths before graph scan."""
    class MockNode:
        path = "/"
        dirty = False
        children = []

    class MockApp:
        version = "2025.33230"
        build = "2025.33230"

    class MockProject:
        folder = "/Users/4jp/Workspace/audiovisual-composition-system"
        name = "audiovisual-sampler-01.toe"

    class MockTD:
        project = MockProject()
        app = MockApp()

        def op(self, path):
            return MockNode()

    inspect_session(MockTD())
