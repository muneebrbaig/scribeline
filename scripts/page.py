#!/usr/bin/env python3
"""Fill a page template and write it to a GitLab wiki with checks after every write.

  page.py fill TEMPLATE --map MAP.json --out FILE
  page.py gitlab put    --repo OWNER/REPO --title "Section/Name" --file FILE [--host H]
  page.py gitlab list   --repo OWNER/REPO [--host H]
  page.py gitlab delete --repo OWNER/REPO --slug "Section/Name" [--host H]

`fill` replaces {{key}} placeholders from a JSON map. It fails on a leftover placeholder or an
empty result, so a broken substitution can never reach the wiki as an empty page.

`put` creates or updates one page. It always sends the title (a PUT without one moves the page to
the wiki root), then reads the page back and checks the slug, a non-empty body and the wiki
listing. Exit 0 only when every check passes. Output is one JSON object.
"""
import argparse
import json
import os
import re
import subprocess
import sys
from urllib.parse import quote

MAX_ARG_BYTES = 200_000
PLACEHOLDER = re.compile(r"\{\{\s*([A-Za-z0-9_.-]+)\s*\}\}")


def run(cmd):
    try:
        p = subprocess.run(cmd, capture_output=True, text=True, timeout=60)
        return p.returncode, p.stdout, p.stderr
    except (OSError, subprocess.TimeoutExpired) as e:
        return 127, "", str(e)


def fill(template, values):
    """Return text with {{key}} replaced. Raises ValueError on a missing key or empty result."""
    missing = sorted({k for k in PLACEHOLDER.findall(template) if k not in values})
    if missing:
        raise ValueError(f"no value for placeholder(s): {', '.join(missing)}")
    text = PLACEHOLDER.sub(lambda m: str(values[m.group(1)]), template)
    if not text.strip():
        raise ValueError("result is empty")
    return text


def slugify(title):
    """GitLab keeps path segments and turns spaces into hyphens."""
    return "/".join(p.strip().replace(" ", "-") for p in title.strip("/").split("/"))


def api(host, path, *args):
    cmd = ["glab", "api", path, "--hostname", host, *args]
    code, out, err = run(cmd)
    if code != 0:
        raise RuntimeError(f"glab api {path} failed: {(out + err).strip()[:300]}")
    try:
        return json.loads(out) if out.strip() else None
    except ValueError:
        raise RuntimeError(f"glab api {path} returned unreadable output")


def project(repo):
    return f"projects/{repo.replace('/', '%2F')}"


def list_slugs(host, repo):
    return [p["slug"] for p in api(host, f"{project(repo)}/wikis") or []]


def put(host, repo, title, content):
    """Create or update a page, then verify. Returns the result dict. ok is False on any failed check."""
    if not content.strip():
        return {"ok": False, "checks": {"body_not_empty": False}, "error": "refusing to write an empty body"}
    if len(content.encode()) > MAX_ARG_BYTES:
        return {"ok": False, "error": f"body over {MAX_ARG_BYTES} bytes; split the page"}
    expected = slugify(title)
    existed = expected in list_slugs(host, repo)
    base = f"{project(repo)}/wikis"
    fields = ["-f", f"title={title}", "-f", "format=markdown", "-f", f"content={content}"]
    if existed:
        written = api(host, f"{base}/{quote(expected, safe='')}", "-X", "PUT", *fields)
    else:
        written = api(host, base, "-X", "POST", *fields)
    try:
        back = api(host, f"{base}/{quote(expected, safe='')}")
    except RuntimeError:
        back = None  # a page that moved away is a failed check, not a crash
    checks = {
        "slug_as_intended": (written or {}).get("slug") == expected,
        "readback_slug_matches": (back or {}).get("slug") == expected,
        "body_not_empty": bool((back or {}).get("content", "").strip()),
        "body_matches": ((back or {}).get("content", "").strip() == content.strip()),
        "in_listing": expected in list_slugs(host, repo),
    }
    return {
        "ok": all(checks.values()),
        "action": "updated" if existed else "created",
        "expected_slug": expected,
        "slug": (written or {}).get("slug"),
        "content_len": len((back or {}).get("content", "")),
        "checks": checks,
    }


def delete(host, repo, slug):
    api(host, f"{project(repo)}/wikis/{quote(slug, safe='')}", "-X", "DELETE")
    return {"ok": slug not in list_slugs(host, repo), "slug": slug}


def main(argv=None):
    ap = argparse.ArgumentParser()
    sub = ap.add_subparsers(dest="cmd", required=True)
    f = sub.add_parser("fill")
    f.add_argument("template")
    f.add_argument("--map", required=True)
    f.add_argument("--out", required=True)
    g = sub.add_parser("gitlab")
    g.add_argument("action", choices=["put", "list", "delete"])
    g.add_argument("--repo", required=True)
    g.add_argument("--host", default="gitlab.com")
    g.add_argument("--title")
    g.add_argument("--file")
    g.add_argument("--slug")
    a = ap.parse_args(argv)
    try:
        if a.cmd == "fill":
            text = fill(open(a.template).read(), json.load(open(a.map)))
            with open(a.out, "w") as o:
                o.write(text)
            print(json.dumps({"ok": True, "out": a.out, "bytes": len(text.encode())}))
            return 0
        if a.action == "put":
            if not (a.title and a.file):
                ap.error("put needs --title and --file")
            res = put(a.host, a.repo, a.title, open(a.file).read())
        elif a.action == "delete":
            if not a.slug:
                ap.error("delete needs --slug")
            res = delete(a.host, a.repo, a.slug)
        else:
            res = {"ok": True, "slugs": list_slugs(a.host, a.repo)}
    except (ValueError, RuntimeError, OSError) as e:
        print(json.dumps({"ok": False, "error": str(e)}))
        return 1
    print(json.dumps(res, indent=2))
    return 0 if res.get("ok") else 1


if __name__ == "__main__":
    sys.exit(main())
