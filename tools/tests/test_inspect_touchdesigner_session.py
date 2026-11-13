import importlib.util
from pathlib import Path
import sys
import tempfile
import os
import unittest

REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

MODULE_PATH = Path(__file__).resolve().parents[1] / "inspect_touchdesigner_session.py"
SPEC = importlib.util.spec_from_file_location("inspect_touchdesigner_session", MODULE_PATH)
inspect_mod = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(inspect_mod)

verify_offline_toe_files = inspect_mod.verify_offline_toe_files
inspect_session = inspect_mod.inspect_session


TD_APP = Path(os.environ.get("TOUCHDESIGNER_APP", "/Applications/TouchDesigner.app"))
LIVE_ROOT = Path("/Users/4jp/Workspace/audiovisual-composition-system")
HOST_HAS_TD = (TD_APP / "Contents/MacOS/toeexpand").is_file()
LIVE_TOE = LIVE_ROOT / ".agents/god-here/native-session/audiovisual-material-workspace.11.toe"
NATIVE_TOE = ".agents/god-here/native-session/audiovisual-material-workspace.11.toe"


class VerifyOfflineToeFiles(unittest.TestCase):
    @unittest.skipUnless(HOST_HAS_TD and LIVE_TOE.is_file(), "needs host TouchDesigner and live native session")
    def test_passes_on_live_repository(self):
        self.assertIs(verify_offline_toe_files(verbose=False), True)

    @unittest.skipUnless(HOST_HAS_TD, "needs host TouchDesigner")
    def test_fails_on_missing_file(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            with self.assertRaises(FileNotFoundError):
                verify_offline_toe_files(workspace_root=Path(tmpdir), verbose=False)

    @unittest.skipUnless(HOST_HAS_TD, "needs host TouchDesigner")
    def test_fails_on_corrupt_size(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            target = Path(tmpdir) / NATIVE_TOE
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes(b"dummy corrupted content")
            with self.assertRaisesRegex(ValueError, "Size mismatch"):
                verify_offline_toe_files(workspace_root=Path(tmpdir), verbose=False)

    @unittest.skipUnless(HOST_HAS_TD, "needs host TouchDesigner")
    def test_fails_on_corrupt_hash(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            target = Path(tmpdir) / NATIVE_TOE
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes(b"0" * 1261236)
            with self.assertRaisesRegex(ValueError, "SHA-256 mismatch"):
                verify_offline_toe_files(workspace_root=Path(tmpdir), verbose=False)


class InspectSession(unittest.TestCase):
    def test_refuses_unauthorized_project(self):
        class MockProject:
            folder = "/unauthorized/path"
            name = "rogue.toe"

        class MockTD:
            project = MockProject()

        with self.assertRaisesRegex(RuntimeError, "Inspection refused: open project"):
            inspect_session(MockTD())

    def _td(self, folder, dirty_values):
        values = iter(dirty_values)

        class MockNode:
            path = "/"
            children = []

            @property
            def dirty(self):
                return next(values)

        class MockApp:
            version = "2025.33230"
            build = "2025.33230"

        class MockProject:
            name = "audiovisual-sampler-01.toe"

        MockProject.folder = str(folder)

        class MockTD:
            project = MockProject()
            app = MockApp()

            def op(self, path):
                return MockNode()

        return MockTD()

    def test_validates_authorized_project_path(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            workspace = Path(tmpdir) / "workspace"
            workspace.mkdir()
            out = Path(tmpdir) / "receipts"
            inspect_session(self._td(workspace, [False, False]), workspace=workspace, output_dir=out)
            receipts = list(out.glob("session-*.json"))
            self.assertEqual(len(receipts), 1)
            self.assertIn('"status": "complete"', receipts[0].read_text())

    def test_rejects_dirty_state_change(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            workspace = Path(tmpdir) / "workspace"
            workspace.mkdir()
            out = Path(tmpdir) / "receipts"
            with self.assertRaisesRegex(RuntimeError, "integrity failure"):
                inspect_session(self._td(workspace, [False, True]), workspace=workspace, output_dir=out)
            receipts = list(out.glob("session-*.json"))
            self.assertEqual(len(receipts), 1)
            self.assertIn('"status": "failed"', receipts[0].read_text())


if __name__ == "__main__":
    unittest.main()
