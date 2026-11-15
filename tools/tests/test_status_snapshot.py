import copy
import importlib.util
import io
import json
import sys
from contextlib import redirect_stderr, redirect_stdout
from pathlib import Path
import tempfile
import unittest

TOOLS = Path(__file__).resolve().parents[1]
ROOT = TOOLS.parent


if str(TOOLS) not in sys.path:
    sys.path.insert(0, str(TOOLS))


def load(name):
    spec = importlib.util.spec_from_file_location(name, TOOLS / (name + ".py"))
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


status = load("status_snapshot")
identity = load("identity_contract")


def manifest():
    return {"repositories": [
        {"key": "alpha", "full_name": "4444J" "99/alpha-public", "private": False},
        {"key": "hidden-alias", "full_name": "4444J" "99/hidden-thing", "private": True},
        {"key": "named-alias", "full_name": "4444J" "99/named-thing", "private": True, "status_listing": "name-only"},
    ]}


def sha(n):
    return ("%x" % n).ljust(status.SHA_LEN, "0")


def run(workflow, run_id, steps, conclusion="success", state="completed", head=1, current=True):
    return {"workflow": workflow, "run_id": run_id, "event": "push", "status": state, "conclusion": conclusion,
            "created_at": "2026-11-15T12:00:00Z", "head_sha": sha(head), "on_current_head": current, "jobs": 1,
            "executed_steps": steps, "verdict": status.verdict(state, conclusion, steps)}


def snapshot():
    repo = {
        "full_name": "4444J" "99/alpha-public", "listing": "full", "visibility_live": "public", "default_branch": "main",
        "main": {"sha": sha(1), "title": "head", "committed_at": "2026-11-15T10:00:00Z", "pr": 12, "resolved": True},
        "merged_prs": [
            {"number": 11, "title": "Pipe | and `tick` <b>", "merged_at": "2026-11-14T10:00:00Z",
             "merge_sha": sha(2), "head_sha": sha(3), "resolved": True},
            {"number": 12, "title": "Second", "merged_at": "2026-11-15T10:00:00Z",
             "merge_sha": sha(1), "head_sha": sha(4), "resolved": True}],
        "open_prs": [{"number": 13, "title": "Open one", "draft": True, "head_sha": sha(5),
                      "updated_at": "2026-11-15T11:00:00Z", "resolved": True}],
        "ci": [run("Verify", 100, 9), run("Dead", 101, 0, conclusion="failure"), run("Wait", 102, 3, conclusion=None, state="in_progress")],
        "red_at_merge": [
            {"pr": 11, "head_sha": sha(3), "check": "test", "state": "red", "conclusion": "failure", "run_id": 55,
             "executed_steps": 7, "merged_at": "2026-11-14T10:00:00Z"},
            {"pr": 12, "head_sha": sha(4), "check": "startup", "state": "cannot-start", "conclusion": "failure",
             "run_id": 56, "executed_steps": 0, "merged_at": "2026-11-15T10:00:00Z"}],
        "issues_open_count": 2,
        "issues_updated": [{"number": 7, "title": "An issue", "state": "closed", "updated_at": "2026-11-15T09:00:00Z"}],
    }
    return {"schema": 1, "date": "2026-11-15", "since": "2026-11-13", "started_at": "2026-11-15T15:50:00Z",
            "captured_at": "2026-11-15T16:00:00Z", "repositories": [repo], "name_only": ["named-thing"], "omitted_count": 1}


class VerdictTests(unittest.TestCase):
    def test_zero_executed_steps_is_never_a_pass(self):
        self.assertEqual(status.verdict("completed", "failure", 0), "cannot-start")
        self.assertEqual(status.verdict("completed", "success", 0), "no-steps")
        self.assertEqual(status.verdict("completed", "skipped", 0), "skipped")
        self.assertEqual(status.verdict("completed", "cancelled", 0), "cancelled")
        for conclusion in ("success", "failure", "cancelled", None):
            self.assertNotEqual(status.verdict("completed", conclusion, 0), "pass")

    def test_executed_step_verdicts(self):
        self.assertEqual(status.verdict("completed", "success", 4), "pass")
        self.assertEqual(status.verdict("completed", "failure", 4), "red")
        self.assertEqual(status.verdict("completed", "cancelled", 1), "cancelled")
        self.assertEqual(status.verdict("in_progress", None, 9), "pending")

    def test_bookkeeping_steps_do_not_make_a_hollow_job_look_executed(self):
        hollow = [{"name": "Set up job", "status": "completed", "conclusion": "success"},
                  {"name": "Run tests", "status": "completed", "conclusion": "skipped"},
                  {"name": "Post Run checkout", "status": "completed", "conclusion": "success"},
                  {"name": "Complete job", "status": "completed", "conclusion": "success"}]
        self.assertEqual(status.count_executed(hollow), 0)
        self.assertEqual(status.verdict("completed", "success", status.count_executed(hollow)), "no-steps")
        died = [{"name": "Set up job", "status": "completed", "conclusion": "failure"}]
        self.assertEqual(status.verdict("completed", "failure", status.count_executed(died)), "cannot-start")
        real = hollow + [{"name": "Run lint", "status": "completed", "conclusion": "success"}]
        self.assertEqual(status.count_executed(real), 1)

    def test_count_executed_ignores_skipped_and_unfinished(self):
        steps = [{"status": "completed", "conclusion": "success"}, {"status": "completed", "conclusion": "skipped"},
                 {"status": "in_progress", "conclusion": None}, {"status": "completed", "conclusion": "failure"}]
        self.assertEqual(status.count_executed(steps), 2)
        self.assertEqual(status.count_executed(None), 0)

    def test_check_classification_at_merge(self):
        base = {"status": "completed", "completed_at": "2026-11-14T09:00:00Z", "conclusion": "failure"}
        merged = "2026-11-14T10:00:00Z"
        self.assertEqual(status.classify_check(base, merged, 5), "red")
        self.assertEqual(status.classify_check(base, merged, 0), "cannot-start")
        self.assertEqual(status.classify_check({**base, "conclusion": "success"}, merged, 5), None)
        self.assertEqual(status.classify_check({**base, "completed_at": "2026-11-14T11:00:00Z"}, merged, 5), "late")
        self.assertEqual(status.classify_check({**base, "completed_at": "2026-11-14T11:00:00Z", "conclusion": "success"},
                                                merged, 5), "late")
        self.assertEqual(status.classify_check({"status": "in_progress"}, merged, None), "pending")
        self.assertEqual(status.classify_check({**base, "conclusion": "cancelled"}, merged, 2), "cancelled")


