#!/usr/bin/env python3
"""Generate a dated audiovisual status page from live GitHub state.

Status pages that are written by hand go stale and have carried verifier-found
errors. This tool replaces the hand-written numbers: it reads each tracked
repository's live state with the ``gh`` CLI into a snapshot, then renders the
page from that snapshot alone, so a fixed snapshot always yields byte-identical
output (``--from-snapshot``).

Rules the tool enforces:

* Every pull request and commit it cites must have been resolved against the
  live repository when the snapshot was taken (merge commits are checked to be
  ancestors of the default branch: compare status ahead or identical). The collector refuses to emit a snapshot
  that cites anything it cannot resolve, and the renderer refuses a snapshot
  that carries an unresolved citation.
* A hosted run with zero executed steps is flagged ``cannot-start`` and is never
  reported as a pass, whatever its recorded conclusion.
* Only repositories the manifest marks public are listed in full. A restricted
  repository is listed by name only when its manifest record carries
  ``"status_listing": "name-only"``; otherwise it is omitted (only a count is
  kept). A repository the manifest calls public but GitHub reports as not public
  stops the run.
* Commit identifiers are stored as 12-character prefixes. The public-surface
  validator treats 40-character pins as source bindings, and a prefix checked
  against the full identifier at collection time is enough to name a commit.
* The finished page is passed through the public-surface fact extractor and the
  run is refused if it names a restricted repository or carries a full pin.

Only the Python standard library and the ``gh`` CLI are used.
"""

import argparse
import datetime
import json
import re
import subprocess
import time
import urllib.parse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import identity_contract  # noqa: E402  (sibling module)

SCHEMA = 1
HUB = "4444J99/hub-audiovisual-projects"
SHA_LEN = 12
SHOW_LEN = 7
PLACEHOLDER = "(restricted repository)"
SUBSTRING_MIN = 4  # restricted names at least this long are matched even inside longer tokens
HEX = re.compile(r"[0-9a-f]+")
TIMESTAMP = re.compile(r"[0-9]{4}-[0-9]{2}-[0-9]{2}T[0-9]{2}:[0-9]{2}:[0-9]{2}Z")
WORD = re.compile(r"[a-z0-9_-]+")
NAME = re.compile(r"[A-Za-z0-9_.-]+")
DATE = re.compile(r"\d{4}-\d{2}-\d{2}\Z")
FULL_PIN = re.compile(r"\b[0-9a-f]{40}\b", re.IGNORECASE)
RED_CONCLUSIONS = {"failure", "timed_out", "action_required", "startup_failure"}
MERGE_STATES = ("red", "cannot-start", "no-steps", "late", "pending", "cancelled")
EXECUTED = {"success", "failure", "cancelled", "timed_out"}
LIST_LIMIT = 300
RUN_WINDOW = 100  # newest default-branch runs examined; a workflow idle for longer is not listed
ACTIONS_JOB = r"https://github\.com/%s/actions/runs/(\d+)/job/(\d+)"
GENERATED_NOTE = identity_contract.GENERATED_STATUS_MARKER + " Do not edit by hand: regenerate from the snapshot. -->"


class StatusError(Exception):
    """A snapshot cannot be taken or rendered without citing something unresolved."""


class HeadMoved(StatusError):
    """The default branch advanced while a repository was being read."""


class NotFound(StatusError):
    """GitHub answered HTTP 404 for a read."""


# --------------------------------------------------------------------------- gh


TRANSIENT = re.compile(r"unexpected EOF|connection reset|timed? ?out|TLS handshake|\bHTTP 50[0-4]\b|temporarily unavailable",
                       re.IGNORECASE)
RETRIES = 2
HEAD_ATTEMPTS = 3


def gh_json(*args):
    """Run ``gh`` and parse its JSON output; any failure is a StatusError. A transient network or 5xx failure is
    retried (a rate limit or any 4xx is not)."""
    for attempt in range(RETRIES + 1):
        try:
            done = subprocess.run(["gh", *args], capture_output=True, text=True, timeout=120, check=False)
        except subprocess.TimeoutExpired as exc:
            if attempt < RETRIES:
                time.sleep(2 * (attempt + 1))
                continue
            raise StatusError("gh timed out: %s" % exc) from exc
        except OSError as exc:
            raise StatusError("gh could not run: %s" % exc) from exc
        if done.returncode != 0 and TRANSIENT.search(done.stderr) and attempt < RETRIES:
            time.sleep(2 * (attempt + 1))
            continue
        break
    if done.returncode != 0:
        kind = NotFound if re.search(r"\bHTTP 404\b", done.stderr) else StatusError
        raise kind("gh %s failed: %s" % (" ".join(args[:3]), done.stderr.strip()[:300]))
    try:
        return json.loads(done.stdout) if done.stdout.strip() else None
    except ValueError as exc:
        raise StatusError("gh returned non-JSON for %s" % " ".join(args[:3])) from exc


# ------------------------------------------------------------------- classifying


def real_timestamp(value):
    """True for an actual UTC instant written YYYY-MM-DDTHH:MM:SSZ (ASCII digits only)."""
    if not isinstance(value, str) or TIMESTAMP.fullmatch(value) is None:
        return False
    try:
        datetime.datetime.strptime(value, "%Y-%m-%dT%H:%M:%SZ")
    except ValueError:
        return False
    return True


