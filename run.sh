#!/usr/bin/env bash
# Growth Engine POC — install what it needs, start it, open the browser.
set -e
cd "$(dirname "$0")"

PY=python3
command -v "$PY" >/dev/null 2>&1 || PY=python
command -v "$PY" >/dev/null 2>&1 || { echo "Python 3.9 or later is needed: https://www.python.org/downloads/"; exit 1; }

echo
echo "  Growth Engine POC — contact centre AI"
echo
echo "  [1/3] Installing dependencies"
"$PY" -m pip install -r requirements.txt --quiet --disable-pip-version-check

echo "  [2/3] Configuration"
if [ -n "$ANTHROPIC_API_KEY" ]; then
  echo "        Claude: on — live analysis layered over the engine's"
else
  echo "        Claude: off — everything works without it"
fi
if [ "$CUSTOMER_PLATFORM" = "unomi" ]; then
  echo "        Customer platform: Apache Unomi — start it from platform/ first"
else
  echo "        Customer platform: built-in store"
fi

PORT="${PORT:-8000}"
echo "  [3/3] Starting at http://localhost:$PORT   (Ctrl+C to stop)"
( sleep 2; (open "http://localhost:$PORT" || xdg-open "http://localhost:$PORT") >/dev/null 2>&1 ) &
exec "$PY" backend/main.py
