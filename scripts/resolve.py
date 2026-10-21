#!/usr/bin/env python3
"""Resolve platform, repo, account and profile for scribeline.

Prints one JSON object. Never prints a token.

  resolve.py [--path DIR] [--remote URL] [--ssh-config FILE] [--home DIR] [--check]

Exit code follows `status`: 0 resolved, 2 unresolved, 3 blocked.
`first_run` is true in a git repo with neither personal nor team config.
`issue_templates` lists issue forms found in the repo.

Login precedence: repo-personal config > ssh alias label > owner rules in the registry.
Profile precedence: repo-personal config > team config > registry profile rules.
"""
import argparse
import fnmatch
import glob
import json
import os
import re
import subprocess
import sys

KNOWN_HOSTS = {"github.com": "github", "gitlab.com": "gitlab"}
EXIT_CODES = {"resolved": 0, "unresolved": 2, "blocked": 3}
REMOTE_RE = [
    re.compile(r"^(?:ssh://)?(?:[^@/]+@)?(?P<host>[^:/]+)(?::\d+)?[:/](?P<path>[^/].*)$"),
    re.compile(r"^https?://(?:[^@/]+@)?(?P<host>[^/:]+)(?::\d+)?/(?P<path>.+)$"),
]


def run(cmd, env=None):
    try:
        p = subprocess.run(cmd, capture_output=True, text=True, env=env, timeout=20)
        return p.returncode, p.stdout, p.stderr
    except (OSError, subprocess.TimeoutExpired) as e:
        return 127, "", str(e)


def read_json(path):
    try:
        with open(path) as f:
            return json.load(f)
    except (OSError, ValueError):
        return {}


def parse_remote(url):
    """Return (host_or_alias, owner, repo, is_wiki) or None."""
    url = url.strip()
    pattern = REMOTE_RE[1] if url.startswith(("http://", "https://")) else REMOTE_RE[0]
    m = pattern.match(url)
    if not m:
        return None
    path = m.group("path").rstrip("/")
    if path.endswith(".git"):
        path = path[:-4]
    is_wiki = path.endswith(".wiki")
    if is_wiki:
        path = path[:-5]
    parts = path.split("/")
    if len(parts) < 2:
        return None
    return m.group("host"), "/".join(parts[:-1]), parts[-1], is_wiki


def ssh_aliases(config_path):
    """Map Host alias -> HostName from an ssh config. Wildcard hosts are skipped."""
    aliases, current = {}, []
    try:
        lines = open(config_path).read().splitlines()
    except OSError:
        return aliases
    for line in lines:
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        key, _, value = line.partition(" ")
        key, value = key.lower(), value.strip()
        if key == "host":
            current = [h for h in value.split() if not re.search(r"[*?!]", h)]
        elif key == "hostname":
            for h in current:
                aliases[h] = value
    return aliases


def split_alias(host, aliases):
    """github.com-alice -> (github.com, alice). Plain hosts -> (host, None)."""
    real = aliases.get(host)
    if not real:
        return host, None
    label = host[len(real) + 1:] if host.startswith(real + "-") else host
    return real, label if label != host else None


def git_paths(path):
    code, out, _ = run(["git", "-C", path, "rev-parse", "--show-toplevel", "--git-common-dir"])
    if code != 0:
        return None, None
    top, common = out.splitlines()[:2]
    if not os.path.isabs(common):
        common = os.path.normpath(os.path.join(top, common))
    return top, common


def issue_templates(top):
    """Repo-relative paths of issue forms and templates, so the skill can't forget to read them."""
    if not top:
        return []
    found = []
    for pattern in (".github/ISSUE_TEMPLATE/*", ".gitlab/issue_templates/*", ".github/ISSUE_TEMPLATE.md"):
        found += sorted(os.path.relpath(p, top) for p in glob.glob(os.path.join(top, pattern)) if os.path.isfile(p))
    return found


def match_rule(rules, owner, repo):
    full = f"{owner}/{repo}"
    best = None
    for pattern, value in (rules or {}).items():
        if fnmatch.fnmatch(full, pattern) or fnmatch.fnmatch(owner, pattern):
            # a rule without wildcards beats one with, then the longer pattern wins
            rank = ("*" not in pattern and "?" not in pattern, len(pattern))
            if best is None or rank > best[0]:
                best = (rank, value)
    return best[1] if best else None


def authenticated(platform, host, login):
    """True/False for github (gh knows the login), None when it cannot be told."""
    if platform != "github" or not login:
        return None
    code, _, _ = run(["gh", "auth", "token", "--hostname", host, "-u", login])
    return code == 0


