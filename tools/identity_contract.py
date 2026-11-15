#!/usr/bin/env python3
"""Typed ACE identity contract and conservative public catalog projection.

The authored manifest retains already-published legacy custody records. Their
sensitive subset is frozen; the public projection never exports those bindings.
Implementation contracts remain in the repositories that own their source.
"""

from copy import deepcopy
import hashlib
import json
from pathlib import PurePosixPath
import re

COLLECTIONS = {
    "software_systems": "software_system", "capabilities": "capability",
    "modules": "module", "source_media": "source_media",
    "compositions": "composition", "artworks": "artwork", "editions": "edition",
    "archives": "archive",
}
REF_TYPES = {
    "system_ref": "software_system", "software_ref": "software_system",
    "capability_refs": "capability", "artwork_ref": "artwork",
    "composition_ref": "composition", "source_media_refs": "source_media",
    "archive_ref": "archive",
}
ID = re.compile(r"[a-z0-9]+(?:-[a-z0-9]+)*\Z")
COMMON_FIELDS = {"type", "id", "visibility"}
ENTITY_FIELDS = {
    "software_system": {"name", "responsibility", "repository_github_id", "implementation_contract", "integration_status"},
    "capability": {"native_id", "description"},
    "module": {"native_id", "software_ref", "path", "capability_refs", "interfaces", "reuse_status", "description", "compatibility_note"},
    "source_media": {"native_id", "label", "description", "content_digest", "provenance"},
    "composition": {"native_id", "software_ref", "artwork_ref", "path", "source_media_refs", "status", "description", "json_pointer"},
    "artwork": {"project_id", "title", "aliases", "publication_status"},
    "edition": {"native_id", "artwork_ref", "composition_ref", "version", "path", "json_pointer", "publication_status", "provenance"},
    "archive": {"legacy_slug", "description"},
}
PROVENANCE_FIELDS = {"repository_github_id", "record_path", "source_id", "original_name", "status"}
PRIVATE_SOFTWARE = {
    1408128309: ("synchronized-generation-playback", "Synchronized Generation Playback"),
    1320324017: ("deterministic-performance-engine", "Deterministic Performance Engine"),
}
# Captured from coordination main before migration 2.1.0. Changing this pin is a
# reviewed publication-contract migration, never part of rendering or discovery.
LEGACY_PRIVATE_SHA256 = "8b8d00ca7e0df9dcbdb006c146e49e4e75f304c81c8dd2cf2aa46161ff9bbf70"
LEGACY_PRIVATE_IDS = {1408128309, 1320324017}
REPOSITORY_ADDITIONS = {"directory_slug", "software_ref", "status_listing"}
PROJECT_ADDITIONS = {"identity_ref"}


def _required(record, *fields):
    for field in fields:
        if field not in record or record[field] in (None, ""):
            raise ValueError(f"Missing {field} in {record.get('id', record.get('key', 'record'))}")


def _portable_path(value):
    path = PurePosixPath(value)
    if not value or str(path) == "." or path.is_absolute() or ".." in path.parts or "\\" in value:
        raise ValueError(f"Nonportable identity path: {value!r}")


def _ref(value, expected, records):
    if not isinstance(value, dict) or set(value) != {"type", "id"}:
        raise ValueError("A typed reference requires exactly type and id")
    if value["type"] != expected:
        raise ValueError(f"Wrong reference type: expected {expected}")
    if records.get(value["id"], {}).get("type") != expected:
        raise ValueError(f"Unresolved {expected} reference: {value['id']}")


