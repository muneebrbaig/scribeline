# Changelog

## 0.1.0 (2026-10-21)

First release.

### Added
- `SKILL.md`: writes wiki pages, tickets and issues on GitHub or GitLab. Drafts in chat first and publishes only on a clear yes.
- `scripts/resolve.py`: reads the git remote and prints the platform, repo, account and profile as JSON. It maps SSH host aliases such as `github.com-alice` to an account, and with `--check` probes the login and repo access. It never prints a token.
- Three config layers: personal per clone (`.git/info/scribeline.json`), shared per repo (`.scribeline.json`, never a login), and per user (`~/.config/scribeline/`).
- Profiles: a Markdown file per team that sets tone, severity labels, slug rules, issue shapes and hard rules. A template is in `references/profile-template.md`.
- References: QA run report layout, publishing commands for GitLab wiki, GitHub wiki and issues on both platforms.
- Agents `scribeline-publisher` and `scribeline-evidence`: Haiku helpers for uploads and for matching screenshots to finding IDs.
- Unit tests for the resolver (`scripts/test_resolve.py`).

### Known gaps
- The GitHub wiki steps are written from the documented behavior and have not run against a live wiki yet.
- `--check` on GitLab probes the default `glab` login, not the alias login.
