"""
BRAND PACKS — who the demo company is.

The company in this repository is fictional. It is called Acme, it sells creative
software by subscription, and its products have invented names. That is what you get
when you clone the repository and run it.

To show the demo as a real company, you do not edit the code. You add a brand pack:

    brand/default.json     committed     the fictional company, as shipped
    brand/local.json       NOT committed your company: its names, its logo, its endpoints

A brand pack is mostly a dictionary — placeholder on the left, the name to show on the
right:

    "names": { "Acme": "Your Company", "PhotoForge": "Your Photo Product" }

When a local pack is present, install() substitutes those names into the application's
own source as it is imported, and into the page as it is served. Every figure, every
decision and every sentence is otherwise identical; only the names change. With no local
pack nothing is substituted and nothing here runs: the code you read is the code that
executes.

    BRAND_PACK=default          ignore brand/local.json
    BRAND_PACK=path/to/x.json   use that pack

Names are matched as whole words and are case-sensitive, so "Acme" never matches inside
"AcmeMark". Keep placeholders distinctive — a placeholder that is also an ordinary word
would be replaced wherever that word appears.
"""
import importlib.abc, importlib.util, json, os, re, sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
DEFAULT = ROOT / "brand" / "default.json"
LOCAL = ROOT / "brand" / "local.json"

_pack = None
_pattern = None
_installed = False

# A name is substituted into source code and into a web page, so it must be inert in both.
_UNSAFE = re.compile(r"""["'\\<>{}`$\n\r]""")


def _load():
    base = json.loads(DEFAULT.read_text(encoding="utf-8")) if DEFAULT.is_file() else {}
    choice = os.environ.get("BRAND_PACK", "").strip()
    path = None
    if choice.lower() == "default":
        path = None
    elif choice:
        path = Path(choice)
        if not path.is_file():
            raise FileNotFoundError("BRAND_PACK points at %s, which does not exist" % path)
    elif LOCAL.is_file():
        path = LOCAL
    pack = dict(base)
    pack["source"] = "default"
    if path:
        over = json.loads(path.read_text(encoding="utf-8"))
        for k, v in over.items():
            if isinstance(v, dict) and isinstance(pack.get(k), dict):
                pack[k] = {**pack[k], **v}
            else:
                pack[k] = v
        pack["source"] = path.name
    for k, v in (pack.get("names") or {}).items():
        if _UNSAFE.search(k) or _UNSAFE.search(str(v)):
            raise ValueError("Brand pack name %r -> %r contains a character that is not allowed "
                             "(quotes, backslash, angle brackets, braces, backtick, $)" % (k, v))
    return pack


def pack():
    global _pack
    if _pack is None:
        _pack = _load()
    return _pack


def _compile():
    """One pattern for every name, longest first, so 'Acme Cloud' wins over 'Acme'."""
    global _pattern
    names = pack().get("names") or {}
    if not names:
        _pattern = False
        return
    keys = sorted(names, key=lambda k: -len(k))
    # A boundary is anything that is not a letter, digit or underscore — except that a
    # placeholder which itself starts with an underscore may follow a quote or a dot.
    _pattern = re.compile("(?<![A-Za-z0-9_])(" + "|".join(re.escape(k) for k in keys) + ")(?![A-Za-z0-9_])")


def active():
    """True when a pack is substituting names."""
    if _pattern is None:
        _compile()
    return bool(_pattern)


def apply(text):
    """Substitute the pack's names into a piece of text."""
    if not active():
        return text
    names = pack()["names"]
    return _pattern.sub(lambda m: names[m.group(1)], text)


def vendor_api():
    """How to reach the vendor's customer data platform. Placeholders unless a pack says otherwise."""
    return dict(pack().get("vendor_api") or {})


def public():
    """What the page needs to draw the brand: the marks, and nothing secret."""
    p = pack()
    return {"logo": p.get("logo"), "partner": p.get("partner"), "source": p.get("source")}


# ══════════════════════════════════════════════════════════════════════════════
#  IMPORT HOOK — only ever installed when a pack has names to substitute
# ══════════════════════════════════════════════════════════════════════════════
class _Loader(importlib.abc.SourceLoader):
    """Loads a module from this folder with the pack's names substituted. It offers no
    modification time, so nothing is written to or read from __pycache__: a cached module
    compiled under one brand can never be served under another."""

    def __init__(self, path):
        self.path = path

    def get_filename(self, fullname):
        return self.path

    def get_data(self, path):
        with open(path, "rb") as f:
            data = f.read()
        if os.path.normcase(path) == os.path.normcase(self.path):
            return apply(data.decode("utf-8")).encode("utf-8")
        return data


class _Finder(importlib.abc.MetaPathFinder):
    def find_spec(self, fullname, path=None, target=None):
        if "." in fullname or fullname == "brand":
            return None
        candidate = HERE / (fullname + ".py")
        if not candidate.is_file():
            return None
        return importlib.util.spec_from_file_location(fullname, str(candidate), loader=_Loader(str(candidate)))


def install():
    """Call once, before importing any other module from this folder."""
    global _installed
    if _installed or not active():
        return active()
    sys.meta_path.insert(0, _Finder())
    _installed = True
    return True
