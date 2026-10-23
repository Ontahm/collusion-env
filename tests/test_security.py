"""Security checks: the secret scanner catches what it should (fake keys are built at run time, so
this file holds no key-shaped text), the repository itself is clean, and the pinned tools meet
the minimum versions of SECURITY.md."""

import importlib.util
import re
import subprocess
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
spec = importlib.util.spec_from_file_location("check_secrets", ROOT / "scripts" / "check_secrets.py")
check_secrets = importlib.util.module_from_spec(spec)
spec.loader.exec_module(check_secrets)


def fake(prefix: str, n: int = 32) -> str:
    return prefix + "Ab3" * (n // 3 + 1)


@pytest.fixture
def repo(tmp_path, monkeypatch):
    """A throwaway git repository the scanner treats as the project root."""
    subprocess.run(["git", "init", "-q", str(tmp_path)], check=True)
    monkeypatch.setattr(check_secrets, "ROOT", tmp_path)
    return tmp_path


def stage(repo: Path, name: str, text: str) -> None:
    (repo / name).write_text(text)
    subprocess.run(["git", "add", name], cwd=repo, check=True)


def test_staged_keys_are_refused(repo):
    stage(repo, "a.py", f'key = "{fake("sk-proj-")}"\n')
    stage(repo, "b.md", f"modal token {fake('ak-', 20)}\n")
    stage(repo, "c.txt", "-----BEGIN OPENSSH " + "PRIVATE KEY-----\n")
    found = check_secrets.scan(staged=True)
    assert any("a.py:1" in p and "OpenAI" in p for p in found)
    assert any("b.md:1" in p and "Modal" in p for p in found)
    assert any("c.txt:1" in p and "private key" in p for p in found)


def test_env_values_and_env_file_are_refused(repo):
    value = fake("", 24)
    stage(repo, ".env", f"MODAL_VLLM_API_KEY={value}\nCOLLUSION_LOG_LEVEL=verbose\n")
    stage(repo, "notes.md", f"the endpoint key is {value}\n")
    found = check_secrets.scan(staged=True)
    assert any("notes.md:1" in p and "MODAL_VLLM_API_KEY" in p for p in found)
    assert any(p.startswith(".env:") for p in found)
    assert not any("COLLUSION_LOG_LEVEL" in p for p in found)       # settings are not secrets


def test_clean_changes_and_ignored_lines_pass(repo):
    stage(repo, "ok.py", 'headers["Authorization"] = f"Bearer {key}"\n')
    stage(repo, "doc.md", f"example: {fake('sk-')}  <!-- secret-check: ignore -->\n")
    assert check_secrets.scan(staged=True) == []


def test_the_repository_holds_no_secret():
    assert check_secrets.scan(staged=False) == [], "make check-secrets"


def test_pinned_tools_meet_the_advisory_minimums():
    flake = (ROOT / "flake.nix").read_text()
    uv = tuple(int(x) for x in re.search(r'pname = "uv";\s*version = "([\d.]+)"', flake).group(1).split("."))
    assert uv >= (0, 13, 4)
    assert "emSign Root CA - G1" in flake and "SSL_CERT_FILE" in flake
    lock = (ROOT / "uv.lock").read_text()
    certifi = re.search(r'name = "certifi"\nversion = "([\d.]+)"', lock).group(1)
    assert tuple(int(x) for x in certifi.split(".")) >= (2026, 10, 19)
    assert 'required-version = ">=0.13.4"' in (ROOT / "pyproject.toml").read_text()


vspec = importlib.util.spec_from_file_location("verify_installed", ROOT / "scripts" / "verify_installed.py")
verify_installed = importlib.util.module_from_spec(vspec)
vspec.loader.exec_module(verify_installed)


def test_verify_installed_reads_records_and_hashes_like_pip():
    """Offline part of scripts/verify_installed.py (the PyPI comparison needs the network)."""
    rec = verify_installed.record("pkg/__init__.py,sha256=abc,10\npkg-1.0.dist-info/RECORD,,\n")
    assert rec == {"pkg/__init__.py": "sha256=abc"}                 # RECORD itself has no hash
    assert verify_installed.b64sha256(b"") == "sha256=47DEQpj8HBSa-_TImW-5JCeuQeRkm5NMpJWZG3hSuFU"


def _check_uv(tmp_path, fake_uv_dir=None, version=None):
    """Run scripts/check_uv.sh with only a fake uv (or none) on the PATH, plus the system tools it uses."""
    import os
    import shutil
    tools = {os.path.dirname(shutil.which(t)) for t in ("sh", "awk", "cat")}
    path = list(tools)
    if fake_uv_dir is not None:
        fake_uv_dir.mkdir(parents=True, exist_ok=True)
        uv = fake_uv_dir / "uv"
        uv.write_text(f"#!/bin/sh\necho 'uv {version} (x86_64-unknown-linux-gnu)'\n")
        uv.chmod(0o755)
        path.insert(0, str(fake_uv_dir))
    env = {"PATH": ":".join(path), "HOME": str(tmp_path / "home")}
    r = subprocess.run(["sh", str(ROOT / "scripts" / "check_uv.sh")], env=env, capture_output=True, text=True)
    return r.returncode, r.stderr


def test_check_uv_explains_how_to_install_or_update(tmp_path):
    code, msg = _check_uv(tmp_path)                                               # no uv at all
    if code == 0:
        pytest.skip("a uv is installed system-wide here: cannot hide it")
    assert code == 1 and "brew install uv" in msg and "astral.sh/uv/install.sh" in msg and "make install" in msg
    assert _check_uv(tmp_path, tmp_path / "ok" / "bin", "0.13.4")[0] == 0              # the minimum
    assert _check_uv(tmp_path, tmp_path / "ok2" / "bin", "0.14.0")[0] == 0
    assert _check_uv(tmp_path, tmp_path / "ok3" / "bin", "1.0.0")[0] == 0
    for where, version, advice in ((tmp_path / "opt" / "homebrew" / "bin", "0.11.21", "brew upgrade uv"),
                                   (tmp_path / "pipx" / "venvs" / "uv" / "bin", "0.13.3", "pipx upgrade uv"),
                                   (tmp_path / "home" / ".local" / "bin", "0.9.0", "uv self update"),
                                   (tmp_path / "elsewhere" / "bin", "0.12.99", "uv self update   (or: brew upgrade uv")):
        code, msg = _check_uv(tmp_path, where, version)
        assert code == 1 and f"uv {version} is too old" in msg and advice in msg and "make install" in msg, (where, msg)
