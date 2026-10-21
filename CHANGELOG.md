# Changelog

## Unreleased

### Added
- `scripts/page.py`: fills `{{placeholders}}` from a JSON map and refuses a leftover placeholder or an empty result. `gitlab put` creates or updates a wiki page, always sends the title, and checks the slug, the stored body and the wiki listing. `gitlab list` and `gitlab delete` round it out. Tests in `scripts/test_page.py`.
- Resolver output has `issue_templates` (issue forms found in the repo) and `first_run` (no config yet). The exit code now follows `status`: 0 resolved, 2 unresolved, 3 blocked.
- `SKILL.md`: rules for the confirm gate when the request already says "create", the one-time first-run question (asked after the task, never instead of it), what "run the prose cleanup" means, who supplies evidence, test-content rules, and thresholds for the two agents (5 or more attachments, 10 or more evidence files).
- `references/publishing.md`: delete and list recipes for wiki pages, closing an issue, which issue URL to link, and the limits on upload cleanup and image checks.
- README has an "Invoking" section: the slash command, automatic loading from the description, and how to switch it off.

### Fixed
- A wiki PUT without `title` moved the page to the wiki root. The docs and `page.py` now always send it.

### Changed
- The skill description now says it writes and publishes pages and tickets, not the work a ticket describes, to keep it apart from implementation skills.
- `references/publishing.md`: after removing GitHub wiki test files, check the page URL and the repo listing. Raw image URLs can outlive the file.
- `references/publishing.md` has a "Screenshots on a page" section: collapsed `<details>` with a caption row and one image per cell, for both GitLab and GitHub.
- GitHub wiki steps in `references/publishing.md` now reflect a live run: clone and push over the SSH alias, `master` branch, `images/` folder with relative links, and a post-push check that pages and images return 200.

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
- `--check` on GitLab probes the default `glab` login, not the alias login.