def code(text):
    """Text for a markdown code span: single line, no backticks."""
    return " ".join(str(text).split()).replace("`", "'")


def real_date(value):
    """True for an actual calendar date written YYYY-MM-DD."""
    try:
        datetime.date.fromisoformat(value)
    except (TypeError, ValueError):
        return False
    return DATE.match(value) is not None


def short(sha):
    return sha[:SHA_LEN]


SYNTHETIC_STEPS = ("Set up job", "Complete job", "Initialize containers", "Stop containers")


def count_executed(steps):
    """Steps of the workflow itself that ran: completed with a conclusion other than skipped. GitHub's own
    'Set up job', 'Complete job', container and 'Post Run ...' bookkeeping steps do not count (the post-step of a
    named step, 'Post <step name>', cannot be told from a user step and does count, but exists only when its main step ran), so a job whose every real step
    was skipped, or that died before its first step, has zero."""
    return sum(1 for s in steps or []
               if s.get("status") == "completed" and s.get("conclusion") in EXECUTED
               and s.get("name") not in SYNTHETIC_STEPS and not str(s.get("name", "")).startswith("Post Run "))


def verdict(status, conclusion, executed):
    """One word for a hosted run. Zero executed steps is never a pass."""
    if status != "completed":
        return "pending"
    if conclusion == "skipped":
        return "skipped"
    if conclusion == "cancelled":
        return "cancelled"
    if executed == 0:
        return "cannot-start" if conclusion != "success" else "no-steps"
    if conclusion == "success":
        return "pass"
    if conclusion in RED_CONCLUSIONS:
        return "red"
    return "unknown"


def classify_check(check, merged_at, executed):
    """State of one check on a pull request head at merge time, or None when it was fine."""
    done = check.get("completed_at")
    if check.get("status") != "completed" or not done:
        return "pending"
    if done > merged_at:
        return "late"
    conclusion = check.get("conclusion")
    if conclusion == "success":
        return "no-steps" if executed == 0 else None
    if conclusion in RED_CONCLUSIONS:
        return "cannot-start" if executed == 0 else "red"
    if conclusion == "cancelled":
        return "cancelled"
    return None


# ------------------------------------------------------------------- collection


def check_manifest(manifest):
    """The fields this tool relies on must be well formed; the full contract is enforced by identity_contract."""
    for repo in manifest.get("repositories", []):
        if type(repo.get("private")) is not bool:
            raise StatusError("manifest repository privacy must be explicit")
        if repo.get("status_listing") not in (None, "name-only") or (repo.get("status_listing") and not repo["private"]):
            raise StatusError("manifest status_listing must be absent or name-only, on a restricted repository")


def tracked_repositories(manifest):
    """(full list, name-only list, omitted count) from the manifest's own marks."""
    check_manifest(manifest)
    full = [HUB]
    name_only = []
    omitted = 0
    for repo in manifest["repositories"]:
        if not repo["private"]:
            if repo["full_name"] not in full:
                full.append(repo["full_name"])
        elif repo.get("status_listing") == "name-only":
            name_only.append(repo["full_name"])
        else:
            omitted += 1
    return full, sorted(name_only), omitted


def _is_ancestor(gh, repo, sha, branch):
    cmp = gh("api", "repos/%s/compare/%s...%s" % (repo, sha, urllib.parse.quote(branch, safe="")))
    return isinstance(cmp, dict) and cmp.get("status") in ("ahead", "identical")