def validate_registry(manifest):
    registry = manifest.get("identity_registry")
    if not isinstance(registry, dict) or registry.get("schema_version") != "1.0.0":
        raise ValueError("Unsupported identity registry")
    if set(registry) != {"schema_version", *COLLECTIONS}:
        raise ValueError("Identity registry must declare all eight typed collections")
    records = {}
    for collection, kind in COLLECTIONS.items():
        if not isinstance(registry[collection], list):
            raise ValueError(f"Identity collection must be an array: {collection}")
        for record in registry[collection]:
            _required(record, "id", "type", "visibility")
            if record["type"] != kind:
                raise ValueError(f"Wrong entity type in {collection}")
            unknown = set(record) - COMMON_FIELDS - ENTITY_FIELDS[kind]
            if unknown:
                raise ValueError(f"Unknown {kind} fields: {sorted(unknown)}")
            structured = {"repository_github_id", "provenance", "aliases", "interfaces", *REF_TYPES}
            for key, value in record.items():
                if key not in structured and not isinstance(value, str):
                    raise ValueError(f"{kind}.{key} must be a string")
            for key in ("aliases", "interfaces"):
                if key in record and (not isinstance(record[key], list) or
                                      any(not isinstance(value, str) for value in record[key])):
                    raise ValueError(f"{kind}.{key} must be an array of strings")
            if "repository_github_id" in record and (type(record["repository_github_id"]) is not int or record["repository_github_id"] <= 0):
                raise ValueError("Repository identity must be a positive integer")
            if not ID.fullmatch(record["id"]):
                raise ValueError(f"Invalid identity: {record['id']}")
            if record["id"] in records:
                raise ValueError(f"Duplicate identity: {record['id']}")
            if record["visibility"] not in ("public", "restricted"):
                raise ValueError("Identity visibility must be explicit")
            records[record["id"]] = record
    repos = {r["github_id"]: r for r in manifest["repositories"]}
    if len(repos) != len(manifest["repositories"]):
        raise ValueError("Duplicate GitHub repository identity")
    project_ids = {p["id"] for p in manifest["projects"]}
    artwork_project_ids = set()
    for record in records.values():
        kind = record["type"]
        for key, value in record.items():
            if key.endswith(("_ref", "_refs")):
                if key not in REF_TYPES:
                    raise ValueError(f"Unknown typed relationship: {key}")
                if key.endswith("_refs"):
                    if not isinstance(value, list):
                        raise ValueError(f"Reference collection must be an array: {key}")
                    values = value
                else:
                    values = [value]
                for ref in values:
                    _ref(ref, REF_TYPES[key], records)
        if "path" in record:
            _portable_path(record["path"])
        if "implementation_contract" in record:
            _portable_path(record["implementation_contract"])
        if "provenance" in record:
            provenance = record["provenance"]
            if not isinstance(provenance, dict) or set(provenance) - PROVENANCE_FIELDS:
                raise ValueError("Unknown provenance fields")
            _required(provenance, "repository_github_id", "record_path")
            if type(provenance["repository_github_id"]) is not int:
                raise ValueError("Provenance repository identity must be an integer")
            if any(not isinstance(value, str) for key, value in provenance.items() if key != "repository_github_id"):
                raise ValueError("Provenance metadata must use scalar strings")
            _portable_path(provenance["record_path"])
            owner = repos.get(provenance["repository_github_id"])
            if owner is None or owner["private"]:
                raise ValueError("Source provenance must belong to a public existing owner")
        if kind == "software_system":
            _required(record, "name", "responsibility")
            if "repository_github_id" in record:
                repo = repos.get(record["repository_github_id"])
                if repo is None:
                    raise ValueError("Software refers to an unknown repository")
                expected = "restricted" if repo["private"] else "public"
                if record["visibility"] != expected:
                    raise ValueError("Software visibility differs from its repository")
        elif kind == "capability":
            _required(record, "description")
        elif kind == "module":
            _required(record, "software_ref", "capability_refs", "path", "interfaces")
            if not record["capability_refs"] or not isinstance(record["interfaces"], list):
                raise ValueError("Module needs capabilities and explicit interface list")
        elif kind == "source_media":
            _required(record, "description", "content_digest", "provenance")
            if not re.fullmatch(r"sha256:[a-f0-9]{64}", record["content_digest"]):
                raise ValueError("Source media needs a verified SHA-256 content identity")
            _required(record["provenance"], "original_name")
        elif kind == "composition":
            _required(record, "software_ref", "artwork_ref", "source_media_refs", "status")
        elif kind == "artwork":
            _required(record, "project_id", "title", "publication_status")
            if record["project_id"] not in project_ids or record["project_id"] in artwork_project_ids:
                raise ValueError("Artwork must resolve to one unique existing project")
            artwork_project_ids.add(record["project_id"])
            if record["publication_status"] not in ("unverified", "unpublished", "published"):
                raise ValueError("Invalid artwork publication status")
        elif kind == "edition":
            _required(record, "native_id", "artwork_ref", "composition_ref", "path", "publication_status", "provenance")
            if record["publication_status"] not in ("unverified", "unpublished", "published"):
                raise ValueError("Invalid edition publication status")
            composition = records[record["composition_ref"]["id"]]
            if composition["artwork_ref"] != record["artwork_ref"]:
                raise ValueError("Edition and composition must refer to the same artwork")
            software = records[composition["software_ref"]["id"]]
            if record["provenance"]["repository_github_id"] != software.get("repository_github_id"):
                raise ValueError("Edition provenance differs from composition owner")
        elif kind == "archive":
            _required(record, "description", "legacy_slug")
            if record["legacy_slug"] not in {a["slug"] for a in manifest["archives"]}:
                raise ValueError("Archive must refer to a retained existing archive")
    for group, field in (("repositories", "software_ref"), ("projects", "identity_ref")):
        for item in manifest[group]:
            if field in item:
                expected = "software_system" if group == "repositories" else item[field]["type"]
                if expected not in ("software_system", "artwork"):
                    raise ValueError("Project identity must describe software or artwork")
                _ref(item[field], expected, records)
                if group == "repositories" and records[item[field]["id"]].get("repository_github_id") != item["github_id"]:
                    raise ValueError("Repository/software identity mismatch")
    for group, key in (("repositories", "key"), ("components", "slug"), ("archives", "slug")):
        destinations = {}
        for item in manifest[group]:
            canonical = item.get("directory_slug", item[key])
            if not ID.fullmatch(canonical):
                raise ValueError("Invalid functional directory slug")
            for value in {canonical, item[key]}:
                if value in destinations and destinations[value] != item[key]:
                    raise ValueError("Canonical directory collides with a compatibility alias")
                destinations[value] = item[key]
    return records