class RenderTests(unittest.TestCase):
    def test_rendering_is_deterministic(self):
        self.assertEqual(status.render(snapshot(), manifest()), status.render(copy.deepcopy(snapshot()), manifest()))

    def test_page_content(self):
        page = status.render(snapshot(), manifest())
        self.assertIn("generated, not hand-written", page)
        self.assertIn("| [#11](https://github.com/4444J" "99/alpha-public/pull/11) | Pipe \\| and \\`tick\\` &lt;b&gt;", page)
        self.assertIn("`%s`" % sha(2)[:7], page)
        self.assertNotIn(sha(2), page)
        self.assertIn("**cannot-start**", page)
        self.assertIn("**pending**", page)
        self.assertIn("**red** | failure | [55]", page)
        self.assertIn("**cannot-start** | failure | [56]", page)
        self.assertIn("`named-thing`", page)
        self.assertNotIn("hidden-thing", page)
        self.assertIn("1 manifest repositories are omitted", page)

    def test_zero_step_run_row_never_says_pass(self):
        page = status.render(snapshot(), manifest())
        dead = [line for line in page.splitlines() if "| Dead |" in line][0]
        self.assertIn("**cannot-start**", dead)
        self.assertNotIn("**pass**", dead)

    def test_older_head_is_marked(self):
        snap = snapshot()
        snap["repositories"][0]["ci"][0] = run("Verify", 100, 9, head=9, current=False)
        page = status.render(snap, manifest())
        self.assertNotIn("| Verify |", page)
        self.assertIn("**alpha-public** — latest `main` run of 1 workflow(s) is on an older head", page)
        self.assertIn("Verify ([100](https://github.com/4444J" "99/alpha-public/actions/runs/100), `9000000`, pass)", page)

    def test_none_red_statement(self):
        snap = snapshot()
        snap["repositories"][0]["red_at_merge"] = []
        self.assertIn("No merged pull request in this window had a red", status.render(snap, manifest()))
        self.assertIn("read between 2026-11-15T15:50:00Z and 2026-11-15T16:00:00Z", status.render(snap, manifest()))

    def test_collector_redaction_and_renderer_gate_for_restricted_names(self):
        self.assertEqual(status.redact("Wire hidden-thing into ORG/hidden-thing", {"hidden-thing"}),
                         "Wire (restricted repository) into ORG/(restricted repository)")
        self.assertEqual(status.redact("ok  text", set()), "ok text")
        snap = snapshot()
        snap["repositories"][0]["merged_prs"][0]["title"] = "Wire hidden-thing"
        with self.assertRaises(status.StatusError):
            status.render(snap, manifest())

    def test_markdown_metacharacters_are_escaped(self):
        self.assertEqual(status.clean("a & b <i> @user *x* _y_ #1 ~z~ [l](u) |"),
                         "a &amp; b &lt;i&gt; &#64;user \\*x\\* \\_y\\_ \\#1 \\~z\\~ \\[l\\](u) \\|")

    def test_full_pin_in_a_title_is_shortened(self):
        snap = snapshot()
        snap["repositories"][0]["merged_prs"][0]["title"] = "Revert " + "ab" * 20
        page = status.render(snap, manifest())
        self.assertNotIn("ab" * 20, page)

    def test_name_only_listing_follows_the_snapshot_and_manifest_marks(self):
        snap = snapshot()
        snap["name_only"] = []
        self.assertNotIn("named-thing", status.render(snap, manifest()))
        self.assertIn("named-thing", status.render(snapshot(), manifest()))
        unmarked = manifest()
        del unmarked["repositories"][2]["status_listing"]
        with self.assertRaises(status.StatusError):
            status.render(snapshot(), unmarked)