def collect_repo(gh, repo, since, restricted=(), marked=()):
    meta = gh("api", "repos/%s" % repo)
    if meta.get("private") is not False or meta.get("visibility", "public") != "public":
        raise StatusError("%s is marked public in the manifest but GitHub does not report it public" % repo)
    branch = meta["default_branch"]
    head = gh("api", "repos/%s/commits/%s" % (repo, urllib.parse.quote(branch, safe="")))
    head_sha = head["sha"]
    head_pr = None
    head_pr_merged = None
    for pull in gh("api", "repos/%s/commits/%s/pulls" % (repo, head_sha)) or []:
        if pull.get("merged_at") and pull.get("merge_commit_sha") == head_sha:
            head_pr = pull["number"]
            head_pr_merged = pull["merged_at"]

    merged_raw = gh("pr", "list", "-R", repo, "--state", "merged", "--search", "merged:>=%s" % since,
                    "--limit", str(LIST_LIMIT), "--json", "number,title,mergedAt,mergeCommit,headRefOid,baseRefName")
    if len(merged_raw) >= LIST_LIMIT:
        raise StatusError("%s: merged pull request list reached the %d limit; narrow --since" % (repo, LIST_LIMIT))
    merged = []
    red = []
    other_base = 0
    for pr in sorted(merged_raw, key=lambda p: (p["mergedAt"], p["number"])):
        if pr["baseRefName"] != branch:
            other_base += 1
            continue
        merge_sha = (pr.get("mergeCommit") or {}).get("oid")
        if not merge_sha or not _is_ancestor(gh, repo, merge_sha, branch):
            raise StatusError("%s #%d: merge commit cannot be resolved on %s" % (repo, pr["number"], branch))
        merged.append({"number": pr["number"], "title": redact(pr["title"], restricted, marked), "merged_at": pr["mergedAt"],
                       "merge_sha": short(merge_sha), "head_sha": short(pr["headRefOid"]), "resolved": True})
        red.extend(_red_at_merge(gh, repo, pr, restricted, marked))

    if head_pr is not None and head_pr_merged[:10] >= since and head_pr not in {p["number"] for p in merged_raw}:
        raise StatusError("%s: the head's pull request #%d is missing from the merged-PR search (index lag); run again shortly"
                          % (repo, head_pr))
    open_raw = gh("pr", "list", "-R", repo, "--state", "open", "--limit", str(LIST_LIMIT),
                  "--json", "number,title,isDraft,headRefOid,updatedAt,baseRefName")
    if len(open_raw) >= LIST_LIMIT:
        raise StatusError("%s: open pull request list reached the %d limit" % (repo, LIST_LIMIT))
    open_prs = [{"number": p["number"], "title": redact(p["title"], restricted, marked), "draft": bool(p["isDraft"]),
                 "head_sha": short(p["headRefOid"]), "updated_at": p["updatedAt"], "resolved": True}
                for p in sorted(open_raw, key=lambda p: p["number"])]

    runs = gh("api", "repos/%s/actions/runs?branch=%s&per_page=%d" % (repo, urllib.parse.quote(branch, safe=""), RUN_WINDOW))["workflow_runs"]
    latest = {}
    for run in sorted(runs, key=lambda r: (r["created_at"], r["id"]), reverse=True):
        if run.get("event") in ("pull_request", "pull_request_target") or run.get("head_sha") is None:
            continue  # a pull request from a fork branch named like the default branch is not default-branch CI
        latest.setdefault(run["workflow_id"], run)
    ci = []
    for workflow_id in sorted(latest, key=lambda w: (latest[w].get("name") or "", w)):
        run = latest[workflow_id]
        jobs = gh_pages(gh, "repos/%s/actions/runs/%d/jobs?per_page=100" % (repo, run["id"]), "jobs")
        executed = sum(count_executed(j.get("steps")) for j in jobs)
        ci.append({"workflow": redact(run.get("name") or "(unnamed workflow)", restricted, marked), "workflow_id": workflow_id, "run_id": run["id"], "event": run["event"], "status": run["status"],
                   "conclusion": run["conclusion"], "created_at": run["created_at"],
                   "head_sha": short(run["head_sha"]), "on_current_head": run["head_sha"] == head_sha,
                   "jobs": len(jobs), "executed_steps": executed,
                   "verdict": verdict(run["status"], run["conclusion"], executed)})

    if gh("api", "repos/%s/commits/%s" % (repo, urllib.parse.quote(branch, safe="")))["sha"] != head_sha:
        raise HeadMoved("%s: %s moved while its state was being read; run again" % (repo, branch))
    issues_updated = gh("issue", "list", "-R", repo, "--state", "all", "--search", "updated:>=%s" % since,
                        "--limit", str(LIST_LIMIT), "--json", "number,title,state,updatedAt")
    issues_open = gh("issue", "list", "-R", repo, "--state", "open", "--limit", "500", "--json", "number")
    if len(issues_updated) >= LIST_LIMIT or len(issues_open) >= 500:
        raise StatusError("%s: issue list reached its limit" % repo)
    return {
        "full_name": repo, "listing": "full", "visibility_live": "public", "default_branch": branch,
        "main": {"sha": short(head_sha), "title": redact((head["commit"]["message"].splitlines() or [""])[0], restricted, marked),
                 "committed_at": head["commit"]["committer"]["date"], "pr": head_pr, "resolved": True},
        "merged_prs": merged, "merged_other_base": other_base, "open_prs": open_prs, "ci": ci, "red_at_merge": red,
        "issues_open_count": len(issues_open),
        "issues_updated": [{"number": i["number"], "title": redact(i["title"], restricted, marked), "state": i["state"].lower(),
                            "updated_at": i["updatedAt"]} for i in sorted(issues_updated, key=lambda i: i["number"])],
    }


def gh_pages(gh, path, key):
    """Every item under ``key`` across all pages of a list endpoint; refuses an incomplete read."""
    pages = gh("api", "--paginate", "--slurp", path)
    items = [item for page in pages for item in page[key]]
    total = pages[0].get("total_count", len(items)) if pages else 0
    if total != len(items):
        raise StatusError("%s: read %d of %d %s" % (path.split("?")[0], len(items), total, key))
    return items