def validate_publication(manifest):
    access = manifest.get("access", {})
    if access.get("repository_id") != 1413700288 or access.get("observed_visibility") != "public":
        raise ValueError("Coordination access observation is missing or changed; recheck publication contract")
    if not access.get("checked_at") or access.get("publication_policy") != "public-existing-relationships-only":
        raise ValueError("Missing conservative publication policy")
    for repo in manifest["repositories"]:
        if type(repo.get("private")) is not bool:
            raise ValueError("Repository privacy must be explicit")
        if repo.get("status_listing") not in (None, "name-only"):
            raise ValueError("status_listing must be absent or name-only")
        if repo.get("status_listing") and not repo["private"]:
            raise ValueError("status_listing applies only to restricted repositories")
    private = [r for r in manifest["repositories"] if r["private"]]
    if {r["github_id"] for r in private} != LEGACY_PRIVATE_IDS:
        raise ValueError("New or changed private repository relationship requires a publication review")
    keys = {r["key"] for r in private}
    sensitive = {
        "repositories": [{k: v for k, v in r.items() if k not in REPOSITORY_ADDITIONS} for r in private],
        "projects": [{k: v for k, v in p.items() if k not in PROJECT_ADDITIONS}
                     for p in manifest["projects"] if keys.intersection(p["repository_keys"])],
    }
    digest = hashlib.sha256(json.dumps(sensitive, sort_keys=True, separators=(",", ":")).encode()).hexdigest()
    if digest != LEGACY_PRIVATE_SHA256:
        raise ValueError("Private relationship differs from frozen published baseline")
    # Restricted implementations may be represented by existing repository IDs and
    # functional responsibilities, but private implementation/source manifests may
    # not be copied into this public coordination repository.
    for collection, records in manifest["identity_registry"].items():
        if not isinstance(records, list):
            continue
        for record in records:
            if record["visibility"] == "restricted":
                if collection != "software_systems" or record.get("repository_github_id") not in LEGACY_PRIVATE_IDS:
                    raise ValueError("Private implementation or source records belong in their private owner")
                if set(record) - {"type", "id", "name", "responsibility", "visibility", "repository_github_id"}:
                    raise ValueError("Private software record contains source relationships")
                expected = PRIVATE_SOFTWARE[record["repository_github_id"]]
                owner = next(r for r in private if r["github_id"] == record["repository_github_id"])
                if (record["id"], record["name"]) != expected or record["responsibility"] != owner["role"]:
                    raise ValueError("Private software descriptor differs from reviewed public responsibility")
    records = {r["id"]: r for group in COLLECTIONS for r in manifest["identity_registry"][group]}
    for record in records.values():
        if record["type"] in ("module", "composition"):
            software = records[record["software_ref"]["id"]]
            if software["visibility"] == "restricted":
                raise ValueError("Private module or composition relationship cannot be published")


