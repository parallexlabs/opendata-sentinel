#!/usr/bin/env python3
"""Export the selected working tree as a separate, scanned initial public import."""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import shutil
import subprocess
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def hygiene_errors(content: bytes) -> list[str]:
    errors = []
    if re.search(rb"/(?:Users|home)/[A-Za-z0-9._-]+/", content):
        errors.append("absolute home-directory path")
    if "\u2014".encode() in content:
        errors.append("em dash")
    return errors


def git(*args: str, cwd: Path = ROOT, data: bytes | None = None) -> bytes:
    return subprocess.run(["git", *args], cwd=cwd, input=data, capture_output=True, check=True).stdout



def scan_public_refs(repository: Path, branch: str | None = None, *, main_alias: bool = False) -> list[str]:
    """Reject unselected refs before scanning the complete selected public history."""
    branch = branch or git("branch", "--show-current", cwd=repository).decode().strip() or "main"
    if branch != "main" and not re.fullmatch(r"publication-v[0-9]+", branch):
        raise SystemExit("Public branch must be main or publication-vN")
    allowed = {f"refs/heads/{branch}", f"refs/remotes/origin/{branch}", "refs/remotes/origin/HEAD"}
    if main_alias:
        allowed.add("refs/heads/main")
    refs = git("for-each-ref", "--format=%(refname)", cwd=repository).decode().splitlines()
    if unexpected := sorted(set(refs) - allowed):
        raise SystemExit(f"Unexpected public refs: {', '.join(unexpected)}")
    head = git("rev-parse", "HEAD", cwd=repository).decode().strip()
    if any(git("rev-parse", ref, cwd=repository).decode().strip() != head for ref in refs):
        raise SystemExit("Public refs must identify the same selected commit")
    commits = git("rev-list", "--all", cwd=repository).decode().splitlines()
    if not commits:
        raise SystemExit("No public commits to scan")
    for commit in commits:
        metadata = git("show", "-s", "--format=fuller", commit, cwd=repository)
        if hygiene_errors(metadata):
            raise SystemExit("Public commit metadata fails hygiene")
        names = git("ls-tree", "-r", "--name-only", "-z", commit, cwd=repository).split(b"\0")
        for raw in filter(None, names):
            errors = hygiene_errors(git("show", f"{commit}:{raw.decode()}", cwd=repository))
            if errors:
                raise SystemExit(f"Public ref hygiene failure: {raw.decode()}")
    return commits