def _red_at_merge(gh, repo, pr, restricted, marked):
    """Checks on the final head that were red, cannot-start, cancelled, unfinished (late or still pending) when the PR merged."""
    found = []
    checks = gh_pages(gh, "repos/%s/commits/%s/check-runs?per_page=100" % (repo, pr["headRefOid"]), "check_runs")
    for check in sorted(checks, key=lambda c: (c["name"], c["id"])):
        run_id = None
        executed = None
        match = re.fullmatch(ACTIONS_JOB % re.escape(repo), check.get("details_url") or "", flags=re.IGNORECASE)
        if match:
            run_id = int(match.group(1))
            if check.get("status") == "completed" and check.get("conclusion") in RED_CONCLUSIONS | {"success"}:
                try:
                    job = gh("api", "repos/%s/actions/jobs/%s" % (repo, match.group(2)))
                    executed = count_executed(job.get("steps"))
                except NotFound:
                    executed = None  # expired logs: steps are not observable
        state = classify_check(check, pr["mergedAt"], 1 if executed is None else executed)
        if state is None:
            continue
        found.append({"pr": pr["number"], "head_sha": short(pr["headRefOid"]), "check": redact(check["name"], restricted, marked),
                      "state": state, "conclusion": check.get("conclusion"), "run_id": run_id,
                      "executed_steps": executed, "merged_at": pr["mergedAt"]})
    # Legacy commit statuses (status contexts) are not check runs; read them as well.
    combined = gh("api", "repos/%s/commits/%s/status?per_page=100" % (repo, pr["headRefOid"]))
    statuses = combined.get("statuses") or []
    if combined.get("total_count", len(statuses)) > len(statuses):
        raise StatusError("%s #%d: more than 100 commit statuses; red-at-merge would be incomplete" % (repo, pr["number"]))
    for item in sorted(statuses, key=lambda x: (x["context"], x.get("id", 0))):
        done = item.get("state") != "pending"
        state = ("pending" if not done else "late" if item["updated_at"] > pr["mergedAt"]
                 else "red" if item["state"] in ("failure", "error") else None)
        if state is None:
            continue
        found.append({"pr": pr["number"], "head_sha": short(pr["headRefOid"]), "check": redact(item["context"], restricted, marked),
                      "state": state, "conclusion": item["state"], "run_id": None, "executed_steps": None,
                      "merged_at": pr["mergedAt"]})
    return found


def redact(text, restricted, marked=()):
    """Replace restricted repository names in free text so they never enter a snapshot. A name-only repository
    keeps its bare name, but a path, owner-qualified or tagged use of it (``name/x``, ``a/name``, ``name:x``,
    ``name@x``, ``name#1``) is replaced, since the exemption covers the bare name only."""
    text = FULL_PIN.sub(lambda m: short(m.group(0)).lower(), " ".join(str(text).split()))
    parts = []
    for name in sorted(marked, key=len, reverse=True):
        n = re.escape(name)
        parts.append(r"[/\\:@]\s*%s(?![a-z0-9_-])|(?<![a-z0-9_.-])%s\s*[/\\]|(?<![a-z0-9_.-])%s[:@#](?=\S)" % (n, n, n))
    parts += [re.escape(n) if len(n) >= SUBSTRING_MIN else r"(?<![A-Za-z0-9])%s(?![A-Za-z0-9])" % re.escape(n)
              for n in sorted(restricted, key=len, reverse=True)]
    if not parts:
        return text
    # One pass over every alternative, so a replacement is never re-matched by a later name.
    return re.sub("|".join(parts), PLACEHOLDER, text, flags=re.IGNORECASE)


def collect_repo_retrying(gh, repo, since, restricted, marked):
    """A repository that merges while it is being read is read again (a few times) rather than failing the run."""
    for attempt in range(HEAD_ATTEMPTS):
        try:
            return collect_repo(gh, repo, since, restricted, marked)
        except HeadMoved:
            if attempt == HEAD_ATTEMPTS - 1:
                raise


def utc_now():
    return datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def collect_snapshot(manifest, since, date, started_at, gh=gh_json, clock=utc_now):
    full, name_only, omitted = tracked_repositories(manifest)
    restricted = identity_contract.private_repository_names(manifest, allow_listed=True) | set(
        identity_contract.private_qualified_origins(manifest, allow_listed=True))
    marked = {r["full_name"].split("/", 1)[1] for r in manifest["repositories"] if identity_contract.name_listed(r)}
    repositories = [collect_repo_retrying(gh, repo, since, restricted, marked) for repo in full]
    return {"schema": SCHEMA, "date": date, "since": since, "started_at": started_at, "captured_at": clock(),
            "repositories": repositories, "name_only": [n.split("/", 1)[1] for n in name_only],
            "omitted_count": omitted}


# ----------------------------------------------------------------------- render