class NameOnlyTests(unittest.TestCase):
    def test_exemption_is_opt_in_and_names_only_the_marked_repository(self):
        m = manifest()
        self.assertIn("named-thing", identity.private_repository_names(m))
        self.assertNotIn("named-thing", identity.private_repository_names(m, allow_listed=True))
        self.assertNotIn("4444J" "99/named-thing", identity.private_qualified_origins(m, allow_listed=True))
        self.assertIn("hidden-thing", identity.private_repository_names(m, allow_listed=True))
        self.assertIn("4444J" "99/hidden-thing", identity.private_qualified_origins(m, allow_listed=True))

    def test_only_generated_status_pages_may_name_a_marked_repository(self):
        m = manifest()
        read = lambda p: identity.GENERATED_STATUS_MARKER + " -->\nsee named-thing"  # noqa: E731
        identity.validate_public_surface(["docs/status/2026-11-15.md", "docs/status/2026-11-15.snapshot.json"], read, {}, m)
        with self.assertRaises(ValueError):
            identity.validate_public_surface(["docs/other.md"], read, {}, m)
        with self.assertRaises(ValueError):
            identity.validate_public_surface(["docs/status/x.md"], lambda p: "see hidden-thing", {}, m)

    def test_exemption_requires_the_generated_marker(self):
        m = manifest()
        marked = identity.GENERATED_STATUS_MARKER + " -->\nsee named-thing"
        both = ["docs/status/a.md", "docs/status/a.snapshot.json"]
        identity.validate_public_surface(both, lambda p: marked, {}, m)
        with self.assertRaises(ValueError):
            identity.validate_public_surface(["docs/status/a.md"], lambda p: marked, {}, m)  # no snapshot beside it
        with self.assertRaises(ValueError):
            identity.validate_public_surface(both, lambda p: "see named-thing", {}, m)
        with self.assertRaises(ValueError):
            identity.validate_public_surface(["docs/status/a.json"], lambda p: marked, {}, m)

    def test_name_only_exemption_does_not_cover_paths_or_owner_qualified_references(self):
        m = manifest()
        both = ["docs/status/a.md", "docs/status/a.snapshot.json"]
        for text in ("see named-thing/src/internal.py", "see 4444J" "99/named-thing", "see x/named-thing here",
                     "path named-thing\\src", "named-thing:src/x.py", "named-thing@abc", "pin " + "a" * 40):
            with self.subTest(text=text):
                files = {both[0]: identity.GENERATED_STATUS_MARKER + " -->\n" + text, both[1]: "{}"}
                with self.assertRaises(ValueError):
                    identity.validate_public_surface(both, files.get, {}, m)
        files = {both[0]: identity.GENERATED_STATUS_MARKER + " -->\nlisted `named-thing` only", both[1]: "{}"}
        identity.validate_public_surface(both, files.get, {}, m)

    def test_renderer_refuses_a_path_built_on_a_name_only_repository(self):
        snap = snapshot()
        snap["repositories"][0]["merged_prs"][0]["title"] = "fix named-thing/src/internal.py"
        with self.assertRaises(status.StatusError):
            status.render(snap, manifest())

    def test_red_at_merge_state_must_match_its_conclusion(self):
        snap = snapshot()
        snap["repositories"][0]["red_at_merge"][1].update(state="no-steps")  # a failure cannot be a hollow pass
        with self.assertRaises(status.StatusError):
            status.render(snap, manifest())
        snap = snapshot()
        snap["repositories"][0]["red_at_merge"][0].update(conclusion="success")  # a success cannot be red
        with self.assertRaises(status.StatusError):
            status.render(snap, manifest())

    def test_snapshot_beside_a_generated_page_is_exempt_but_a_lone_one_is_not(self):
        m = manifest()
        page = identity.GENERATED_STATUS_MARKER + " -->\npage"
        files = {"docs/status/a.md": page, "docs/status/a.snapshot.json": '{"name_only": ["named-thing"]}',
                 "docs/status/b.snapshot.json": '{"name_only": ["named-thing"]}'}
        identity.validate_public_surface(["docs/status/a.md", "docs/status/a.snapshot.json"], files.get, {}, m)
        with self.assertRaises(ValueError):
            identity.validate_public_surface(["docs/status/b.snapshot.json"], files.get, {}, m)

    def test_exemption_covers_the_bare_name_not_the_aliases_or_origin(self):
        m = manifest()
        m["repositories"][2]["local_path"] = "named-local"
        m["repositories"][2]["configured_origin"] = "https://example.invalid/x/named-origin.git"
        names = identity.private_repository_names(m, allow_listed=True)
        self.assertNotIn("named-thing", names)
        self.assertTrue({"named-alias", "named-local", "named-origin"} <= names)
        self.assertIn("x/named-origin", identity.private_qualified_origins(m, allow_listed=True))

    def test_mark_on_a_public_repository_is_rejected(self):
        real = json.loads((ROOT / "workspace-manifest.json").read_text(encoding="utf-8"))
        next(r for r in real["repositories"] if not r["private"])["status_listing"] = "name-only"
        with self.assertRaises(ValueError):
            identity.validate_manifest(real)

    def test_mark_is_accepted_by_the_real_manifest_contract_and_bad_values_are_not(self):
        real = json.loads((ROOT / "workspace-manifest.json").read_text(encoding="utf-8"))
        identity.validate_manifest(real)
        marked = copy.deepcopy(real)
        next(r for r in marked["repositories"] if r["private"])["status_listing"] = "name-only"
        identity.validate_manifest(marked)
        marked_bad = copy.deepcopy(real)
        next(r for r in marked_bad["repositories"] if r["private"])["status_listing"] = "full"
        with self.assertRaises(ValueError):
            identity.validate_manifest(marked_bad)


class RefusalTests(unittest.TestCase):
    def assertRefused(self, mutate):
        snap = snapshot()
        mutate(snap)
        with self.assertRaises(status.StatusError):
            status.render(snap, manifest())

    def test_unresolved_citations_are_refused(self):
        repo = lambda s: s["repositories"][0]  # noqa: E731
        self.assertRefused(lambda s: repo(s)["merged_prs"][0].update(resolved=False))
        self.assertRefused(lambda s: repo(s)["merged_prs"][0].pop("resolved"))
        self.assertRefused(lambda s: repo(s)["merged_prs"][0].update(merge_sha=None))
        self.assertRefused(lambda s: repo(s)["merged_prs"][0].update(merge_sha="nothex000000"))
        self.assertRefused(lambda s: repo(s)["merged_prs"][0].update(merge_sha="abc"))
        self.assertRefused(lambda s: repo(s)["merged_prs"][0].update(number=0))
        self.assertRefused(lambda s: repo(s)["merged_prs"][0].update(number=True))
        self.assertRefused(lambda s: repo(s)["main"].update(resolved=False))
        self.assertRefused(lambda s: repo(s)["main"].update(pr="12"))
        self.assertRefused(lambda s: repo(s)["open_prs"][0].update(resolved=False))
        self.assertRefused(lambda s: repo(s)["red_at_merge"][0].update(pr=99))
        self.assertRefused(lambda s: repo(s)["red_at_merge"][0].update(state="weird"))

    def test_non_public_listing_is_refused(self):
        repo = lambda s: s["repositories"][0]  # noqa: E731
        self.assertRefused(lambda s: repo(s).update(visibility_live="private"))
        self.assertRefused(lambda s: repo(s).update(listing="name-only"))

    def test_head_flag_cannot_contradict_heads(self):
        def lie(s):
            s["repositories"][0]["ci"][0]["on_current_head"] = False
        self.assertRefused(lie)

    def test_red_at_merge_must_match_the_cited_pull_request(self):
        repo = lambda s: s["repositories"][0]  # noqa: E731
        self.assertRefused(lambda s: repo(s)["red_at_merge"][0].update(head_sha=sha(9)))
        self.assertRefused(lambda s: repo(s)["red_at_merge"][0].update(merged_at="2020-01-01T00:00:00Z"))
        self.assertRefused(lambda s: repo(s)["red_at_merge"][0].update(run_id="55"))

    def test_malformed_fields_refuse_instead_of_crashing(self):
        repo = lambda s: s["repositories"][0]  # noqa: E731
        self.assertRefused(lambda s: repo(s)["ci"][0].update(run_id="100"))
        self.assertRefused(lambda s: repo(s)["ci"][0].update(status=None))
        self.assertRefused(lambda s: s.update(name_only=[5]))
        self.assertRefused(lambda s: s.update(omitted_count="1"))
        self.assertRefused(lambda s: s.pop("captured_at"))

    def test_run_verdict_cannot_contradict_steps(self):
        def lie(s):
            s["repositories"][0]["ci"][1]["verdict"] = "pass"
        self.assertRefused(lie)

    def test_bad_schema_and_dates(self):
        self.assertRefused(lambda s: s.update(schema=2))
        self.assertRefused(lambda s: s.update(date="Nov 15"))
        self.assertRefused(lambda s: s.update(repositories=[]))

    def test_markdown_escaping_cannot_hide_a_restricted_name(self):
        m = manifest()
        m["repositories"][1]["full_name"] = "4444J" "99/hid_den-thing"
        snap = snapshot()
        snap["repositories"][0]["ci"][0]["workflow"] = "deploy hid_den-thing"
        with self.assertRaises(status.StatusError):
            status.render(snap, m)

    def test_red_state_must_match_its_step_count(self):
        snap = snapshot()
        snap["repositories"][0]["red_at_merge"][0].update(state="red", executed_steps=0)
        with self.assertRaises(status.StatusError):
            status.render(snap, manifest())
        snap = snapshot()
        snap["repositories"][0]["red_at_merge"][1].update(state="cannot-start", executed_steps=3)
        with self.assertRaises(status.StatusError):
            status.render(snap, manifest())
        snap = snapshot()
        snap["repositories"][0]["red_at_merge"][0].update(executed_steps="7")
        with self.assertRaises(status.StatusError):
            status.render(snap, manifest())

    def test_name_only_entries_must_be_owner_slash_name(self):
        snap = snapshot()
        snap["name_only"] = ["x`y", "o/r"]
        with self.assertRaises(status.StatusError):
            status.render(snap, manifest())

    def test_page_naming_a_restricted_repository_is_refused(self):
        with self.assertRaises(status.StatusError):
            status._gate_surface("see 4444J" "99/hidden-thing", manifest())
        with self.assertRaises(status.StatusError):
            status._gate_surface("hidden-thing is private " + "a" * 40, manifest())


