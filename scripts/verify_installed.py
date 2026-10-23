#!/usr/bin/env python3
"""Check that the packages installed in a Python environment are PyPI's official files.

    <environment's python> scripts/verify_installed.py
    e.g. ~/.local/share/uv/tools/modal/bin/python scripts/verify_installed.py     # the Modal CLI
         .venv/bin/python scripts/verify_installed.py                             # the project
         python3 scripts/verify_installed.py --path DIR [DIR ...]                 # unpacked packages
                                                       # (e.g. folders of uv's cache: archive-v0/<id>)

For each installed package: (1) every installed file still has the hash recorded when it was
installed (nothing modified since), and (2) that record matches the RECORD inside the official
wheel on PyPI for the same version and platform (the download was not tampered with). Standard
library only; downloads each wheel once (a few MB per package).
"""

from __future__ import annotations

import base64
import hashlib
import importlib.metadata as md
import io
import json
import sys
import urllib.request
import zipfile
from pathlib import Path

SKIP = {"INSTALLER", "REQUESTED", "RECORD", "direct_url.json", "uv_cache.json", "uv_build.json"}


def b64sha256(data: bytes) -> str:
    return "sha256=" + base64.urlsafe_b64encode(hashlib.sha256(data).digest()).rstrip(b"=").decode()


def record(text: str) -> dict:
    out = {}
    for line in text.splitlines():
        parts = line.rsplit(",", 2)
        if len(parts) == 3 and parts[1]:
            out[parts[0]] = parts[1]
    return out


def official_record(name: str, version: str, tags: set) -> tuple:
    with urllib.request.urlopen(f"https://pypi.org/pypi/{name}/{version}/json", timeout=60) as r:
        files = json.load(r)["urls"]
    for f in files:
        if f["packagetype"] != "bdist_wheel":
            continue
        stem = f["filename"][:-4].split("-")
        wheel_tags = {f"{py}-{abi}-{plat}" for py in stem[-3].split(".") for abi in stem[-2].split(".")
                      for plat in stem[-1].split(".")}
        if wheel_tags & tags:
            with urllib.request.urlopen(f["url"], timeout=120) as r:
                data = r.read()
            if hashlib.sha256(data).hexdigest() != f["digests"]["sha256"]:
                return None, f"{f['filename']}: download does not match PyPI's hash"
            z = zipfile.ZipFile(io.BytesIO(data))
            # the wheel's own record, at the top level (vendored packages inside it have their own)
            rec = next(n for n in z.namelist() if n.endswith(".dist-info/RECORD") and n.count("/") == 1)
            return record(z.read(rec).decode()), f["filename"]
    return None, "no official wheel for this platform (built from source: not checkable this way)"


def main() -> int:
    import argparse
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--path", nargs="+", help="check the packages unpacked in these folders instead")
    args = parser.parse_args()
    bad = 0
    found = md.distributions(path=args.path) if args.path else md.distributions()
    dists = sorted(found, key=lambda d: d.metadata["Name"].lower())
    for d in dists:
        name, version = d.metadata["Name"], d.version
        # (1) installed files unchanged since install
        modified = [str(f) for f in (d.files or []) if f.hash and f.hash.mode == "sha256"
                    and Path(d.locate_file(f)).is_file()
                    and b64sha256(Path(d.locate_file(f)).read_bytes()) != f"sha256={f.hash.value}"]
        # (2) install record = the official wheel's record
        tags = {line.split(":", 1)[1].strip() for line in (d.read_text("WHEEL") or "").splitlines() if line.startswith("Tag:")}
        installed = record(d.read_text("RECORD") or "")
        try:
            official, source = official_record(name, version, tags)
        except Exception as exc:                       # network, unknown package...
            official, source = None, f"could not check: {type(exc).__name__}: {exc}"
        differ, extra = [], []
        if official is not None:
            official_hashes = set(official.values())
            launchers = {e.name for e in d.entry_points if e.group in ("console_scripts", "gui_scripts")}

            def generated(path: str) -> bool:      # written by the installer, not part of any wheel
                return Path(path).name in SKIP or path.endswith(".pyc") or "/__pycache__/" in f"/{path}"

            if args.path:                          # an unpacked folder: every file physically present
                base = Path(d.locate_file(""))
                present = [str(f.relative_to(base)) for f in base.rglob("*") if f.is_file()]
            else:                                  # an environment: every file the install recorded
                present = list(installed)
            for path in present:
                if generated(path) or path in official:
                    continue
                if path.startswith("../") and installed.get(path) in official_hashes:
                    continue                       # a .data file installed outside site-packages
                if path.startswith("../") and Path(path).parent.name == "bin" and Path(path).name in launchers:
                    continue                       # a launcher the installer wrote for a declared entry point
                extra.append(path)
            installed_hashes = set(installed.values())
            for path, h in official.items():
                if Path(path).name in SKIP or path.endswith(".pyc"):
                    continue
                if ".data/" in path:                   # installed under another prefix: compare by hash
                    if h not in installed_hashes:
                        differ.append(path)
                elif installed.get(path) != h:
                    differ.append(path)
        if modified or differ or extra:
            bad += 1
            print(f"FAIL {name} {version}: {len(modified)} files modified since install, {len(differ)} files differ from "
                  f"{source}, {len(extra)} files not in it")
            for p in (modified + differ + extra)[:5]:
                print(f"       {p}")
        elif official is None:
            print(f"?    {name} {version}: {source}")
        else:
            print(f"ok   {name} {version} = {source}")
    print(f"\n{len(dists)} packages, {bad} failed" + ("" if bad else ": every checked file is PyPI's official file"))
    return 1 if bad else 0


if __name__ == "__main__":
    sys.exit(main())