def validate_snapshot(snap):
    """Refuse any snapshot that cites something it did not resolve or lists something it should not."""
    if not isinstance(snap, dict) or snap.get("schema") != SCHEMA:
        raise StatusError("unsupported snapshot schema")
    for key in ("date", "since"):
        if not isinstance(snap.get(key), str) or not real_date(snap[key]):
            raise StatusError("snapshot %s must be a real YYYY-MM-DD date" % key)
    if snap["since"] > snap["date"]:
        raise StatusError("snapshot since is after its date")
    if not isinstance(snap.get("repositories"), list) or not snap["repositories"]:
        raise StatusError("snapshot lists no repositories")

    def sha_ok(value):
        return isinstance(value, str) and len(value) == SHA_LEN and HEX.fullmatch(value) is not None

    if type(snap.get("omitted_count")) is not int:
        raise StatusError("snapshot lacks omitted_count")
    for key in ("started_at", "captured_at"):
        if not real_timestamp(snap.get(key)):
            raise StatusError("snapshot %s must be a real YYYY-MM-DDTHH:MM:SSZ instant" % key)
    if snap["started_at"] > snap["captured_at"]:
        raise StatusError("snapshot started_at is after captured_at")
    if not all(isinstance(n, str) and NAME.fullmatch(n) for n in snap.get("name_only", [])):
        raise StatusError("snapshot name_only must be a list of bare repository names")
    for repo in snap["repositories"]:
        name = repo.get("full_name", "?")
        if repo.get("listing") != "full" or repo.get("visibility_live") != "public":
            raise StatusError("%s: only repositories confirmed public may be listed in full" % name)
        if not isinstance(repo.get("default_branch"), str) or not repo["default_branch"].strip():
            raise StatusError("%s: default branch name is missing" % name)
        for pr in repo.get("merged_prs", []):
            if not real_timestamp(pr.get("merged_at")):
                raise StatusError("%s: merged pull request %r has no real merge time" % (name, pr.get("number")))
        for field in ("issues_open_count", "merged_other_base"):
            if type(repo.get(field, 0)) is not int or repo.get(field, 0) < 0:
                raise StatusError("%s: %s is not a count" % (name, field))
        for issue in repo.get("issues_updated", []):
            if type(issue.get("number")) is not int or issue["number"] <= 0:
                raise StatusError("%s: issue number is not a positive integer" % name)
            if issue.get("state") not in ("open", "closed") or not real_timestamp(issue.get("updated_at")):
                raise StatusError("%s: issue %r has an unknown state or update time" % (name, issue.get("number")))
        for run in repo.get("ci", []):
            for field in ("status", "conclusion"):
                if run.get(field) is not None and not (isinstance(run[field], str) and WORD.fullmatch(run[field])):
                    raise StatusError("%s: CI run %r has an unexpected %s" % (name, run.get("run_id"), field))
        for entry in repo.get("red_at_merge", []):
            if entry.get("conclusion") is not None and not (isinstance(entry["conclusion"], str)
                                                            and WORD.fullmatch(entry["conclusion"])):
                raise StatusError("%s: red-at-merge fact has an unexpected conclusion" % name)
        main = repo.get("main") or {}
        if not sha_ok(main.get("sha")) or main.get("resolved") is not True:
            raise StatusError("%s: main head is not resolved" % name)
        if main.get("pr") is not None and (type(main["pr"]) is not int or main["pr"] <= 0):
            raise StatusError("%s: main head cites an unresolved pull request" % name)
        for pr in repo.get("merged_prs", []):
            if (type(pr.get("number")) is not int or pr["number"] <= 0 or pr.get("resolved") is not True
                    or not sha_ok(pr.get("merge_sha")) or not sha_ok(pr.get("head_sha"))):
                raise StatusError("%s: merged pull request %r is not resolved" % (name, pr.get("number")))
        for pr in repo.get("open_prs", []):
            if type(pr.get("number")) is not int or pr.get("resolved") is not True or not sha_ok(pr.get("head_sha")):
                raise StatusError("%s: open pull request %r is not resolved" % (name, pr.get("number")))
        by_number = {pr["number"]: pr for pr in repo.get("merged_prs", [])}
        if main.get("pr") is None and any(p["merge_sha"] == main["sha"] for p in repo.get("merged_prs", [])):
            raise StatusError("%s: main head is a listed merge commit but cites no pull request" % name)
        in_window = by_number.get(main.get("pr"))
        if in_window is not None and in_window["merge_sha"] != main["sha"]:
            raise StatusError("%s: main head cites pull request #%d whose merge commit is a different commit" % (name, main["pr"]))
        for entry in repo.get("red_at_merge", []):
            cited = by_number.get(entry.get("pr"))
            if cited is None or entry.get("head_sha") != cited["head_sha"] or entry.get("merged_at") != cited["merged_at"]:
                raise StatusError("%s: red-at-merge fact does not match the merged pull request it cites" % name)
            if entry.get("run_id") is not None and type(entry["run_id"]) is not int:
                raise StatusError("%s: red-at-merge run id is not an integer" % name)
            steps = entry.get("executed_steps")
            if steps is not None and (type(steps) is not int or steps < 0):
                raise StatusError("%s: red-at-merge step count is not a count" % name)
            allowed = {"red": RED_CONCLUSIONS | {"error"}, "cannot-start": RED_CONCLUSIONS, "no-steps": {"success"},
                       "cancelled": {"cancelled"}}.get(entry["state"])
            if allowed is not None and entry.get("conclusion") not in allowed:
                raise StatusError("%s: red-at-merge state %r contradicts its conclusion %r" % (
                    name, entry["state"], entry.get("conclusion")))
            if entry["state"] in ("red", "cannot-start", "no-steps") and steps is not None and (entry["state"] != "red") != (steps == 0):
                raise StatusError("%s: red-at-merge state %r contradicts its %d executed steps" % (name, entry["state"], steps))
            if entry.get("state") not in MERGE_STATES:
                raise StatusError("%s: unknown red-at-merge state %r" % (name, entry.get("state")))
        for run in repo.get("ci", []):
            if (not sha_ok(run.get("head_sha")) or type(run.get("executed_steps")) is not int
                    or type(run.get("run_id")) is not int or type(run.get("jobs")) is not int
                    or not isinstance(run.get("status"), str) or not isinstance(run.get("workflow"), str)
                    or (run.get("conclusion") is not None and not isinstance(run["conclusion"], str))):
                raise StatusError("%s: CI run %r lacks a resolved head or step count" % (name, run.get("run_id")))
            if run.get("on_current_head") is not (run["head_sha"] == main["sha"]):
                raise StatusError("%s: CI run %r head flag contradicts the recorded heads" % (name, run.get("run_id")))
            expected = verdict(run.get("status"), run.get("conclusion"), run["executed_steps"])
            if run.get("verdict") != expected:
                raise StatusError("%s: CI run %r verdict %r contradicts its recorded steps (%s)"
                                  % (name, run.get("run_id"), run.get("verdict"), expected))