class TrackingTests(unittest.TestCase):
    def test_tracked_repositories_follow_the_manifest_marks(self):
        full, name_only, omitted = status.tracked_repositories(manifest())
        self.assertEqual(full, [status.HUB, "4444J" "99/alpha-public"])
        self.assertEqual(name_only, ["4444J" "99/named-thing"])
        self.assertEqual(omitted, 1)


class FakeGh:
    """Answers the gh calls collect_repo makes from fixed data and records every call."""

    def __init__(self, private=False, bad_merge=False, truncate=False, empty_message=False, many_checks=False,
                 many_jobs=False, head_moves=False, other_base=False, job404=False, job_other_error=False):
        self.job_other_error = job_other_error
        self.other_base = other_base
        self.job404 = job404
        self.head_moves = head_moves
        self.head_reads = 0
        self.empty_message = empty_message
        self.many_checks = many_checks
        self.many_jobs = many_jobs
        self.calls = []
        self.private = private
        self.bad_merge = bad_merge
        self.truncate = truncate

    def __call__(self, *args):
        self.calls.append(args)
        text = " ".join(args)
        full = lambda n: sha(n) + "e" * 28  # noqa: E731
        if args[:1] == ("api",):
            path = args[-1]
            if "--slurp" in args:
                page = self(*[a for a in args if a not in ("--paginate", "--slurp")])
                return [page]
            if path == "repos/o/r":
                return {"private": self.private, "visibility": "private" if self.private else "public", "default_branch": "main"}
            if path == "repos/o/r/commits/main":
                self.head_reads += 1
                return {"sha": full(77 if self.head_moves and self.head_reads > 1 else 1), "commit": {"message": "" if self.empty_message else "head subject\n\nbody", "committer": {"date": "2026-11-15T10:00:00Z"}}}
            if path == "repos/o/r/commits/%s/pulls" % full(1):
                return [{"number": 12, "merged_at": "2026-11-15T10:00:00Z", "merge_commit_sha": full(1)}]
            if path.startswith("repos/o/r/compare/"):
                return {"status": "diverged" if self.bad_merge else "ahead"}
            if path.startswith("repos/o/r/actions/runs?"):
                return {"workflow_runs": [
                    {"id": 100, "workflow_id": 1, "name": "Verify", "status": "completed", "conclusion": "success", "event": "push",
                     "created_at": "2026-11-15T12:00:00Z", "head_sha": full(1)},
                    {"id": 90, "workflow_id": 1, "name": "Verify", "status": "completed", "conclusion": "failure", "event": "push",
                     "created_at": "2026-11-14T12:00:00Z", "head_sha": full(9)},
                    {"id": 101, "workflow_id": 2, "name": "Dead", "status": "completed", "conclusion": "failure",
                     "event": "push", "created_at": "2026-11-15T12:30:00Z", "head_sha": full(1)},
                    {"id": 102, "workflow_id": 3, "name": "Verify", "status": "completed", "conclusion": "cancelled",
                     "event": "push", "created_at": "2026-11-15T12:40:00Z", "head_sha": full(1)}]}
            if path == "repos/o/r/actions/runs/100/jobs?per_page=100":
                return {"jobs": [{"steps": [{"status": "completed", "conclusion": "success"},
                                             {"status": "completed", "conclusion": "skipped"}]}]}
            if path == "repos/o/r/actions/runs/101/jobs?per_page=100":
                return {"jobs": [{"steps": []}]}
            if path == "repos/o/r/actions/runs/102/jobs?per_page=100":
                return {"jobs": [{"steps": []}], "total_count": 2 if self.many_jobs else 1}
            if path == "repos/o/r/commits/%s/check-runs?per_page=100" % full(4):
                return {"total_count": 101 if self.many_checks else 7, "check_runs": [
                    {"id": 1, "name": "test", "status": "completed", "conclusion": "failure",
                     "completed_at": "2026-11-15T09:00:00Z", "details_url": "https://github.com/o/r/actions/runs/55/job/66"},
                    {"id": 2, "name": "startup", "status": "completed", "conclusion": "failure",
                     "completed_at": "2026-11-15T09:00:00Z", "details_url": "https://github.com/o/r/actions/runs/56/job/67"},
                    {"id": 3, "name": "pages", "status": "completed", "conclusion": "failure",
                     "completed_at": "2026-11-15T09:00:00Z", "details_url": "https://pages.example/build"},
                    {"id": 7, "name": "hollow", "status": "completed", "conclusion": "success",
                     "completed_at": "2026-11-15T09:00:00Z", "details_url": "https://github.com/o/r/actions/runs/60/job/71"},
                    {"id": 6, "name": "slow", "status": "completed", "conclusion": "success",
                     "completed_at": "2026-11-15T10:30:00Z", "details_url": "https://github.com/o/r/actions/runs/59/job/70"},
                    {"id": 4, "name": "late", "status": "in_progress", "conclusion": None, "completed_at": None,
                     "details_url": "https://github.com/o/r/actions/runs/57/job/68"},
                    {"id": 5, "name": "ok", "status": "completed", "conclusion": "success",
                     "completed_at": "2026-11-15T09:00:00Z", "details_url": "https://github.com/o/r/actions/runs/58/job/69"}]}
            if path == "repos/o/r/actions/jobs/66":
                if self.job404:
                    raise status.NotFound("gh api repos/o/r/actions/jobs failed: HTTP 404 Not Found")
                if self.job_other_error:
                    raise status.StatusError("gh api repos/o/r/actions/jobs/66404 failed: HTTP 403 rate limited")
                return {"steps": [{"status": "completed", "conclusion": "success"}, {"status": "completed", "conclusion": "failure"}]}
            if path.startswith("repos/o/r/commits/") and "/status?" in path:
                return {"total_count": 4, "statuses": [
                    {"id": 1, "context": "ci/legacy-red", "state": "failure", "updated_at": "2026-11-15T09:00:00Z"},
                    {"id": 2, "context": "ci/legacy-ok", "state": "success", "updated_at": "2026-11-15T09:00:00Z"},
                    {"id": 3, "context": "ci/legacy-late", "state": "success", "updated_at": "2026-11-15T11:00:00Z"},
                    {"id": 4, "context": "ci/legacy-wait", "state": "pending", "updated_at": "2026-11-15T09:00:00Z"}]}
            if path == "repos/o/r/actions/jobs/67":
                return {"steps": []}
            if path == "repos/o/r/actions/jobs/69":
                return {"steps": [{"name": "Run ok", "status": "completed", "conclusion": "success"}]}
            if path == "repos/o/r/actions/jobs/70":
                return {"steps": [{"name": "Run slow", "status": "completed", "conclusion": "success"}]}
            if path == "repos/o/r/actions/jobs/71":
                return {"steps": [{"name": "Set up job", "status": "completed", "conclusion": "success"},
                                  {"name": "Run all", "status": "completed", "conclusion": "skipped"}]}
        if args[:2] == ("pr", "list"):
            if "merged" in args:
                count = status.LIST_LIMIT if self.truncate else 1
                base = {"number": 12, "title": "Second", "mergedAt": "2026-11-15T10:00:00Z",
                        "mergeCommit": {"oid": full(1)}, "headRefOid": full(4), "baseRefName": "main"}
                if self.other_base:
                    return [base, dict(base, number=14, baseRefName="feature")]
                return [dict(base, number=12 + i) for i in range(count)] if self.truncate else [base]
            return [{"number": 13, "title": "Open one", "isDraft": False, "headRefOid": full(5),
                     "updatedAt": "2026-11-15T11:00:00Z", "baseRefName": "main"}]
        if args[:2] == ("issue", "list"):
            if "open" in args:
                return [{"number": 1}, {"number": 2}]
            return [{"number": 7, "title": "An issue", "state": "CLOSED", "updatedAt": "2026-11-15T09:00:00Z"}]
        raise AssertionError("unexpected gh call: " + text)


