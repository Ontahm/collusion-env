#!/usr/bin/env python3
"""Refuse secrets in git: API keys, tokens, private keys, and the values of .env.

    python3 scripts/check_secrets.py            # every tracked file (also: make check-secrets, make test)
    python3 scripts/check_secrets.py --staged   # what is about to be committed (the pre-commit hook)

Installed as a pre-commit hook by `make hooks` (git config core.hooksPath .githooks). Standard
library only. It looks for:
  - the values of the keys in .env (any variable whose name contains KEY, TOKEN or SECRET);
  - known key formats: OpenAI (sk-...), Modal tokens (ak-/as-...), Hugging Face (hf_...), GitHub
    (ghp_/github_pat_...), AWS (AKIA...), bearer tokens, PEM private keys;
  - files that must never be committed: .env, .modal.toml, private SSH keys.
A false positive can be allowed for one line by adding the comment `secret-check: ignore`.
It also warns when .env can be read by other users (chmod 600 .env).
"""

from __future__ import annotations

import argparse
import os
import re
import stat
import subprocess
import sys
from pathlib import Path
from typing import Dict, Iterable, List, Tuple

ROOT = Path(__file__).resolve().parent.parent
PATTERNS = {
    "OpenAI-style key": re.compile(rb"\bsk-(?:proj-)?[A-Za-z0-9_-]{20,}"),
    "Modal token": re.compile(rb"\ba[ks]-[A-Za-z0-9]{16,}"),
    "Hugging Face token": re.compile(rb"\bhf_[A-Za-z0-9]{30,}"),
    "GitHub token": re.compile(rb"\b(?:ghp|gho|ghu|ghs|ghr)_[A-Za-z0-9]{30,}|\bgithub_pat_[A-Za-z0-9_]{40,}"),
    "AWS access key": re.compile(rb"\bAKIA[0-9A-Z]{16}\b"),
    "bearer token": re.compile(rb"Bearer [A-Za-z0-9._~+/-]{20,}"),
    "private key": re.compile(rb"-----BEGIN (?:[A-Z]+ )?PRIVATE KEY-----"),
}
FORBIDDEN_NAMES = {".env", ".modal.toml", "id_rsa", "id_ed25519", "id_ecdsa"}
IGNORE = b"secret-check: ignore"


def env_secrets() -> Dict[str, bytes]:
    """Values of the secret-looking variables in .env (never printed)."""
    out: Dict[str, bytes] = {}
    path = ROOT / ".env"
    if not path.exists():
        return out
    for line in path.read_text(errors="replace").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.removeprefix("export ").split("=", 1)
        value = value.split(" #", 1)[0].strip().strip("'\"")
        if value and len(value) >= 8 and any(w in key.upper() for w in ("KEY", "TOKEN", "SECRET")):
            out[key.strip()] = value.encode()
    return out


def git(*args: str) -> bytes:
    return subprocess.run(["git", *args], cwd=ROOT, check=True, capture_output=True).stdout


def files(staged: bool) -> Iterable[Tuple[str, bytes]]:
    if staged:
        names = git("diff", "--cached", "--name-only", "--diff-filter=ACMR", "-z").split(b"\0")
        for name in filter(None, names):
            yield name.decode(), git("show", f":{name.decode()}")
    else:
        for name in filter(None, git("ls-files", "-z").split(b"\0")):
            path = ROOT / name.decode()
            if path.is_file():
                yield name.decode(), path.read_bytes()


def scan(staged: bool) -> List[str]:
    secrets = env_secrets()
    problems = []
    for name, data in files(staged):
        if Path(name).name in FORBIDDEN_NAMES:
            problems.append(f"{name}: this file must never be committed")
            continue
        for lineno, line in enumerate(data.splitlines(), 1):
            if IGNORE in line:
                continue
            for what, value in secrets.items():
                if value in line:
                    problems.append(f"{name}:{lineno}: the value of {what} from .env")
            for what, rx in PATTERNS.items():
                if rx.search(line):
                    problems.append(f"{name}:{lineno}: looks like a {what}")
    return problems


def env_permissions_warning() -> str:
    path = ROOT / ".env"
    if path.exists() and path.stat().st_mode & (stat.S_IRGRP | stat.S_IROTH):
        return "warning: .env can be read by other users on this machine: chmod 600 .env"
    return ""


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--staged", action="store_true", help="check what is staged for commit")
    args = parser.parse_args(argv)
    problems = scan(args.staged)
    warning = env_permissions_warning()
    if warning:
        print(warning, file=sys.stderr)
    if problems:
        print("Secret check failed: nothing was committed." if args.staged else "Secret check failed:", file=sys.stderr)
        for p in problems:
            print("  " + p, file=sys.stderr)
        print("Remove the secret (keys belong in .env, which git ignores). A false positive: add the comment "
              "'secret-check: ignore' on that line.", file=sys.stderr)
        return 1
    print(f"secret check: ok ({'staged changes' if args.staged else 'all tracked files'})")
    return 0


if __name__ == "__main__":
    sys.exit(main())