def clean(text):
    """Single-line, markdown-safe text with full pins shortened. Restricted names are removed at collection."""
    text = FULL_PIN.sub(lambda m: m.group(0)[:SHOW_LEN], " ".join(str(text).split()))
    for ch in "\\|`[]*_#~":
        text = text.replace(ch, "\\" + ch)
    text = text.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;").replace("@", "&#64;")
    # Keep titles from becoming live links (GFM autolinks): break the scheme separator and www prefix.
    return re.sub(r"(?i)\bwww\.", "www&#46;", text.replace("://", ":&#47;&#47;"))


def _url(repo, kind, number):
    return "https://github.com/%s/%s/%s" % (repo, kind, number)


def _pr(repo, number):
    return "[#%d](%s)" % (number, _url(repo, "pull", number))


def _step_text(entry):
    return "not observed" if entry is None else str(entry)


def render(snap, manifest):
    validate_snapshot(snap)
    marked = {r["full_name"].split("/", 1)[1] for r in manifest["repositories"] if identity_contract.name_listed(r)}
    if not set(snap.get("name_only", [])) <= marked:
        raise StatusError("snapshot lists a name the manifest does not mark name-only")
    allowed = {HUB} | {r["full_name"] for r in manifest["repositories"] if not r["private"]}
    for repo in snap["repositories"]:
        if repo["full_name"] not in allowed:
            raise StatusError("%s is not a public repository of this manifest and may not be listed in full" % repo["full_name"])
    c = clean
    older_note = []
    lines = [GENERATED_NOTE, "", "# Audiovisual estate status — %s (generated)" % snap["date"], "",
             "This page is generated, not hand-written, by `tools/status_snapshot.py` from live GitHub state "
             "read between %s and %s. Pull requests are those merged since %s. Every merged pull request, its merge commit "
             "and the `main` head were resolved against their repository when the snapshot was taken (merge commits "
             "checked as ancestors of `main`), and the tool refuses to cite what it cannot resolve; run and check heads, "
             "open pull requests and issues are as GitHub's API reported them. Commits are shown as %d-character prefixes. Regenerate with the command in "
             "[status-generation.md](../status-generation.md); do not edit this file." % (
                 snap["started_at"], snap["captured_at"], snap["since"], SHOW_LEN), "",
             "Reading the CI column: a run with **zero executed steps is `cannot-start`, never a pass**, whatever its "
             "recorded conclusion; `skipped` and `no-steps` are likewise not passes. Only runs on the current `main` head are "
             "listed in the table; workflows whose latest run is on an older head are named under it with their last "
             "verdict, which says nothing about the current head. `Final conclusion` in the red-at-merge table is the check's conclusion as read when "
             "the snapshot was taken, which can differ from its state at merge.", "",
             "## Heads and hosted CI on the default branch", "",
             "| Repository | `main` head | Workflow | Run | Run head | Conclusion | Executed steps | Verdict |",
             "|---|---|---|---|---|---|---|---|"]
    for repo in snap["repositories"]:
        name = repo["full_name"]
        main = repo["main"]
        head = "`%s`%s" % (main["sha"][:SHOW_LEN], " (%s)" % _pr(name, main["pr"]) if main["pr"] else " (no merged PR)")
        link = "[%s](https://github.com/%s)" % (name.split("/", 1)[1], name)
        current = [r for r in repo["ci"] if r["on_current_head"]]
        if not current:
            lines.append("| %s | %s | no run on the current head | | | | | no-run |" % (link, head))
        for i, run in enumerate(current):
            lines.append("| %s | %s | %s | [%d](%s) | `%s` | %s | %d (%d jobs) | **%s** |" % (
                link if i == 0 else "", head if i == 0 else "", c(run["workflow"]), run["run_id"],
                _url(name, "actions/runs", run["run_id"]), run["head_sha"][:SHOW_LEN],
                "%s/%s" % (run["status"], run["conclusion"] or "none"), run["executed_steps"], run["jobs"],
                run["verdict"]))
        older = [r for r in repo["ci"] if not r["on_current_head"]]
        if older:
            older_note.append("**%s** — latest `%s` run of %d workflow(s) is on an older head, so their state on the "
                              "current head is unknown: %s." % (
                                  name.split("/", 1)[1], code(repo["default_branch"]), len(older), "; ".join(
                                      "%s ([%d](%s), `%s`, %s)" % (c(r["workflow"]), r["run_id"],
                                                                   _url(name, "actions/runs", r["run_id"]),
                                                                   r["head_sha"][:SHOW_LEN], r["verdict"])
                                      for r in older)))
    if older_note:
        lines += ["", "Workflows not run on the current head (from the newest %d default-branch runs):" % RUN_WINDOW, ""]
        lines += ["- " + n for n in older_note]

    lines += ["", "## Merged since %s" % snap["since"], ""]
    for repo in snap["repositories"]:
        name = repo["full_name"]
        lines.append("### %s" % name.split("/", 1)[1])
        lines.append("")
        stacked = repo.get("merged_other_base", 0)
        note = ("%d pull request(s) merged into a branch other than `%s` in this window are not listed." % (
            stacked, code(repo["default_branch"]))) if stacked else ""
        if not repo["merged_prs"]:
            lines += ["No pull request merged into `%s` in this window." % code(repo["default_branch"]), ""] + ([note, ""] if note else [])
            continue
        lines += ["| Pull request | Title | Merge commit | Merged at |", "|---|---|---|---|"]
        for pr in repo["merged_prs"]:
            lines.append("| %s | %s | `%s` | %s |" % (_pr(name, pr["number"]), c(pr["title"]),
                                                       pr["merge_sha"][:SHOW_LEN], pr["merged_at"]))
        lines.append("")
        if note:
            lines += [note, ""]

    lines += ["## Open pull requests", ""]
    for repo in snap["repositories"]:
        name = repo["full_name"]
        if not repo["open_prs"]:
            lines.append("- **%s:** none open." % name.split("/", 1)[1])
            continue
        lines.append("- **%s:**" % name.split("/", 1)[1])
        for pr in repo["open_prs"]:
            lines.append("  - %s%s %s (head `%s`)" % (_pr(name, pr["number"]), " draft" if pr["draft"] else "",
                                                       c(pr["title"]), pr["head_sha"][:SHOW_LEN]))

    lines += ["", "## Issues", ""]
    for repo in snap["repositories"]:
        name = repo["full_name"]
        lines.append("### %s — %d open" % (name.split("/", 1)[1], repo["issues_open_count"]))
        lines.append("")
        if not repo["issues_updated"]:
            lines += ["No issue updated since %s." % snap["since"], ""]
            continue
        lines += ["| Issue | Title | State | Updated |", "|---|---|---|---|"]
        for issue in repo["issues_updated"]:
            lines.append("| [#%d](%s) | %s | %s | %s |" % (issue["number"], _url(name, "issues", issue["number"]),
                                                          c(issue["title"]), issue["state"], issue["updated_at"]))
        lines.append("")

    lines += ["## Red at merge", "",
              "Checks on a pull request's final head that were red, unable to start, cancelled or not yet finished when "
              "it merged. GitHub keeps only the latest attempt of a check, so the state describes that attempt: `late` "
              "means it finished after the merge time (a slow check or a later re-run; the column after it gives the "
              "conclusion), `pending` means it had not finished when the snapshot was read. `no-steps` means a check concluded success with zero executed steps (a hollow pass). `cannot-start` means the check's job executed zero steps; it is startup noise, recorded with "
              "its run id, and is not a failing test. A step count of `not observed` means its steps were not read (an external "
              "check, or a check that had not finished).", ""]
    any_red = False
    for repo in snap["repositories"]:
        name = repo["full_name"]
        if not repo["red_at_merge"]:
            continue
        any_red = True
        lines += ["### %s" % name.split("/", 1)[1], "",
                  "| Pull request | Head | Check | State at merge (latest attempt) | Final conclusion | Run | Executed steps |", "|---|---|---|---|---|---|---|"]
        for e in repo["red_at_merge"]:
            run = "[%d](%s)" % (e["run_id"], _url(name, "actions/runs", e["run_id"])) if e["run_id"] else "none"
            lines.append("| %s | `%s` | %s | **%s** | %s | %s | %s |" % (
                _pr(name, e["pr"]), e["head_sha"][:SHOW_LEN], c(e["check"]), e["state"], e["conclusion"] or "none",
                run, _step_text(e["executed_steps"])))
        lines.append("")
    if not any_red:
        lines += ["No merged pull request in this window had a red, cannot-start, no-steps, cancelled, late or pending check run or commit status at merge.", ""]

    lines += ["## Scope", "",
              "Tracked and listed in full: %s." % ", ".join(r["full_name"].split("/", 1)[1] for r in snap["repositories"])]
    if snap.get("name_only"):
        lines += ["", "Listed by name only (the manifest marks the name public-safe): %s." % ", ".join(
            "`%s`" % n for n in snap["name_only"])]
    lines += ["", "%d manifest repositories are omitted because the manifest does not mark them public-safe; their "
              "names, pull requests and contents are not described here." % snap["omitted_count"], "",
              "This page asserts no artistic, device, delivery or custody acceptance for any work. Each repository's "
              "own documents remain the owner of its claims. Local gate results are not in a snapshot and are not "
              "claimed here.", ""]
    page = "\n".join(lines)
    _gate_surface(page, manifest)
    _gate_surface(json.dumps(snap, sort_keys=True), manifest)  # the stored snapshot carries fields the page does not print
    return page


