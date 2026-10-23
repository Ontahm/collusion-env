#!/bin/sh
# Is uv installed and recent enough? If not, say how to fix it for the way it was installed.
# Used by `make install` and before every make command (check-env). POSIX sh: macOS, Linux, Nix.
# uv >= 0.13.4 is required by the eMudhra/emSign CA advisory (SECURITY.md); pyproject.toml also
# sets it as uv's required-version.
MIN="0.13.4"

missing() {
  cat >&2 <<EOF
uv is not installed. It is the only tool this project needs (it installs Python and the dependencies).
  macOS (Homebrew):  brew install uv
  macOS or Linux:    curl -LsSf https://astral.sh/uv/install.sh | sh     (Astral's installer)
  with pipx:         pipx install uv
  Nix:               nix develop     (this repository's shell includes uv)
Then open a new terminal and run: make install
More: https://docs.astral.sh/uv/getting-started/installation/
EOF
  exit 1
}

command -v uv >/dev/null 2>&1 || missing
VERSION=$(uv --version 2>/dev/null | awk '{print $2}')
[ -n "$VERSION" ] || missing

# numeric comparison, field by field: exit 0 if VERSION >= MIN
if echo "$VERSION $MIN" | awk '{ n = split($1, v, "."); split($2, m, ".");
     for (i = 1; i <= 3; i++) { if (v[i] + 0 > m[i] + 0) exit 0; if (v[i] + 0 < m[i] + 0) exit 1 } exit 0 }'; then
  exit 0
fi

UV_PATH=$(command -v uv)
case "$UV_PATH" in
  /nix/store/*)               HOW="leave this shell and enter it again: exit, then nix develop (the flake pins a recent uv)" ;;
  *homebrew*|*/Cellar/*|*linuxbrew*) HOW="brew upgrade uv" ;;
  *pipx*)                     HOW="pipx upgrade uv" ;;
  "$HOME/.local/bin/uv"|"$HOME/.cargo/bin/uv") HOW="uv self update" ;;
  *)                          HOW="uv self update   (or: brew upgrade uv / pipx upgrade uv / pip install -U uv, depending on how you installed it)" ;;
esac
cat >&2 <<EOF
uv $VERSION is too old: this project needs uv >= $MIN (security fix, see SECURITY.md).
  Update it ($UV_PATH):  $HOW
Then run: make install
EOF
exit 1
