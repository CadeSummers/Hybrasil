# SPDX-FileCopyrightText: 2026 Cade Summers
# SPDX-License-Identifier: AGPL-3.0-or-later
"""The web app as static files: every scene built ahead of time, no server.

    python -m hybrasil.cli --build-site site

writes

    site/index.html                  the viewer shell (web/app.py's, relative URLs)
    site/api/systems.json            the index /api/systems would serve
    site/api/systems/<slug>.json     one file per system, as /api/systems/<id>
    site/sky/milky_way_4k.jpg        the background Milky Way
    site/intro/*                     the intro's maps (web/intro/)
    site/llms.txt                    the canonical home, licences and citations (web/discovery.py)
    site/_headers, robots.txt, .nojekyll

so any static host can serve it -- Cloudflare Pages, or GitHub Pages as the
fallback -- under any path.  Every URL the page asks for is relative, and each
index entry carries the `url` of its scene file, so the browser never has to
turn a system id (``catalog:tau Cet``) into a file name itself.

The build is strict where the server is forgiving: a site without its catalog,
or with a system that failed to build, is not one to deploy, so either fails
the whole build.  Scenes start at the build time, like the server's; a weekly
rebuild keeps them current.
"""

from __future__ import annotations

import hashlib
import json
import os
import re
import shutil
from pathlib import Path
from typing import Callable, Optional

from ..viz.three_viewer import INTRO_DIR, SKY_DIR, SKY_FILE, intro_files
from . import discovery
from .app import SystemLibrary, app_page

API_DIR = "api"
SCENE_DIR = f"{API_DIR}/systems"
# Answered by the Cloudflare function functions/api/suggestions.js, not a file.
SUGGEST_PATH = f"{API_DIR}/suggestions"
# The Turnstile widget's site key (public by design); its secret is a
# Cloudflare secret the function reads.  Without one the form still shows,
# and the function refuses every submission.
SITEKEY_ENV = "HYBRASIL_TURNSTILE_SITEKEY"
INDEX_FILE = f"{API_DIR}/systems.json"
SKY_PATH = f"sky/{SKY_FILE}"
INTRO_PATH = "intro/"

# Cloudflare Pages reads this file; GitHub Pages ignores it.  Scenes change
# with each build, the sky never does, the intro's maps seldom.
HEADERS = f"""/*
  X-Content-Type-Options: nosniff
  Referrer-Policy: strict-origin-when-cross-origin
  Permissions-Policy: camera=(), microphone=(), geolocation=()

/{API_DIR}/*
  Cache-Control: public, max-age=3600

/sky/*
  Cache-Control: public, max-age=2592000

/intro/*
  Cache-Control: public, max-age=86400
"""

ROBOTS = "User-agent: *\nAllow: /\n"


class SiteBuildError(RuntimeError):
    """The site is incomplete and must not be deployed."""


def slug(system_id: str) -> str:
    """A file name for a system id: lower case, letters and digits, hyphens between.

    ``catalog:tau Cet`` -> ``catalog-tau-cet``.  An id with nothing usable in
    it falls back to a hash, so the result is never empty.
    """
    s = re.sub(r"[^a-z0-9]+", "-", system_id.lower()).strip("-")
    return s or hashlib.sha1(system_id.encode("utf-8")).hexdigest()[:10]


def scene_files(ids: list[str]) -> dict[str, str]:
    """{id: file name}, unique even where two ids slug alike.

    A clash takes a short hash of its id, so ``catalog:HD 1`` and
    ``catalog:hd-1`` do not overwrite each other -- including on the
    case-insensitive file systems of Windows and macOS.
    """
    counts: dict[str, int] = {}
    for i in ids:
        counts[slug(i)] = counts.get(slug(i), 0) + 1
    out = {}
    for i in ids:
        s = slug(i)
        if counts[s] > 1:
            s = f"{s}-{hashlib.sha1(i.encode('utf-8')).hexdigest()[:8]}"
        out[i] = f"{s}.json"
    if len(set(out.values())) != len(out):
        raise SiteBuildError("two systems map to the same scene file")
    return out


def _write_json(path: Path, value) -> int:
    data = json.dumps(value, separators=(",", ":"), ensure_ascii=False).encode("utf-8")
    path.write_bytes(data)
    return len(data)


def build_site(library: SystemLibrary, out_dir, initial: str = "solar", *,
               require_catalog: bool = True,
               progress: Optional[Callable[[int, int, str], None]] = None) -> dict:
    """Write the whole site into `out_dir`, replacing what is there.

    Returns a summary: system count, bytes written, the catalog's title.
    Raises SiteBuildError if the catalog did not load (unless
    `require_catalog` is false) or any system failed to build.
    """
    out = Path(out_dir)
    status = library.catalog_status()
    if require_catalog and not status["available"]:
        raise SiteBuildError(f"the catalog did not load: {status['error']}")
    index = library.index()
    if not any(e["id"] == initial for e in index):
        raise SiteBuildError(f"the initial system {initial!r} is not in the index")

    files = scene_files([e["id"] for e in index])
    if out.exists():
        shutil.rmtree(out)
    (out / SCENE_DIR).mkdir(parents=True)

    total = 0
    failed: list[str] = []
    for n, entry in enumerate(index, 1):
        if progress:
            progress(n, len(index), entry["id"])
        try:
            payload = library.scene(entry["id"])
        except Exception as e:                   # collect them all, then fail
            failed.append(f"{entry['id']}: {e.__class__.__name__}: {e}")
            continue
        total += _write_json(out / SCENE_DIR / files[entry["id"]], payload)
    if failed:
        raise SiteBuildError(f"{len(failed)} system(s) failed to build:\n  " + "\n  ".join(failed))

    # The index the server would send, each entry pointing at its file.  Only
    # the catalog's title goes out: the server's error text can name a path.
    systems = [dict(e, url=f"{SCENE_DIR}/{files[e['id']]}") for e in index]
    total += _write_json(out / INDEX_FILE, {
        "systems": systems,
        "catalog": {"available": status["available"], "title": status["title"], "error": None},
    })

    page = app_page(library, initial, api_base=API_DIR, index_url=INDEX_FILE, sky=SKY_PATH,
                    suggest_url=SUGGEST_PATH,
                    turnstile_sitekey=os.environ.get(SITEKEY_ENV) or None,
                    intro_base=INTRO_PATH)
    (out / "index.html").write_text(page, encoding="utf-8")
    total += len(page.encode("utf-8"))
    sky = SKY_DIR / SKY_FILE
    if sky.exists():
        (out / "sky").mkdir()
        shutil.copyfile(sky, out / SKY_PATH)
        total += sky.stat().st_size
    names = intro_files()
    if names:
        (out / INTRO_PATH).mkdir()
        for name in names:
            shutil.copyfile(INTRO_DIR / name, out / INTRO_PATH / name)
            total += (INTRO_DIR / name).stat().st_size
    (out / "_headers").write_text(HEADERS, encoding="utf-8")
    (out / "robots.txt").write_text(ROBOTS, encoding="utf-8")
    (out / discovery.LLMS_FILE).write_text(discovery.llms_txt(), encoding="utf-8")
    (out / ".nojekyll").write_text("", encoding="utf-8")   # GitHub Pages: serve as-is

    return {"systems": len(index), "bytes": total, "catalog": status["title"]}