class CollectTests(unittest.TestCase):
    def test_collects_resolved_state(self):
        gh = FakeGh()
        repo = status.collect_repo(gh, "o/r", "2026-11-13")
        self.assertEqual(repo["main"], {"sha": sha(1), "title": "head subject", "committed_at": "2026-11-15T10:00:00Z",
                                        "pr": 12, "resolved": True})
        self.assertEqual(repo["merged_prs"][0]["merge_sha"], sha(1))
        self.assertTrue(all(len(p["merge_sha"]) == status.SHA_LEN for p in repo["merged_prs"]))
        ci = {r["workflow"]: r for r in repo["ci"] if r["workflow_id"] != 3}
        self.assertEqual(ci["Verify"]["run_id"], 100)
        self.assertEqual(ci["Verify"]["executed_steps"], 1)
        self.assertEqual(ci["Verify"]["verdict"], "pass")
        self.assertTrue(ci["Verify"]["on_current_head"])
        self.assertEqual(ci["Dead"]["verdict"], "cannot-start")
        by_id = {r["workflow_id"]: r for r in repo["ci"]}
        self.assertEqual(len(repo["ci"]), 3, "workflows sharing a display name stay separate")
        self.assertEqual(by_id[3]["verdict"], "cancelled")
        self.assertTrue([c for c in gh.calls if c[-1].endswith("/jobs/71")], "successful checks are read for hollow passes")
        states = {e["check"]: (e["state"], e["executed_steps"], e["run_id"]) for e in repo["red_at_merge"]
                  if not e["check"].startswith("ci/")}
        self.assertEqual(states, {"test": ("red", 2, 55), "startup": ("cannot-start", 0, 56),
                                  "pages": ("red", None, None), "late": ("pending", None, 57),
                                  "slow": ("late", 1, 59), "hollow": ("no-steps", 0, 60)})
        self.assertEqual(repo["issues_open_count"], 2)
        self.assertEqual(repo["issues_updated"][0]["state"], "closed")
        status.validate_snapshot({"schema": 1, "date": "2026-11-15", "since": "2026-11-13", "started_at": "w", "captured_at": "x",
                                  "repositories": [repo], "name_only": [], "omitted_count": 0})

    def test_unresolvable_merge_commit_is_refused(self):
        with self.assertRaises(status.StatusError):
            status.collect_repo(FakeGh(bad_merge=True), "o/r", "2026-11-13")

    def test_repository_that_is_not_public_stops_the_run(self):
        with self.assertRaises(status.StatusError):
            status.collect_repo(FakeGh(private=True), "o/r", "2026-11-13")

    def test_restricted_names_are_redacted_from_workflow_and_check_names(self):
        repo = status.collect_repo(FakeGh(), "o/r", "2026-11-13", restricted={"startup", "Dead"})
        self.assertIn("(restricted repository)", [r["workflow"] for r in repo["ci"]])
        self.assertIn("(restricted repository)", [e["check"] for e in repo["red_at_merge"]])

    def test_fork_pull_request_runs_named_main_are_not_default_branch_ci(self):
        class Fork(FakeGh):
            def __call__(self, *args):
                out = super().__call__(*args)
                if args[-1].startswith("repos/o/r/actions/runs?") and "--slurp" not in args:
                    out["workflow_runs"].append({"id": 999, "workflow_id": 1, "name": "Verify", "status": "completed",
                                                 "conclusion": "failure", "event": "pull_request", "head_sha": sha(55) + "e" * 28,
                                                 "created_at": "2026-11-15T23:00:00Z"})
                return out
        repo = status.collect_repo(Fork(), "o/r", "2026-11-13")
        self.assertNotIn(999, [r["run_id"] for r in repo["ci"]])
        self.assertEqual({r["workflow_id"]: r["run_id"] for r in repo["ci"]}[1], 100)

    def test_legacy_commit_statuses_are_read_for_red_at_merge(self):
        repo = status.collect_repo(FakeGh(), "o/r", "2026-11-13")
        got = {e["check"]: (e["state"], e["conclusion"]) for e in repo["red_at_merge"]}
        self.assertEqual(got["ci/legacy-red"], ("red", "failure"))
        self.assertEqual(got["ci/legacy-late"], ("late", "success"))
        self.assertEqual(got["ci/legacy-wait"], ("pending", "pending"))
        self.assertNotIn("ci/legacy-ok", got)

    def test_restricted_name_fused_into_a_longer_token_is_redacted_and_gated(self):
        self.assertEqual(status.redact("sync-hidden-thing_v2 x.hidden-thing", {"hidden-thing"}),
                         "sync-(restricted repository)_v2 x.(restricted repository)")
        snap = snapshot()
        snap["repositories"][0]["merged_prs"][0]["title"] = "sync-hidden-thing outputs"
        with self.assertRaises(status.StatusError):
            status.render(snap, manifest())

    def test_full_entry_must_be_a_public_repository_of_the_manifest(self):
        snap = snapshot()
        snap["repositories"][0]["full_name"] = "4444J" "99/named-thing"
        with self.assertRaises(status.StatusError):
            status.render(snap, manifest())

    def test_snapshot_fields_the_page_does_not_print_are_gated_too(self):
        snap = snapshot()
        snap["repositories"][0]["main"]["title"] = "mentions hidden-thing"
        with self.assertRaises(status.StatusError):
            status.render(snap, manifest())

    def test_pull_requests_merged_into_other_branches_are_counted_not_hidden(self):
        repo = status.collect_repo(FakeGh(other_base=True), "o/r", "2026-11-13")
        self.assertEqual((len(repo["merged_prs"]), repo["merged_other_base"]), (1, 1))
        snap = snapshot()
        snap["repositories"][0]["merged_other_base"] = 2
        snap["repositories"][0]["merged_prs"] = []
        snap["repositories"][0]["red_at_merge"] = []
        self.assertIn("2 pull request(s) merged into a branch other than `main`", status.render(snap, manifest()))

    def test_expired_job_degrades_to_not_observed_but_other_errors_abort(self):
        repo = status.collect_repo(FakeGh(job404=True), "o/r", "2026-11-13")
        test = [e for e in repo["red_at_merge"] if e["check"] == "test"][0]
        self.assertEqual((test["state"], test["executed_steps"]), ("red", None))

    def test_only_a_real_404_degrades_and_foreign_urls_are_not_followed(self):
        with self.assertRaises(status.StatusError):
            status.collect_repo(FakeGh(job_other_error=True), "o/r", "2026-11-13")

        class Foreign(FakeGh):
            def __call__(self, *args):
                out = super().__call__(*args)
                if "--slurp" not in args and args[-1].startswith("repos/o/r/commits/") and "check-runs" in args[-1]:
                    out["check_runs"][0]["details_url"] = "https://github.com/other/repo/actions/runs/55/job/66"
                return out
        repo = status.collect_repo(Foreign(), "o/r", "2026-11-13")
        test = [e for e in repo["red_at_merge"] if e["check"] == "test"][0]
        self.assertEqual((test["run_id"], test["executed_steps"]), (None, None))

    def test_other_base_note_is_shown_beside_a_table_too(self):
        snap = snapshot()
        snap["repositories"][0]["merged_other_base"] = 3
        self.assertIn("3 pull request(s) merged into a branch other than `main` in this window are not listed.",
                      status.render(snap, manifest()))

    def test_container_bookkeeping_steps_are_not_work(self):
        steps = [{"name": "Initialize containers", "status": "completed", "conclusion": "success"},
                 {"name": "Stop containers", "status": "completed", "conclusion": "success"}]
        self.assertEqual(status.count_executed(steps), 0)
        self.assertEqual(status.count_executed([{"name": "Post coverage comment", "status": "completed",
                                                  "conclusion": "success"}]), 1)

    def test_short_restricted_names_are_matched_on_word_boundaries_only(self):
        self.assertEqual(status.redact("Inside abc x", {"abc"}), "Inside (restricted repository) x")
        self.assertEqual(status.redact("abcdef", {"abc"}), "abcdef")

    def test_dates_must_be_real_and_ordered(self):
        for bad in ("2026-13-45", "2026-02-30", "Nov 15", None):
            self.assertFalse(status.real_date(bad))
        self.assertTrue(status.real_date("2026-11-15"))
        snap = snapshot()
        snap["since"] = "2026-11-20"
        with self.assertRaises(status.StatusError):
            status.render(snap, manifest())

    def test_name_only_list_must_be_marked_in_the_manifest(self):
        snap = snapshot()
        snap["name_only"] = ["hidden-thing"]
        with self.assertRaises(status.StatusError):
            status.render(snap, manifest())

    def test_head_pull_request_missing_from_the_search_is_refused(self):
        class Lag(FakeGh):
            def __call__(self, *args):
                out = super().__call__(*args)
                if args[:2] == ("pr", "list") and "merged" in args:
                    return []
                return out
        with self.assertRaises(status.StatusError):
            status.collect_repo(Lag(), "o/r", "2026-11-13")

    def test_marked_name_is_not_redacted_at_collection(self):
        calls = {}
        original = status.collect_repo
        status.collect_repo = lambda gh, repo, since, restricted=(): calls.setdefault("r", set(restricted)) or {"full_name": repo}
        self.addCleanup(setattr, status, "collect_repo", original)
        status.collect_snapshot(manifest(), "2026-11-13", "2026-11-15", "a", gh=None, clock=lambda: "b")
        self.assertNotIn("named-thing", calls["r"])
        self.assertIn("hidden-thing", calls["r"])

    def test_one_pass_redaction_does_not_garble_or_trip_the_gate(self):
        text = status.redact("see hidden-thing and rest", {"hidden-thing", "rest", "repo"})
        self.assertEqual(text, "see (restricted repository) and (restricted repository)")
        m = manifest()
        m["repositories"][1]["key"] = "rest"
        status._gate_surface("see (restricted repository) here", m)  # the placeholder's own letters are not a leak
        with self.assertRaises(status.StatusError):
            status._gate_surface("the rest of it", m)

    def test_head_that_moves_during_collection_is_refused(self):
        with self.assertRaises(status.StatusError):
            status.collect_repo(FakeGh(head_moves=True), "o/r", "2026-11-13")

    def test_bookkeeping_titles_and_pins_are_shortened_at_collection(self):
        self.assertEqual(status.redact("Revert " + "ab" * 20, set()), "Revert " + "ab" * 6)

    def test_empty_commit_message_is_tolerated(self):
        repo = status.collect_repo(FakeGh(empty_message=True), "o/r", "2026-11-13")
        self.assertEqual(repo["main"]["title"], "")

    def test_overflowing_check_runs_and_jobs_are_refused(self):
        with self.assertRaises(status.StatusError):
            status.collect_repo(FakeGh(many_checks=True), "o/r", "2026-11-13")
        with self.assertRaises(status.StatusError):
            status.collect_repo(FakeGh(many_jobs=True), "o/r", "2026-11-13")

    def test_truncated_list_is_refused(self):
        with self.assertRaises(status.StatusError):
            status.collect_repo(FakeGh(truncate=True), "o/r", "2026-11-13")

    def test_collect_snapshot_visits_only_listed_repositories_and_redacts(self):
        seen = []
        original = status.collect_repo

        def spy(gh, repo, since, restricted=()):
            seen.append((repo, sorted(restricted)))
            return {"full_name": repo}
        status.collect_repo = spy
        self.addCleanup(setattr, status, "collect_repo", original)
        snap = status.collect_snapshot(manifest(), "2026-11-13", "2026-11-15", "start", gh=None, clock=lambda: "end")
        self.assertEqual((snap["started_at"], snap["captured_at"]), ("start", "end"))
        self.assertEqual([r for r, _ in seen], [status.HUB, "4444J" "99/alpha-public"])
        self.assertIn("hidden-thing", seen[0][1])
        self.assertEqual((snap["name_only"], snap["omitted_count"]), (["named-thing"], 1))

    def test_omitted_repository_is_never_collected(self):
        full, _, _ = status.tracked_repositories(manifest())
        self.assertNotIn("4444J" "99/hidden-thing", full)
        self.assertNotIn("4444J" "99/named-thing", full)


