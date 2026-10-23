# Security

What protects this repository, what each person sets up once, and the advisories we have checked.
Last review: 23 Oct 2026.

## Once per person

```bash
make install        # any OS: checks uv, installs the locked dependencies, the git hook, a private .env
```

- **uv** is the only tool to install yourself (it brings Python). `make install` and every other
  `make` command check it is >= 0.13.4 and, if not, say how to install or update it for the way you
  installed it (Homebrew, Astral's installer, pipx, Nix). `pyproject.toml` also makes older uv refuse
  to run.
- **Nix users:** `nix develop` first. Its shell adds uv 0.13.5 and, for curl and git, a certificate
  bundle without the eMudhra/emSign roots.
- **Everyone else:** Python's HTTPS (every model call) is protected by certifi 2026.10.23 from
  `uv.lock`. curl, git and your browser use your operating system's certificate store, which this
  repository cannot change: keep macOS or your Linux distribution up to date.

## What is in place

| Protection | Where |
|---|---|
| Every dependency file is checked against a SHA-256 in `uv.lock`; `make` runs `uv run --locked`, so dependencies never change silently | `uv.lock`, `Makefile` |
| uv >= 0.13.4 is required; the Nix shell pins Astral's official uv 0.13.5 binary by its published SHA-256 | `pyproject.toml`, `flake.nix` |
| curl, git and OpenSSL in the Nix shells use a certificate bundle where the four emSign roots are explicitly distrusted (outside Nix: your system's store) | `flake.nix` (`cacert-safe`) |
| Python HTTPS (httpx, used for every model API) trusts certifi 2026.10.23, on every OS | `uv.lock` |
| uv >= 0.13.4 is checked before every make command, with the fix for your install | `scripts/check_uv.sh` |
| No secret reaches git: a pre-commit hook scans staged changes; `make check-secrets` and `make test` scan every tracked file (API keys, tokens, private keys, the values of `.env`; `.env` itself is refused) | `scripts/check_secrets.py`, `.githooks/` |
| Keys live only in `.env` (git-ignored); runs record the name of the key variable, never its value | `.gitignore`, `agents/llm.py` |
| The local model server only listens on 127.0.0.1 (it refuses other addresses) | `scripts/serve.sh` |
| The Modal endpoint refuses requests without its key (check after each deploy: `curl` must print 401); the key reaches vLLM by environment, never on its command line (vLLM logs its arguments) | `deploy/README.md`, `deploy/modal_vllm.py` |
| Model files are checked against `models/SHA256SUMS` after download | `Makefile` (`make models`) |

## Advisories checked

| Advisory | Status for this repository |
|---|---|
| **eMudhra/emSign CA keys compromised** (Oct 2026; minimums: certifi >= 2026.10.19, uv >= 0.13.4, pip >= 26.2.2). Fake HTTPS certificates could impersonate sites and intercept traffic. | **Mitigated.** certifi 2026.10.23 in `uv.lock`; uv 0.13.5 in the Nix shell; the four emSign roots distrusted in the shell's certificate bundle (a superset of every certifi decision so far: 2026.10.19 kept three of them, 2026.10.23 keeps one; none of PyPI, GitHub, Hugging Face, OpenAI or Modal uses them). We do not use pip. **Your machine:** update NixOS (its system certificate store), and anything outside the Nix shell that uses Python packages (certifi, pip). |
| **CVE-2026-114583**: CPython `tarfile` extraction with `filter="tar"` can write outside the destination (crafted symlinks). | **No exposure.** Nothing here extracts tar archives with Python (uv and Nix use their own extraction; our only dependency mentioning tarfile is a pygments maintainer script that never runs). No fixed Python release yet (CPython issue still open on 23 Oct); update Python when one reaches nixpkgs. If you add code that unpacks archives, use `filter="data"` and only trusted, checksummed sources. |

## Checking that installed code is official

`scripts/verify_installed.py` checks an installed Python environment, or uv's cache, against PyPI:
every file unchanged since installation, identical to the official wheel, and no extra file (such
as a planted `.pth`). Standard library only; it downloads each official wheel once.

```bash
.venv/bin/python scripts/verify_installed.py                                   # the project
~/.local/share/uv/tools/modal/bin/python scripts/verify_installed.py           # the Modal command
python3 scripts/verify_installed.py --path "$(uv cache dir)"/archive-v0/*       # everything uv unpacked
```

"0 failed" means every checked file is PyPI's. `?` marks a package built from source (not checkable
this way; `uv.lock` pins its source archive's hash). A local build (for example a package installed
from a folder) differs from PyPI's upload of the same name: expected, not tampering. Used on 23 Oct
after the eMudhra/emSign advisory: every package on the machine was official.

## Keys and accounts

| Secret | Where | If it leaks |
|---|---|---|
| `OPENAI_API_KEY` | `.env` | revoke it in OpenAI's dashboard; use a project key with a monthly limit |
| `MODAL_VLLM_API_KEY` (protects the Modal endpoint) | `.env` and the Modal secret `collusion-vllm` | replace it: `deploy/README.md`, "Security notes" |
| Modal account token | `~/.modal.toml` (outside the repo; `chmod 600`) | revoke it in Modal's dashboard, then `modal setup` |

- Never paste a key in a chat, an issue, a commit or a run log. Share a key with a teammate through a
  password manager only.
- Keep the Modal endpoint URL private: a request without the key is refused, but it can still wake a
  billed GPU for 15 minutes. Stop the server after a session (`scripts/modal_session.sh` does it).
- Set a spending limit on paid accounts (or use a virtual card with a low limit).

## Shared runs

`runs/` is committed and shared. It holds model outputs and local paths (`/home/<user>/...`), no
keys (checked by the hook and the tests). Before making any run public, run `make check-secrets`
again and remove the local paths.

## Reporting

Something that looks like a leaked key or a vulnerability: tell the team privately first, rotate the
key, then fix the cause.