def main(branch: str = "publication-v4", directory: str = "public-tree-v4", bundle: str = "fix_v4.bundle") -> None:
    state = ROOT / "state"
    state.mkdir(exist_ok=True)
    if not re.fullmatch(r"publication-v[0-9]+", branch):
        raise SystemExit("Use a publication-vN branch")
    if any(Path(name).name != name for name in (directory, bundle)):
        raise SystemExit("Export directory and bundle must be simple names inside state")
    destination = state / directory
    if destination.exists():
        raise SystemExit("Export destination already exists; select a fresh directory")
    # Refuse a business release unless every published row matches the source-free recipe.
    import pandas as pd
    from generate_business_fixture import business_frame, sample_frame

    business_paths = sorted((ROOT / "data/snapshots/business-licences").glob("*.parquet"))
    pd.testing.assert_frame_equal(pd.concat([pd.read_parquet(p) for p in business_paths], ignore_index=True),
                                  business_frame())
    pd.testing.assert_frame_equal(pd.read_csv(ROOT / "samples/business-licences.csv",
                                             dtype=str, keep_default_na=False), sample_frame())
    paths = sorted(set(git("ls-files", "--cached", "--others", "--exclude-standard", "-z").split(b"\0")) - {b""})
    selected = []
    for raw in paths:
        relative = Path(raw.decode())
        if relative.parts[0] in {".review", "state"}:
            continue
        source = ROOT / relative
        if not source.exists() and not source.is_symlink():
            continue  # Deleted private chunks must not re-enter the public import.
        if source.is_symlink() or not source.is_file():
            raise SystemExit(f"Export requires a regular file: {relative}")
        content = source.read_bytes()
        errors = hygiene_errors(content)
        if errors:
            raise SystemExit(f"Export hygiene failure in {relative}: {', '.join(errors)}")
        selected.append((relative, content))
    destination.mkdir()
    digests = {}
    for relative, content in selected:
        target = destination / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(content)
        shutil.copymode(ROOT / relative, target)
        digests[str(relative)] = hashlib.sha256(content).hexdigest()
    # fast-import creates one root commit; the original repository's refs/history are untouched.
    git("init", "-b", branch, cwd=destination)
    name = "Amirhossein (Amir) Daneshpajouh"
    email = "52765136+Daneshpajouh@users.noreply.github.com"
    identity = f"{name} <{email}> {int(time.time())} +0000"
    message = b"Fix publication claims, live redirects, retry budgets and review provenance.\n"
    payload = bytearray(f"commit refs/heads/{branch}\nauthor {identity}\ncommitter {identity}\n".encode())
    payload.extend(f"data {len(message)}\n".encode() + message)
    for relative, content in selected:
        mode = "100755" if (ROOT / relative).stat().st_mode & 0o111 else "100644"
        payload.extend(f"M {mode} inline {json.dumps(str(relative))}\ndata {len(content)}\n".encode())
        payload.extend(content + b"\n")
    payload.extend(b"\ndone\n")
    git("fast-import", "--quiet", data=bytes(payload), cwd=destination)
    git("read-tree", "HEAD", cwd=destination)
    public_ref = git("rev-parse", f"refs/heads/{branch}", cwd=destination).decode().strip()
    commits = scan_public_refs(destination, branch)
    assert len(commits) == 1 and commits[0] == public_ref, "Public import must contain one root commit"
    if git("status", "--porcelain", cwd=destination):
        raise SystemExit("Public import checkout must be clean")
    # The recovery main is an alias of the sanitized root, never the private source main.
    recovery = state / f"{directory}-recovery"
    git("clone", "--bare", "--no-local", str(destination), str(recovery))
    git("update-ref", "refs/heads/main", public_ref, cwd=recovery)
    scan_public_refs(recovery, branch, main_alias=True)
    git("bundle", "create", str(state / bundle), "refs/heads/main", f"refs/heads/{branch}", cwd=recovery)
    verification = git("bundle", "verify", str(state / bundle), cwd=recovery).decode().strip()
    bundle_heads = git("bundle", "list-heads", str(state / bundle), cwd=recovery).decode().splitlines()
    assert {line.split()[1] for line in bundle_heads} == {"refs/heads/main", f"refs/heads/{branch}"}
    assert all(line.split()[0] == public_ref for line in bundle_heads)
    receipt = {"public_ref": public_ref, "branch": branch, "commits_scanned": len(commits),
               "files": digests, "tree_scan": "passed", "all_public_refs_scan": "passed",
               "bundle_verification": verification, "bundle_heads": bundle_heads,
               "public_refs": [f"refs/heads/{branch}"], "main_is_sanitized_alias": True,
               "source_history_modified": False}
    (state / f"{directory}-receipt.json").write_text(json.dumps(receipt, indent=2) + "\n")
    print(f"Prepared {branch}: {len(selected)} files; one root commit; scans passed")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--scan-public-refs", action="store_true")
    parser.add_argument("--branch", default="publication-v4")
    parser.add_argument("--directory", default="public-tree-v4")
    parser.add_argument("--bundle", default="fix_v4.bundle")
    args = parser.parse_args()
    if args.scan_public_refs:
        print(f"Public ref scan passed: {len(scan_public_refs(ROOT))} commits")
    else:
        main(args.branch, args.directory, args.bundle)