def repo_access(platform, host, owner, repo, login):
    """Probe the repo with the chosen account. Returns a short dict, no secrets."""
    if platform == "github":
        code, tok, _ = run(["gh", "auth", "token", "--hostname", host, "-u", login])
        if code != 0:
            return {"ok": False, "reason": "login not authenticated in gh"}
        env = dict(os.environ, GH_TOKEN=tok.strip())
        code, out, err = run(["gh", "api", f"repos/{owner}/{repo}", "--jq",
                              "{push:.permissions.push,triage:.permissions.triage,wiki:.has_wiki}"], env)
        if code != 0:
            msg = (out + err).lower()
            if "suspended" in msg:
                return {"ok": False, "reason": "account suspended"}
            return {"ok": False, "reason": "repo not visible to this login (404 or 403)"}
        try:
            return dict(json.loads(out), ok=True)
        except ValueError:
            return {"ok": False, "reason": "unreadable response"}
    if platform == "gitlab":
        proj = f"{owner}/{repo}".replace("/", "%2F")
        code, out, err = run(["glab", "api", f"projects/{proj}", "--hostname", host])
        if code != 0:
            return {"ok": False, "reason": "project not visible to glab login"}
        try:
            d = json.loads(out)
            level = ((d.get("permissions") or {}).get("project_access") or {}).get("access_level")
            return {"ok": True, "access_level": level, "wiki": d.get("wiki_enabled")}
        except ValueError:
            return {"ok": False, "reason": "unreadable response"}
    return {"ok": False, "reason": "unknown platform"}


def resolve(path, remote=None, ssh_config=None, home=None, check=False):
    home = home or os.environ.get("SCRIBELINE_HOME") or os.path.expanduser("~/.config/scribeline")
    ssh_config = ssh_config or os.path.expanduser("~/.ssh/config")
    registry = read_json(os.path.join(home, "accounts.json"))
    notes = []

    top, gitdir = git_paths(path)
    if remote is None:
        if top is None:
            return {"status": "unresolved", "notes": ["not a git repo and no --remote given"]}
        code, out, _ = run(["git", "-C", path, "remote", "get-url", "origin"])
        if code != 0:
            return {"status": "unresolved", "notes": ["no origin remote"]}
        remote = out.strip()

    parsed = parse_remote(remote)
    if not parsed:
        return {"status": "unresolved", "notes": [f"cannot parse remote: {remote}"]}
    raw_host, owner, repo, is_wiki = parsed

    aliases = ssh_aliases(ssh_config)
    host, alias_label = split_alias(raw_host, aliases)
    alias = raw_host if alias_label else None
    if alias_label:
        alias_label = (registry.get("aliases") or {}).get(raw_host, alias_label)

    platform = KNOWN_HOSTS.get(host) or (registry.get("hosts") or {}).get(host) or "unknown"
    if platform == "unknown":
        notes.append(f"unknown host {host}; add it under 'hosts' in accounts.json")

    personal = read_json(os.path.join(gitdir, "info", "scribeline.json")) if gitdir else {}
    team_path = os.path.join(top, ".scribeline.json") if top else None
    team = read_json(team_path) if team_path and os.path.exists(team_path) else {}
    if "login" in team:
        notes.append("ignored 'login' in .scribeline.json: accounts are personal, keep them out of the repo")

    login, source = None, "none"
    if personal.get("login"):
        login, source = personal["login"], "repo-personal"
    elif alias_label:
        login, source = alias_label, "ssh-alias"
    else:
        rule = match_rule((registry.get("owners") or {}).get(host), owner, repo)
        if rule:
            login, source = rule, "registry-owner"

    profile = personal.get("profile") or team.get("profile") or match_rule(registry.get("profiles"), owner, repo)
    profile_file = os.path.join(home, "profiles", f"{profile}.md") if profile else None
    if profile_file and not os.path.exists(profile_file):
        notes.append(f"profile '{profile}' has no file at {profile_file}")
        profile_file = None

    auth = None
    if platform == "github" and login:
        auth = {"cli": "gh", "token_env": "GH_TOKEN",
                "token_cmd": f"gh auth token --hostname {host} -u {login}"}
    elif platform == "gitlab":
        auth = {"cli": "glab", "note": "glab uses its logged-in account for this host"}

    out = {
        "platform": platform, "host": host, "owner": owner, "repo": repo, "is_wiki": is_wiki,
        "ssh_alias": alias, "login": login, "login_source": source,
        "wiki_remote": f"git@{alias or host}:{owner}/{repo}.wiki.git",
        "auth": auth, "profile": profile, "profile_file": profile_file,
        "team_config": team_path if team else None,
        "first_run": bool(top) and not personal and not team,
        "issue_templates": issue_templates(top),
        "status": "resolved" if platform != "unknown" and (login or platform == "gitlab") else "unresolved",
        "notes": notes,
    }
    if out["status"] == "unresolved" and platform == "github" and not login:
        notes.append("no login found: ask the user which account to use, then save it to .git/info/scribeline.json")
    if check and login:
        out["login_authenticated"] = authenticated(platform, host, login)
        out["access"] = repo_access(platform, host, owner, repo, login)
        if not out["access"].get("ok"):
            out["status"] = "blocked"
    return out


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--path", default=os.getcwd())
    ap.add_argument("--remote")
    ap.add_argument("--ssh-config")
    ap.add_argument("--home")
    ap.add_argument("--check", action="store_true", help="probe login and repo access")
    a = ap.parse_args(argv)
    result = resolve(a.path, a.remote, a.ssh_config, a.home, a.check)
    print(json.dumps(result, indent=2))
    return EXIT_CODES.get(result.get("status"), 2)


if __name__ == "__main__":
    sys.exit(main())