PRIVATE_POINTER_PATH = re.compile(r"(?:^|/)private[-_]?pointers?(?:[-_./]|\Z)", re.IGNORECASE)
OWNER_REF = re.compile(r"(?:github\.com[/:])?\b(?:4444j99|organvm)/([a-z0-9._-]+?)(?:\.git)?(?![a-z0-9_-])")
PUBLIC_COMMIT_URL = re.compile(r"github\.com/4444j99/([a-z0-9._-]+)/commit/[0-9a-f]{7,40}")
COMMIT = re.compile(r"\b[0-9a-f]{40}\b")
STATUS_PAGE_PREFIX = "docs/status/"
SNAPSHOT_SUFFIX = ".snapshot.json"
GENERATED_STATUS_MARKER = "<!-- Generated by tools/status_snapshot.py."
PUBLIC_SELF = {"audiovisual-composition-system", "hub-audiovisual-projects"}


# The validator, its tests and the baseline necessarily spell out private names as fixtures.
SURFACE_FIXTURES = frozenset({"tools/identity_contract.py", "tools/tests/test_identity_contract.py",
                              "tools/public_surface_baseline.json"})


def in_surface_scope(path):
    """Every tracked file of any extension or case, except the exact reviewed fixtures. Binary files are skipped by the reader."""
    return path not in SURFACE_FIXTURES


def _repository_names(repo, navigation=True):
    names = {repo["full_name"].split("/", 1)[1]}
    names.update(repo[k] for k in ("key", "local_path") if repo.get(k))
    if navigation and repo.get("directory_slug"):
        names.add(repo["directory_slug"])
    origin = repo.get("configured_origin")
    if origin:
        names.add(origin.rstrip("/").rsplit("/", 1)[-1].removesuffix(".git"))
    return names


def public_repository_names(manifest):
    """Current names, historical aliases and explicitly public remotes of public repositories."""
    names = set(PUBLIC_SELF)
    for repo in manifest["repositories"]:
        if not repo["private"]:
            names |= _repository_names(repo)
        extra = repo.get("additional_remote")
        if extra and extra.get("private") is False:
            names.add(extra["full_name"].split("/", 1)[1])
    return names


def name_listed(repo):
    """A restricted repository whose manifest record deliberately marks its bare name public-safe for generated status pages."""
    return repo["private"] and repo.get("status_listing") == "name-only"


def private_repository_names(manifest, allow_listed=False):
    """Restricted names; ``allow_listed`` drops only the bare repository name of a name-only repository
    (generated status pages only). Its key, local path and origin aliases stay restricted."""
    names = set()
    for repo in manifest["repositories"]:
        if repo["private"]:
            found = _repository_names(repo, navigation=False)
            if allow_listed and name_listed(repo):
                found.discard(repo["full_name"].split("/", 1)[1])
            names |= found
    return names - public_repository_names(manifest)


def listed_name_paths(text, manifest):
    """Uses of a name-only repository's bare name as a path or owner-qualified reference (``name/src/x.py``,
    ``owner/name``). The exemption covers the bare name only, never a source binding built on it."""
    found = []
    lowered = text.lower()
    for repo in manifest["repositories"]:
        if name_listed(repo):
            name = re.escape(repo["full_name"].split("/", 1)[1].lower())
            if (re.search(r"(?<![a-z0-9_.-])%s\s*[/\\]|[/\\:@]\s*%s(?![a-z0-9_-])" % (name, name), lowered)
                    or re.search(r"(?<![a-z0-9_.-])%s[:@#]\S" % name, lowered)):
                found.append(repo["full_name"].split("/", 1)[1])
    return found


def private_qualified_origins(manifest, allow_listed=False):
    """Owner-qualified private identities, which stay private even when a public remote shares the basename."""
    found = set()
    for repo in manifest["repositories"]:
        if repo["private"]:
            if not (allow_listed and name_listed(repo)):
                found.add(repo["full_name"])
            origin = repo.get("configured_origin")
            if origin:
                found.add("/".join(origin.removesuffix(".git").rstrip("/").rsplit("/", 2)[-2:]))
    return found


