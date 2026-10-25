# Security

What protects this repository, what each person sets up once, and the advisories checked. Last
review: 23 Oct 2026.

## Once per person

```bash
make install    # checks uv, installs the locked dependencies, the git hook and a private .env
```

- uv is the only tool to install yourself; it installs Python. Every `make` command checks that uv
  is 0.13.4 or later and says how to update it for the way you installed it. `pyproject.toml` also
  makes older uv refuse to run.
- Nix: run `nix develop` first. Its shell adds uv 0.13.5 and, for curl and git, a certificate bundle
  without the eMudhra/emSign roots.
- Elsewhere: Python's HTTPS (every model call) uses certifi 2026.10.23 from `uv.lock`. curl, git and
  your browser use your system's certificates: keep macOS or your Linux distribution up to date.

## What is in place

| Protection | Where |
|---|---|
| every dependency file is checked against its SHA-256 in `uv.lock`; `make` runs `uv run --locked`, so dependencies never change silently | `uv.lock`, `Makefile` |
| uv 0.13.4 or later is required; the Nix shell pins Astral's uv 0.13.5 binary by its SHA-256 | `pyproject.toml`, `flake.nix`, `scripts/check_uv.sh` |
| in the Nix shells, curl, git and OpenSSL distrust the four emSign roots | `flake.nix` (`cacert-safe`) |
| Python HTTPS trusts certifi 2026.10.23, on every system | `uv.lock` |
| no secret reaches git: a pre-commit hook scans staged changes; `make check-secrets` and `make test` scan every tracked file (API keys, tokens, private keys, the values of `.env`; `.env` itself is refused) | `scripts/check_secrets.py`, `.githooks/` |
| keys live only in `.env` (not in git); runs record the name of the key variable, never its value | `.gitignore`, `agents/llm.py` |
| the local model server only listens on 127.0.0.1 | `scripts/serve.sh` |
| the Modal server refuses requests without its key (check after each deploy: `curl` must print 401); the key never appears on vLLM's command line, which vLLM logs | `deploy/modal_vllm.py`, [run on Modal](docs/how-to/run-on-modal.md#security) |
| downloaded model files are checked against `deploy/local-weights/SHA256SUMS` | `make models` |

## Advisories checked

| Advisory | Status |
|---|---|
| eMudhra/emSign certificate keys compromised (Oct 2026; minimums: certifi 2026.10.19, uv 0.13.4, pip 26.2.2). Fake HTTPS certificates could impersonate sites. | Mitigated: certifi 2026.10.23 in `uv.lock`; uv 0.13.5 in the Nix shell; the four emSign roots distrusted in the shell's certificate bundle. None of PyPI, GitHub, Hugging Face, OpenAI or Modal uses them. pip is not used. On your machine: update NixOS (its system certificates) and any Python outside the Nix shell (certifi, pip). |
| CVE-2026-114583: CPython `tarfile` with `filter="tar"` can write outside the target folder. | Not exposed: nothing here unpacks tar archives with Python. No fixed Python release on 23 Oct; update Python when one reaches nixpkgs. Code that unpacks archives must use `filter="data"` and trusted, checksummed files. |

## Checking that installed code is official

`scripts/verify_installed.py` checks an installed Python environment, or uv's cache, against PyPI:
every file unchanged since installation, identical to the official package, no extra file (such as
a planted `.pth`). Standard library only.

```bash
.venv/bin/python scripts/verify_installed.py                                   # the project
~/.local/share/uv/tools/modal/bin/python scripts/verify_installed.py           # the modal command
python3 scripts/verify_installed.py --path "$(uv cache dir)"/archive-v0/*       # everything uv unpacked
```

"0 failed" means every checked file is PyPI's. `?` marks a package built from source, which this
check cannot compare (`uv.lock` pins its source hash). A package installed from a local folder
differs from PyPI's of the same name; that is expected. Run on 23 Oct after the emSign advisory:
every package was official.

## Keys and accounts

| Secret | Where | If it leaks |
|---|---|---|
| `OPENAI_API_KEY` | `.env` | revoke it in OpenAI's dashboard; use a key with a monthly limit |
| `MODAL_VLLM_API_KEY` (protects your Modal server) | `.env` and the Modal secret `collusion-vllm` | `make modal-setup` makes a new one |
| Modal account token | `~/.modal.toml` (outside the repository) | revoke it in Modal's dashboard, then `modal setup` |

- Never paste a key in a chat, an issue, a commit or a log. Share keys through a password manager
  only.
- Keep your Modal server URL private: without the key a request is refused, but it still wakes a
  billed GPU for 15 minutes. `make modal-run` stops the server at the end.
- Set a spending limit on paid accounts.

## Shared runs

`runs/` is in git and shared. It holds model outputs and local paths (`/home/<user>/...`), no keys
(checked by the hook and the tests). Before making a run public, run `make check-secrets` and
remove the local paths.

## Reporting

A leaked key or a vulnerability: tell the team privately, replace the key, then fix the cause.
