"""Identity, provenance, publication and reversible navigation acceptance tests."""

from copy import deepcopy
import importlib.util
import json
import os
import subprocess
from pathlib import Path
import unittest

TOOLS = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location("identity", TOOLS / "identity_contract.py")
identity = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(identity)
SPEC = importlib.util.spec_from_file_location("layout_identity", TOOLS / "workspace_layout.py")
layout = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(layout)


class IdentityContract(unittest.TestCase):
    def setUp(self):
        self.manifest = json.loads((TOOLS.parent / "workspace-manifest.json").read_text())

    def test_current_contract_and_original_project_identities(self):
        identity.validate_manifest(self.manifest)
        membership = json.loads((TOOLS.parent / self.manifest["membership_source"]).read_text())
        self.assertEqual({(p["id"], p["slug"]) for p in self.manifest["projects"]},
                         {(p["id"], p["slug"]) for p in membership["projects"]})
        self.assertEqual(len(self.manifest["projects"]), 15)

    def test_all_eight_domains_are_explicit_and_do_not_invent_artworks(self):
        registry = self.manifest["identity_registry"]
        self.assertEqual(set(registry) - {"schema_version"}, set(identity.COLLECTIONS))
        works = {a["project_id"] for a in registry["artworks"]}
        for project in self.manifest["projects"]:
            if project["profile"] in ("source-collection", "media-playback"):
                self.assertNotIn(project["id"], works)
        self.assertEqual(len(registry["editions"]), 1)
        edition = registry["editions"][0]
        self.assertEqual(edition["native_id"], "simvltanea-inaugural")
        self.assertEqual(edition["json_pointer"], "/editions/1")
        self.assertEqual(edition["publication_status"], "unverified")
        self.assertNotIn("version", edition)

    def test_duplicate_identity_rejected(self):
        registry = self.manifest["identity_registry"]
        registry["modules"][0]["id"] = registry["capabilities"][0]["id"]
        with self.assertRaisesRegex(ValueError, "Duplicate identity"):
            identity.validate_manifest(self.manifest)

    def test_unresolved_and_wrongly_typed_capability_rejected(self):
        for ref in ({"type": "capability", "id": "missing"},
                    {"type": "artwork", "id": "missing"}):
            with self.subTest(ref=ref):
                manifest = deepcopy(self.manifest)
                manifest["identity_registry"]["modules"][0]["capability_refs"] = [ref]
                with self.assertRaises(ValueError):
                    identity.validate_manifest(manifest)

    def test_new_private_repository_rejected(self):
        self.manifest["repositories"].append({"key": "secret", "github_id": 123456,
                                              "private": True, "full_name": "owner/secret"})
        with self.assertRaisesRegex(ValueError, "private repository"):
            identity.validate_manifest(self.manifest)

    def test_changed_private_binding_rejected(self):
        repo = next(r for r in self.manifest["repositories"] if r["private"])
        repo["local_path"] = "new-private-source"
        with self.assertRaisesRegex(ValueError, "frozen published baseline"):
            identity.validate_manifest(self.manifest)

    SHA = "0123456789abcdef0123456789abcdef01234567"

    def surface(self, files, baseline=None):
        identity.validate_public_surface(list(files), files.__getitem__, baseline or {}, self.manifest)

    def test_private_pointer_files_rejected(self):
        # Regression for closed PR 32: a hand-authored pointer to a private repository
        # bypassed the manifest-only publication checks (AGENTS.md forbids private bindings).
        for path in ("docs/private-pointers/study.md", "docs/private_pointer-x.md", "notes/Private-Pointers/a.md"):
            with self.assertRaisesRegex(ValueError, "private owner"):
                self.surface({"README.md": "", path: ""})

    def test_pointer_under_any_filename_rejected_by_content(self):
        named = "Private repository 4444J99/some-private-study, commit %s, assets/a.wav." % self.SHA
        bare = "Source lives in a private repository; pinned commit %s." % self.SHA
        plain = "Repository: time-moment-brief\nCommit: %s\nPath: assets/a.wav" % self.SHA
        for path in ("docs/source-provenance.md", "docs/private-source-pointer.md", "manifests/x.json", "NOTES.md",
                     "projects/time-moment-brief/source-provenance.md", "artworks/a/notes.txt",
                     "tools/source-provenance.md", ".github/source-provenance.md"):
            for text in (named, bare, plain):
                with self.assertRaisesRegex(ValueError, "private owner"):
                    self.surface({path: text})

    def test_baseline_document_is_frozen_by_content(self):
        old = "private repository 4444J99/old-owner at %s" % self.SHA
        base = {"README.md": identity.content_digest(old)}
        self.surface({"README.md": old}, base)
        for added in ("\nprivate repository 4444J99/new-owner",
                      "\nprivate pin fedcba9876543210fedcba9876543210fedcba98",
                      "\nrepository 4444J99/old-owner at %s asset media/unreviewed-take-42.wav" % self.SHA):
            with self.assertRaisesRegex(ValueError, "private owner"):
                self.surface({"README.md": old + added}, base)

    def test_private_origin_survives_public_continuation_with_same_basename(self):
        text = "origin https://github.com/organvm/the-thing-without-a-name.git at %s media/take.wav" % self.SHA
        with self.assertRaisesRegex(ValueError, "private owner"):
            self.surface({"docs/new-source-provenance.md": text})

    def test_public_navigation_slugs_are_not_source_names(self):
        self.surface({"docs/nav.md": "[engine](../repositories/deterministic-performance-engine/README.md) "
                                     "and synchronized-generation-playback"})

    def test_public_commit_url_is_not_a_private_pin(self):
        text = "private custody note; review at https://github.com/4444J99/hub-audiovisual-projects/commit/%s" % self.SHA
        self.surface({"docs/new-evidence.md": text})

    def test_public_names_aliases_and_public_remotes_allowed(self):
        for ref in ("4444J99/tool-audiovisual-postproduction/pull/1", "4444J99/hub-audiovisual-projects",
                    "https://github.com/4444J99/the-thing-without-a-name.git",
                    "4444J99/audiovisual-media-postproduction-system/pull/59", "4444J99/simvltanea/pull/32"):
            self.surface({"docs/new-note.md": "See %s" % ref})
        self.surface({"tools/x.py": "4444J99/anything %s private" % self.SHA})

    def test_tracked_files_contain_no_private_pointers(self):
        env = {k: v for k, v in os.environ.items() if not k.startswith("GIT_")}
        out = subprocess.run(["git", "ls-files", "-z"], cwd=TOOLS.parent, check=True, env=env,
                             capture_output=True, text=True).stdout
        tracked = [p for p in out.split("\0") if p]
        self.assertTrue(tracked)
        baseline = json.loads((TOOLS / "public_surface_baseline.json").read_text())["paths"]
        self.assertTrue(set(baseline) <= set(tracked))
        identity.validate_public_surface(
            tracked, lambda p: (TOOLS.parent / p).read_text(errors="replace"), baseline, self.manifest)

    def test_private_registry_source_rejected(self):
        source = self.manifest["identity_registry"]["source_media"][0]
        source["visibility"] = "restricted"
        with self.assertRaisesRegex(ValueError, "private owner"):
            identity.validate_manifest(self.manifest)

    def test_public_source_cannot_bind_private_or_unknown_provenance_owner(self):
        for owner in (1408128309, 987654321):
            with self.subTest(owner=owner):
                manifest = deepcopy(self.manifest)
                provenance = manifest["identity_registry"]["source_media"][0]["provenance"]
                provenance.update(repository_github_id=owner, record_path="private-intake/source-manifest.json")
                with self.assertRaisesRegex(ValueError, "public existing owner"):
                    identity.public_catalog(manifest)

    def test_public_module_cannot_bind_private_implementation(self):
        module = self.manifest["identity_registry"]["modules"][0]
        module["software_ref"] = {"type": "software_system", "id": "synchronized-generation-playback"}
        with self.assertRaisesRegex(ValueError, "Private module"):
            identity.validate_manifest(self.manifest)

    def test_unknown_metadata_cannot_escape_public_projection(self):
        software = self.manifest["identity_registry"]["software_systems"][0]
        software["private_source_manifest"] = "/Users/owner/private-source-catalog.json"
        with self.assertRaisesRegex(ValueError, "Unknown software_system fields"):
            identity.public_catalog(self.manifest)

    def test_nested_unknown_metadata_cannot_escape_public_projection(self):
        provenance = self.manifest["identity_registry"]["source_media"][0]["provenance"]
        provenance["private_source_manifest"] = "/Users/owner/private-source-catalog.json"
        with self.assertRaisesRegex(ValueError, "Unknown provenance"):
            identity.public_catalog(self.manifest)

    def test_known_fields_cannot_smuggle_nested_metadata(self):
        for collection, field, value in (
            ("software_systems", "responsibility", {"private_manifest": "/private/source"}),
            ("modules", "interfaces", [{"private_path": "/private/source"}]),
        ):
            with self.subTest(field=field):
                manifest = deepcopy(self.manifest)
                manifest["identity_registry"][collection][0][field] = value
                with self.assertRaises(ValueError):
                    identity.public_catalog(manifest)

    def test_registry_and_provenance_paths_cannot_escape(self):
        for field in ("path", "record_path"):
            manifest = deepcopy(self.manifest)
            target = (manifest["identity_registry"]["modules"][0] if field == "path" else
                      manifest["identity_registry"]["source_media"][0]["provenance"])
            target[field] = "../private/source"
            with self.subTest(field=field), self.assertRaisesRegex(ValueError, "Nonportable"):
                identity.validate_manifest(manifest)

    def test_public_projection_removes_private_owners_and_workstation_metadata(self):
        catalog = identity.public_catalog(self.manifest)
        text = json.dumps(catalog)
        for repo in self.manifest["repositories"]:
            if repo["private"]:
                self.assertNotIn(repo["full_name"], text)
        for key in ("local_path", "local_bindings", "page_url", "page_id", "configured_origin", "authority_state"):
            if key == "local_bindings":
                self.assertTrue(all(not p[key] for p in catalog["projects"]))
            else:
                self.assertNotIn('"' + key + '"', text)
        self.assertNotIn("the-thing-without-a-name", text)
        self.assertFalse(any(s["visibility"] == "restricted" for s in catalog["identity_registry"]["software_systems"]))
        self.assertEqual(identity.public_catalog(self.manifest), catalog)

    def test_visibility_observation_fail_closed(self):
        self.manifest["access"]["observed_visibility"] = "unknown"
        with self.assertRaisesRegex(ValueError, "access observation"):
            identity.public_catalog(self.manifest)

    def test_old_schema_cannot_bypass_publication_checks(self):
        self.manifest["schema_version"] = "2.0.0"
        with self.assertRaisesRegex(ValueError, "Unsupported"):
            identity.public_catalog(self.manifest)

    def test_canonical_and_compatibility_navigation_coexist(self):
        files = layout.rendered_files(self.manifest)
        self.assertIn("repositories/independent-loop-compositor/README.md", files)
        self.assertIn("repositories/simvltanea/README.md", files)
        self.assertIn("../independent-loop-compositor/README.md", files["repositories/simvltanea/README.md"])
        links = dict(layout.planned_links(self.manifest))
        for slug in ("simvltanea", "independent-loop-compositor"):
            self.assertEqual(links[layout.REPOSITORY / "repositories" / slug / "local/source"],
                             layout.REPOSITORY / "simvltanea")

    def test_compatibility_alias_collision_rejected(self):
        self.manifest["repositories"][0]["directory_slug"] = "simvltanea"
        with self.assertRaisesRegex(ValueError, "collides"):
            identity.validate_manifest(self.manifest)

    def test_edition_cannot_claim_another_artwork_or_private_provenance(self):
        edition = self.manifest["identity_registry"]["editions"][0]
        edition["artwork_ref"] = self.manifest["identity_registry"]["compositions"][0]["artwork_ref"]
        with self.assertRaisesRegex(ValueError, "same artwork"):
            identity.validate_manifest(self.manifest)

    def test_source_content_identity_and_original_name_are_preserved(self):
        sources = self.manifest["identity_registry"]["source_media"]
        source = next(s for s in sources if s["native_id"] == "SRC-002")
        self.assertEqual(source["label"], "edited-two-view-dialogue-recording")
        self.assertEqual(source["content_digest"], "sha256:bde1c7e0910941f8ca3bce06e8c2ddb3a31da4335b544fd041d84e97d1060225")
        self.assertEqual(source["provenance"]["original_name"], "2020 04 26   god's ears   second draft.mp4")
        source["content_digest"] = "sha256:unverified"
        with self.assertRaisesRegex(ValueError, "SHA-256"):
            identity.validate_manifest(self.manifest)


if __name__ == "__main__":
    unittest.main()