def surface_facts(text, public, private=frozenset(), qualified=frozenset()):
    """Source bindings in a document: non-public owner references, known private
    repository names (with or without an owner prefix) and 40-hex commit pins
    that accompany either of them or the word private."""
    # GitHub identities are case-insensitive: compare everything lowercased.
    text = text.lower()
    public = {n.lower() for n in public}
    private = {n.lower() for n in private}
    qualified = {n.lower() for n in qualified}
    refs = set(OWNER_REF.findall(text)) - public
    for identity_ in qualified:
        if re.search(r"(?<![A-Za-z0-9_.-])" + re.escape(identity_) + r"(?![A-Za-z0-9_-])", text):
            refs.add(identity_)
    for name in private:
        if re.search(r"(?<![A-Za-z0-9_.-])" + re.escape(name) + r"(?![A-Za-z0-9_-])", text):
            refs.add(name)
    # Commit URLs of explicitly public repositories are public review evidence, not private pins.
    text = PUBLIC_COMMIT_URL.sub(lambda m: "" if m.group(1) in public else m.group(0), text)
    commits = sorted(set(COMMIT.findall(text))) if refs or re.search(r"private", text, re.IGNORECASE) else []
    return {"refs": sorted(refs), "commits": commits}


def read_text_or_none(path):
    """Decode a tracked file for inspection under every plausible text encoding.

    BOM-marked UTF-8/UTF-16/UTF-32 text is decoded; other NUL-bearing data is read as
    every plausible wide encoding at once so a pointer cannot hide behind its encoding.
    """
    data = path.read_bytes()
    for bom, codec in ((b"\xff\xfe\x00\x00", "utf-32"), (b"\x00\x00\xfe\xff", "utf-32"),
                       (b"\xef\xbb\xbf", "utf-8-sig"), (b"\xff\xfe", "utf-16"), (b"\xfe\xff", "utf-16")):
        if data.startswith(bom):
            return data.decode(codec, "replace")
    if b"\0" not in data:
        return data.decode("utf-8", "replace")
    views = [data.decode(codec, "replace") for codec in ("utf-16-le", "utf-16-be")]
    views.append(data.replace(b"\0", b"").decode("utf-8", "replace"))
    return "\n".join(views)


def content_digest(text):
    return hashlib.sha256(text.encode("utf-8", "replace")).hexdigest()


def validate_public_surface(paths, read, baseline, manifest):
    """Reject hand-authored private-source pointers in this public repository.

    Manifest checks only see manifest relationships, so a document naming a private
    repository would bypass them. Pointers live in the private owner. Every in-scope
    tracked file is inspected by content under any filename or extension. ``baseline`` maps the few
    documents that already carried reviewed source bindings to the SHA-256 of their
    reviewed content: any edit to such a document (new binding, new internal path)
    fails until the baseline entry is re-reviewed. All other documents may carry no
    source bindings at all, with one deliberate exception: a generated status page
    (docs/status/*.md starting with the generator marker, beside its snapshot) and
    that snapshot may name a repository whose manifest record carries
    status_listing "name-only", and then only its bare name.
    """
    paths = list(paths)
    bad = sorted(p for p in paths if PRIVATE_POINTER_PATH.search(p))
    if bad:
        raise ValueError("Private source pointers belong in their private owner: " + ", ".join(bad))
    public = public_repository_names(manifest)
    strict = (private_repository_names(manifest), private_qualified_origins(manifest))
    listed_sets = (private_repository_names(manifest, allow_listed=True),
                   private_qualified_origins(manifest, allow_listed=True))
    path_set = set(paths)
    for path in paths:
        if not in_surface_scope(path):
            continue
        text = read(path)
        # Only generated status pages (marker first), and the snapshot beside one, may name a repository the
        # manifest marks name-only.
        listed = path.startswith(STATUS_PAGE_PREFIX) and (
            (path.endswith(".md") and text.startswith(GENERATED_STATUS_MARKER)
             and path[:-3] + SNAPSHOT_SUFFIX in path_set)
            or (path.endswith(SNAPSHOT_SUFFIX) and path[:-len(SNAPSHOT_SUFFIX)] + ".md" in path_set
                and read(path[:-len(SNAPSHOT_SUFFIX)] + ".md").startswith(GENERATED_STATUS_MARKER)))
        private, qualified = listed_sets if listed else strict
        if path in baseline:
            if content_digest(text) != baseline[path]:
                raise ValueError("Private source pointers belong in their private owner: reviewed document %s "
                                 "changed; re-review its source bindings and update the baseline digest" % path)
            continue
        facts = surface_facts(text, public, private, qualified)
        found = facts["refs"] + facts["commits"]
        if listed:
            found += listed_name_paths(text, manifest) + COMMIT.findall(text.lower())
        if found:
            raise ValueError("Private source pointers belong in their private owner: %s adds source binding %s"
                             % (path, found[0]))


