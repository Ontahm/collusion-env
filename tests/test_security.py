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