class CliTests(unittest.TestCase):
    def setUp(self):
        self.dir = tempfile.TemporaryDirectory()
        self.addCleanup(self.dir.cleanup)
        self.tmp = Path(self.dir.name)
        (self.tmp / "manifest.json").write_text(json.dumps(manifest()), encoding="utf-8")
        (self.tmp / "snap.json").write_text(json.dumps(snapshot()), encoding="utf-8")

    def cli(self, *args):
        out, err = io.StringIO(), io.StringIO()
        with redirect_stdout(out), redirect_stderr(err):
            code = status.main(["--manifest", str(self.tmp / "manifest.json"), *args])
        return code, out.getvalue(), err.getvalue()

    def test_from_snapshot_to_stdout_and_file_match(self):
        code, out, _ = self.cli("--from-snapshot", str(self.tmp / "snap.json"))
        self.assertEqual(code, 0)
        page = self.tmp / "page.md"
        self.assertEqual(self.cli("--from-snapshot", str(self.tmp / "snap.json"), "--out", str(page))[0], 0)
        self.assertEqual(page.read_text(encoding="utf-8"), out)

    def test_check_detects_drift(self):
        page = self.tmp / "page.md"
        self.cli("--from-snapshot", str(self.tmp / "snap.json"), "--out", str(page))
        self.assertEqual(self.cli("--from-snapshot", str(self.tmp / "snap.json"), "--out", str(page), "--check")[0], 0)
        page.write_text(page.read_text(encoding="utf-8") + "hand edit\n", encoding="utf-8")
        self.assertEqual(self.cli("--from-snapshot", str(self.tmp / "snap.json"), "--out", str(page), "--check")[0], 1)
        self.assertEqual(self.cli("--from-snapshot", str(self.tmp / "snap.json"), "--out", str(self.tmp / "none.md"), "--check")[0], 1)

    def test_unresolved_snapshot_exits_two(self):
        bad = snapshot()
        bad["repositories"][0]["merged_prs"][0]["resolved"] = False
        (self.tmp / "bad.json").write_text(json.dumps(bad), encoding="utf-8")
        code, out, err = self.cli("--from-snapshot", str(self.tmp / "bad.json"))
        self.assertEqual((code, out), (2, ""))
        self.assertIn("refused", err)

    def fake_collect(self, result):
        original = status.collect_snapshot
        status.collect_snapshot = lambda *a, **k: result
        self.addCleanup(setattr, status, "collect_snapshot", original)

    def test_failed_validation_leaves_no_snapshot_or_page(self):
        bad = snapshot()
        bad["repositories"][0]["main"]["resolved"] = False
        self.fake_collect(bad)
        out, snap = self.tmp / "p.md", self.tmp / "s.json"
        code, _, err = self.cli("--since", "2026-11-13", "--out", str(out), "--snapshot-out", str(snap))
        self.assertEqual(code, 2)
        self.assertEqual(sorted(p.name for p in self.tmp.iterdir()), ["manifest.json", "snap.json"])

    def test_live_run_writes_validated_snapshot_that_rerenders_identically(self):
        self.fake_collect(snapshot())
        out, snap = self.tmp / "p.md", self.tmp / "s.json"
        self.assertEqual(self.cli("--since", "2026-11-13", "--out", str(out), "--snapshot-out", str(snap))[0], 0)
        self.assertEqual(json.loads(snap.read_text(encoding="utf-8")), snapshot())
        self.assertEqual(self.cli("--from-snapshot", str(snap), "--out", str(out), "--check")[0], 0)

    def test_live_mode_writes_page_and_snapshot_together_or_not_at_all(self):
        self.fake_collect(snapshot())
        out, snap = self.tmp / "p.md", self.tmp / "s.json"
        self.assertEqual(self.cli("--since", "2026-11-13", "--out", str(out))[0], 2)
        self.assertEqual(self.cli("--since", "2026-11-13", "--snapshot-out", str(snap))[0], 2)
        self.assertEqual(self.cli("--from-snapshot", str(self.tmp / "snap.json"), "--snapshot-out", str(snap))[0], 2)
        blocked = self.tmp / "nodir" / "s.json"
        self.assertEqual(self.cli("--since", "2026-11-13", "--out", str(out), "--snapshot-out", str(blocked))[0], 2)
        self.assertFalse(out.exists(), "page must not be written when the snapshot cannot be")
        self.assertEqual(sorted(p.name for p in self.tmp.iterdir()), ["manifest.json", "snap.json"])

    def test_existing_dated_page_is_not_overwritten_without_replace(self):
        self.fake_collect(snapshot())
        out, snap = self.tmp / "p.md", self.tmp / "s.json"
        args = ("--since", "2026-11-13", "--out", str(out), "--snapshot-out", str(snap))
        self.assertEqual(self.cli(*args)[0], 0)
        first = out.read_text(encoding="utf-8")
        changed = snapshot()
        changed["captured_at"] = "2026-11-15T17:00:00Z"
        self.fake_collect(changed)
        self.assertEqual(self.cli(*args)[0], 2)
        self.assertEqual(out.read_text(encoding="utf-8"), first)
        self.assertEqual(self.cli(*args, "--replace")[0], 0)
        self.assertNotEqual(out.read_text(encoding="utf-8"), first)

    def test_failed_second_rename_restores_both_files(self):
        page, snap = self.tmp / "p.md", self.tmp / "s.json"
        page.write_text("old page", encoding="utf-8")
        snap.mkdir()  # renaming a file over a directory fails
        with self.assertRaises(OSError):
            status.write_all([(page, "new page"), (snap, "new snapshot")])
        self.assertEqual(page.read_text(encoding="utf-8"), "old page")
        self.assertEqual(sorted(p.name for p in self.tmp.iterdir()), ["manifest.json", "p.md", "s.json", "snap.json"])

    def test_rename_failure_removes_a_file_that_did_not_exist_before(self):
        fresh, blocked = self.tmp / "new.md", self.tmp / "dir"
        blocked.mkdir()
        with self.assertRaises(OSError):
            status.write_all([(fresh, "x"), (blocked, "y")])
        self.assertFalse(fresh.exists())

    def test_check_needs_snapshot_and_out(self):
        self.assertEqual(self.cli("--check", "--since", "2026-11-13")[0], 2)
        self.assertEqual(self.cli("--check", "--from-snapshot", str(self.tmp / "snap.json"))[0], 2)

    def test_unreadable_output_is_a_refusal_not_a_traceback(self):
        code, _, err = self.cli("--from-snapshot", str(self.tmp / "snap.json"), "--out", str(self.tmp / "nodir" / "p.md"))
        self.assertEqual(code, 2)
        self.assertIn("refused", err)

    def test_live_dates_are_validated_before_any_network_call(self):
        out, snap = str(self.tmp / "p.md"), str(self.tmp / "s.json")
        for since, date in (("2026-11-13", "2026-11-10"), ("2026-13-45", "2026-11-15"), ("2026-11-13", "2026-02-30"),
                            ("2026-11-13", "2999-01-01")):
            code, _, err = self.cli("--since", since, "--date", date, "--out", out, "--snapshot-out", snap)
            self.assertEqual(code, 2, (since, date))

    def test_live_mode_without_both_outputs_is_refused(self):
        self.fake_collect(snapshot())
        self.assertEqual(self.cli("--since", "2026-11-13")[0], 2)

    def test_transient_gh_failures_are_retried_but_rate_limits_are_not(self):
        calls = []

        class Done:
            def __init__(self, code, out="", err=""):
                self.returncode, self.stdout, self.stderr = code, out, err
        results = [Done(1, err="Post x: unexpected EOF"), Done(0, out='{"a": 1}')]
        original_run, original_sleep = status.subprocess.run, status.time.sleep
        status.subprocess.run = lambda *a, **k: calls.append(1) or results.pop(0)
        status.time.sleep = lambda s: None
        self.addCleanup(setattr, status.subprocess, "run", original_run)
        self.addCleanup(setattr, status.time, "sleep", original_sleep)
        self.assertEqual(status.gh_json("api", "x"), {"a": 1})
        self.assertEqual(len(calls), 2)
        calls.clear()
        results[:] = [Done(1, err="HTTP 403: API rate limit exceeded"), Done(0, out="{}")]
        with self.assertRaises(status.StatusError):
            status.gh_json("api", "x")
        self.assertEqual(len(calls), 1)

    def test_titles_cannot_become_live_links(self):
        cleaned = status.clean("see https://example.invalid/x and www.example.invalid")
        self.assertNotIn("://", cleaned)
        self.assertNotIn("www.", cleaned)
        self.assertIn("https:&#47;&#47;example.invalid/x", cleaned)

    def test_live_mode_requires_since(self):
        self.assertEqual(self.cli()[0], 2)