def validate_manifest(manifest):
    if manifest.get("schema_version") != "2.1.0":
        raise ValueError("Unsupported manifest contract")
    validate_registry(manifest)
    validate_publication(manifest)


def public_catalog(manifest):
    """Return a whitelist projection, never a redaction of arbitrary nested data."""
    validate_manifest(manifest)
    repos = []
    public_keys = set()
    for repo in manifest["repositories"]:
        fields = ("key", "github_id", "private", "directory_slug")
        projected = {k: deepcopy(repo[k]) for k in fields if k in repo}
        if repo["private"]:
            projected["role"] = "Restricted implementation; source relationships are withheld."
        else:
            public_keys.add(repo["key"])
            for key in ("full_name", "role", "software_ref"):
                if key in repo:
                    projected[key] = deepcopy(repo[key])
        repos.append(projected)
    registry = manifest.get("identity_registry", {})
    public_ids = {r["id"] for group in COLLECTIONS for r in registry.get(group, []) if r["visibility"] == "public"}
    projects = []
    for project in manifest["projects"]:
        fields = ("id", "slug", "title", "profile", "aliases")
        item = {k: deepcopy(project[k]) for k in fields}
        if any(key not in public_keys for key in project["repository_keys"]):
            item["aliases"] = []
        item["repository_keys"] = [key for key in project["repository_keys"] if key in public_keys]
        item["repository_subpath"] = project.get("repository_subpath") if item["repository_keys"] else None
        item["local_bindings"] = {}
        if project.get("identity_ref", {}).get("id") in public_ids:
            item["identity_ref"] = deepcopy(project["identity_ref"])
        item["source_state"] = deepcopy(project.get("source_state", "metadata-only"))
        item["decision"] = "Retained project membership. Artwork titles and legacy aliases do not name reusable software."
        projects.append(item)
    result = {"schema_version": manifest["schema_version"], "name": manifest["name"],
              "display_title": manifest["display_title"], "repositories": repos, "projects": projects,
              "components": [], "archives": []}
    for group in ("components", "archives"):
        for item in manifest[group]:
            projected = {k: deepcopy(item[k]) for k in ("slug", "directory_slug", "version_control") if k in item}
            projected["role"] = ("Preserved source; custody details remain in the existing owner."
                                 if group == "archives" else "Existing component; no duplicate implementation is created.")
            result[group].append(projected)
    restricted_projects = {p["id"] for p in manifest["projects"]
                           if any(key not in public_keys for key in p["repository_keys"])}
    if registry:
        result["identity_registry"] = {"schema_version": registry["schema_version"]}
        for group in COLLECTIONS:
            projected_records = []
            for record in registry[group]:
                if record["id"] not in public_ids:
                    continue
                fields = COMMON_FIELDS | ENTITY_FIELDS[record["type"]]
                item = {key: deepcopy(record[key]) for key in sorted(fields) if key in record}
                if record["type"] == "artwork" and record["project_id"] in restricted_projects:
                    item["aliases"] = []
                if "provenance" in item:
                    item["provenance"] = {key: deepcopy(record["provenance"][key])
                                          for key in sorted(PROVENANCE_FIELDS) if key in record["provenance"]}
                projected_records.append(item)
            result["identity_registry"][group] = projected_records
        for records in result["identity_registry"].values():
            if isinstance(records, list):
                for record in records:
                    for key in list(record):
                        if key in REF_TYPES:
                            refs = record[key] if key.endswith("_refs") else [record[key]]
                            if any(ref["id"] not in public_ids for ref in refs):
                                raise ValueError("Public entity references restricted identity")
    return result
