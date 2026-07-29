#!/usr/bin/env bash
# Write a secret into .env without it touching your shell history or your screen.
#
#   ./scripts/set-secret.sh POCKET_API_KEY
#
# Typing `POCKET_API_KEY=pk_live_...` at a prompt leaves the secret in ~/.bash_history,
# in your terminal scrollback, and in the process list. This reads it silently instead.
set -euo pipefail

KEY="${1:-}"
if [[ -z "$KEY" ]]; then
  echo "usage: $0 <ENV_VAR_NAME>" >&2
  echo "example: $0 POCKET_API_KEY" >&2
  exit 1
fi

cd "$(dirname "$0")/.."

if [[ ! -f .env ]]; then
  cp .env.example .env
  echo "created .env from .env.example"
fi
chmod 600 .env

# -s: no echo. -r: don't mangle backslashes.
printf 'Paste value for %s (input hidden): ' "$KEY"
read -rs VALUE
printf '\n'

if [[ -z "$VALUE" ]]; then
  echo "no value entered — nothing changed" >&2
  exit 1
fi

# Python rather than sed: a key can contain /, &, and other characters that would
# need escaping in a sed replacement, and getting that subtly wrong corrupts the file.
VALUE="$VALUE" KEY="$KEY" python3 - <<'PY'
import os, pathlib, re

key, value = os.environ["KEY"], os.environ["VALUE"]
path = pathlib.Path(".env")
lines = path.read_text().splitlines()

pattern = re.compile(rf"^\s*(?:export\s+)?{re.escape(key)}\s*=")
replaced = False
for i, line in enumerate(lines):
    if pattern.match(line):
        lines[i] = f"{key}={value}"
        replaced = True
        break

if not replaced:
    lines.append(f"{key}={value}")

path.write_text("\n".join(lines) + "\n")
print(f"{'updated' if replaced else 'added'} {key}")
PY

chmod 600 .env
LENGTH=${#VALUE}
PREFIX="${VALUE:0:6}"
echo ".env is 0600; ${KEY} set (${LENGTH} chars, starts '${PREFIX}…')"
echo
echo "verify it works:  make dev  &&  curl -s localhost:8000/api/v1/pocket/status | jq .check"
