"""
Growth Engine POC — start here.

    python backend/main.py

This file does one thing before anything else: it loads the brand pack. The demo company
in this repository is fictional. If brand/local.json exists, its names are substituted
into the application as it is imported — see brand.py. Nothing else in the application
may be imported before that has happened, which is why the application itself lives in
app.py and this launcher is so short.
"""
import os, sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import brand

brand.install()

from app import app, banner      # noqa: E402  (must follow brand.install)

if __name__ == "__main__":
    import uvicorn
    port = int(os.environ.get("PORT", "8000"))
    banner(port)
    uvicorn.run(app, host="127.0.0.1", port=port)