def _restricted_substrings(manifest):
    """Restricted names that must not appear even fused into a longer token (the matcher's word boundary would miss them)."""
    return {n.lower() for n in identity_contract.private_repository_names(manifest, allow_listed=True) if len(n) >= SUBSTRING_MIN}


def _gate_surface(page, manifest):
    bound = identity_contract.listed_name_paths(page.replace("\\", ""), manifest)
    if bound:
        raise StatusError("generated page builds a path or owner-qualified reference on a name-only repository: %s" % bound[0])
    lowered = page.replace(PLACEHOLDER, "").lower().replace("\\", "")
    for name in sorted(_restricted_substrings(manifest)):
        if name in lowered:
            raise StatusError("generated page contains a restricted repository name: %s" % name)
    # Markdown escaping can hide a name from the matcher, so check the page as written and with escapes removed.
    for text in (page, re.sub(r"\\(.)", r"\1", page)):
        facts = identity_contract.surface_facts(
            text, identity_contract.public_repository_names(manifest),
            identity_contract.private_repository_names(manifest, allow_listed=True),
            identity_contract.private_qualified_origins(manifest, allow_listed=True))
        found = facts["refs"] + facts["commits"]
        if found:
            raise StatusError("generated page would add a source binding to the public surface: %s" % found[0])