class CommittedPageTests(unittest.TestCase):
    """Generated pages in the repository must equal the rendering of their snapshot."""

    def test_every_committed_page_matches_its_snapshot(self):
        repo_manifest = json.loads((ROOT / "workspace-manifest.json").read_text(encoding="utf-8"))
        snapshots = sorted((ROOT / "docs" / "status").glob("*.snapshot.json"))
        self.assertTrue(snapshots, "no committed snapshot")
        for snap_path in snapshots:
            page_path = snap_path.with_name(snap_path.name.replace(".snapshot.json", ".md"))
            with self.subTest(page=page_path.name):
                self.assertTrue(page_path.exists())
                expected = status.render(json.loads(snap_path.read_text(encoding="utf-8")), repo_manifest)
                self.assertEqual(page_path.read_text(encoding="utf-8"), expected, "regenerate: do not hand-edit generated pages")

    def test_every_generated_page_has_a_snapshot(self):
        for page in sorted((ROOT / "docs" / "status").glob("*.md")):
            with self.subTest(page=page.name):
                self.assertTrue(page.with_name(page.name[:-3] + ".snapshot.json").exists(),
                                "a page in docs/status without a snapshot is hand-written")
                self.assertTrue(page.read_text(encoding="utf-8").startswith(identity.GENERATED_STATUS_MARKER))

    def test_committed_pages_pass_the_public_surface_validator(self):
        repo_manifest = json.loads((ROOT / "workspace-manifest.json").read_text(encoding="utf-8"))
        paths = [str(p.relative_to(ROOT)) for p in (ROOT / "docs" / "status").iterdir()
                 if p.is_file() and p.suffix in (".md", ".json")]
        identity.validate_public_surface(paths, lambda p: (ROOT / p).read_text(encoding="utf-8"), {}, repo_manifest)

    def test_status_documentation_states_pages_are_generated(self):
        text = (ROOT / "docs" / "status-generation.md").read_text(encoding="utf-8")
        self.assertIn("generated, not hand-written", text)
        self.assertIn("tools/status_snapshot.py", text)


if __name__ == "__main__":
    unittest.main()