# -------------------------------------------------------------------------- cli


def write_all(files):
    """Write every (path, text) beside its target first, then rename them all; if a rename fails, put back what
    each target held before, so a failed run leaves neither a partial pair nor an orphaned page."""
    staged = [(path.with_name(path.name + ".tmp"), path, text) for path, text in files]
    before = {path: (path.read_bytes() if path.is_file() else None) for _, path, _ in staged}
    done = []
    try:
        for tmp, _, text in staged:
            tmp.write_text(text, encoding="utf-8")
        for tmp, path, _ in staged:
            tmp.replace(path)
            done.append(path)
    except BaseException:
        for path in done:
            if before[path] is None:
                path.unlink(missing_ok=True)
            else:
                path.write_bytes(before[path])
        raise
    finally:
        for tmp, _, _ in staged:
            tmp.unlink(missing_ok=True)


def main(argv=None):
    root = Path(__file__).resolve().parents[1]
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--manifest", type=Path, default=root / "workspace-manifest.json")
    parser.add_argument("--from-snapshot", type=Path, help="render this snapshot JSON; no network access")
    parser.add_argument("--date", help="page date, YYYY-MM-DD (live mode; default today UTC)")
    parser.add_argument("--since", help="list pull requests merged on or after YYYY-MM-DD (live mode; required)")
    parser.add_argument("--snapshot-out", type=Path, help="write the live snapshot JSON here")
    parser.add_argument("--out", type=Path, help="write the page here (default: stdout)")
    parser.add_argument("--replace", action="store_true",
                        help="live mode: allow overwriting an existing dated page and snapshot (otherwise refused)")
    parser.add_argument("--check", action="store_true", help="fail (exit 1) when --out differs from the rendering")
    args = parser.parse_args(argv)
    try:
        if args.check and not (args.from_snapshot and args.out):
            raise StatusError("--check needs --from-snapshot and --out")
        if not args.from_snapshot and not (args.out and args.snapshot_out):
            raise StatusError("live mode writes a page and its snapshot together: give both --out and --snapshot-out")
        if args.from_snapshot and args.snapshot_out:
            raise StatusError("--snapshot-out applies to live mode only")
        if not args.from_snapshot and not args.replace:
            for target in (args.out, args.snapshot_out):
                if target and target.exists():
                    raise StatusError("%s already exists: a later capture is a new dated page; pass --replace to overwrite" % target)
        manifest = json.loads(args.manifest.read_text(encoding="utf-8"))
        check_manifest(manifest)
        if args.from_snapshot:
            snap = json.loads(args.from_snapshot.read_text(encoding="utf-8"))
        else:
            if not args.since or not real_date(args.since):
                raise StatusError("--since YYYY-MM-DD (a real date) is required in live mode")
            now = datetime.datetime.now(datetime.timezone.utc)
            date = args.date or now.strftime("%Y-%m-%d")
            if date != now.strftime("%Y-%m-%d"):
                raise StatusError("--date must be the capture day (today, UTC): the page describes the state read now")
            if not real_date(date) or args.since > date:
                raise StatusError("--date must be a real YYYY-MM-DD date on or after --since")
            snap = collect_snapshot(manifest, args.since, date, now.strftime("%Y-%m-%dT%H:%M:%SZ"))
        page = render(snap, manifest)
        if args.check:
            if not args.out.exists() or args.out.read_text(encoding="utf-8") != page:
                print("status_snapshot: %s differs from its snapshot rendering" % args.out, file=sys.stderr)
                return 1
            return 0
        if args.out:
            files = [(args.out, page)]
            if not args.from_snapshot:
                files.append((args.snapshot_out, json.dumps(snap, indent=2, sort_keys=True) + "\n"))
            write_all(files)
        else:
            sys.stdout.write(page)
    except (StatusError, ValueError, KeyError, TypeError, IndexError, AttributeError, OSError) as exc:
        print("status_snapshot refused: %s" % exc, file=sys.stderr)
        return 2
    return 0


if __name__ == "__main__":
    sys.exit(main())
