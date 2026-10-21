---
name: scribeline
description: Write and publish wiki pages, tickets and issues (QA run reports, findings, product notes, bug and feature requests) on GitHub or GitLab. Detects the platform and the right account from the repo, loads the team's house style from a profile, drafts in chat first and publishes only on a clear yes. Use when the user asks for a wiki page, QA report, findings write-up, ticket, issue, or "file this".
---

# scribeline

Turn findings, QA runs and product notes into pages and tickets that a PM, QA lead or client can read without help.

Nothing here is specific to one team. Team style lives in a **profile** (see "Profiles"). Without one, use the defaults in this file.

## Step 0: resolve the repo, account and profile

Run the resolver before any write. It reads the git remote, maps SSH host aliases to accounts, and prints one JSON object. It never prints a token.

```bash
python3 -I <skill-dir>/scripts/resolve.py --path <repo-dir> --check
```

| Field | Use |
| --- | --- |
| `platform` | `github` means `gh`, `gitlab` means `glab`. `unknown`: ask for the host type and save it under `hosts` in `accounts.json`. |
| `login`, `login_source` | The account to act as. `login_source` says why (`repo-personal`, `ssh-alias`, `registry-owner`). |
| `status` | `resolved`: go on. `unresolved`: ask the user which login, then save it (see "Config"). `blocked`: stop and report `access.reason` (for example "account suspended"). Do not fall back to another account without asking. |
| `wiki_remote` | The wiki git URL with the right SSH alias. |
| `profile_file` | Read it fully before drafting. |
| `issue_templates` | Issue forms found in the repo. If the list is not empty and you are writing a ticket, read every file in it first and follow it. |
| `first_run` | `true` when the clone has no personal or team config yet. See "Config". |

The exit code follows `status`: 0 resolved, 2 unresolved, 3 blocked.

**Acting as the resolved account:**

- `gh`: prefix each call with `GH_TOKEN=$(gh auth token --hostname <host> -u <login>)`. Never run `gh auth switch`: it changes the active account for every other terminal and session. Ask first if the user wants that.
- `git` push or clone over SSH: use the `wiki_remote` (or the repo's own remote), which already carries the alias and so the right key.
- `glab`: uses its logged-in account for the host. If `login` differs from `glab auth status`, say so before writing.
- Never echo a token, and never put one in a file.

Re-run the resolver if a call returns 401, 403 or 404. Cached answers can be stale.

## Config

Three places, in order of precedence:

| Layer | Path | Holds | Shared? |
| --- | --- | --- | --- |
| Repo, personal | `<git-dir>/info/scribeline.json` | `login`, `profile` for this clone | No. Inside `.git`, so nothing to ignore. |
| Repo, team | `<repo>/.scribeline.json` | `profile` name and shareable conventions. Never a login. | Yes, if committed |
| User | `~/.config/scribeline/` (or `$SCRIBELINE_HOME`) | `accounts.json` (`hosts`, `aliases`, `owners`, `profiles` rules) and `profiles/<name>.md` | No |

**When the resolver says `first_run: true`**, offer the choice once, after the task is done. Never ahead of it, and never instead of it. An explicit request to create something is not blocked by this question.

1. Add `.scribeline.json` to the repo so the team shares conventions. Write the file, show it, let the user commit it. Never commit it yourself.
2. Keep it local. Write `.git/info/scribeline.json` instead (or append `.scribeline.json` to `.git/info/exclude` if the user wants a worktree file).
3. Skip. Write `{"prompted": true}` to `.git/info/scribeline.json` so the question is not asked again.

Agents and non-interactive runs take option 2 without asking. Repos the user does not own (client repos) take option 2 as well.

## Profiles

A profile is a Markdown file the user owns. It sets: tone, spelling, severity labels and ID prefixes, page slug conventions, index pages to update, issue shapes, labels and forms, and house rules ("never mention X"). Start from `references/profile-template.md`. Profiles often hold client or team rules, so they stay in `~/.config/scribeline/profiles/` and are never shipped with this skill.

If a profile names a stricter rule than this file, the profile wins.

## Defaults (no profile)

- Product-person tone: full sentences, outcome first, no raw logs.
- Prose cleanup means invoking the user's cleanup skill (for example `stop-slop`) with the Skill tool on every draft. If it is not installed, apply the rules by hand and say so in the report. Do not report it as run when you only followed its rules from memory.
- **The confirm gate.** Wikis and issues are visible to the whole team, so nothing is published without a yes. What counts as a yes:
  - The user's request already says create, file or publish, and the user supplied the full text or said to go ahead without a draft: that is the yes. Publish, then report.
  - The request says create, file or publish, but you write the content: draft in chat first and wait. The words "create it" approved the task, not text they have not seen.
  - A repo the user does not own: always draft and wait.
- Check for an existing page or issue on the topic first. Update, don't duplicate.
- Treat ticket text as a claim. Verify against the code before writing "done" or "missing".
- Never paste credentials, client data or personal data.
- Do not `git commit` repo code. The one exception is a wiki push the user asked for.

## What to write

- **QA run report:** `references/qa-run.md`
- **Findings or analysis page, product note:** same top as a QA run (opening paragraph, bottom line), then sections by theme, a scope check and an out-of-scope list.
- **Ticket or issue:** Problem, Proposed direction, Scope check, Out of scope. If the repo has issue forms (`.github/ISSUE_TEMPLATE/*.yml` or `.gitlab/issue_templates/`), read them first and follow them. They are the source of truth.

## Publishing

See `references/publishing.md` for the exact `glab api`, `gh issue create` and GitHub-wiki git commands, and the pitfalls (slug read-back, uploads, `.wiki.git` not existing until the first page).

## Evidence

The skill does not capture or invent screenshots. The user supplies them, or the profile says where they live (for example a gitignored artifacts folder). If a page needs screenshots and none exist, say so and ask. Generated placeholder images are for tests only, and the page must say they are samples.

On GitLab, uploaded attachments cannot be deleted through the API. Every test image stays in the project's uploads, so keep test runs to a few small images.

## Testing the skill itself

Use a sandbox slug the profile names, or `QA/Sandbox/<Name>` when it names none. Do not add a row to any index page for test content. Delete test pages and close test issues when done, and say which uploads remain.

## Workflow

1. Resolve (step 0). Stop on `blocked`.
2. Read the profile and any `issue_templates`. Gather facts: logs, screenshots, the code or ticket the work refers to.
3. Draft in chat, fill any placeholders with `scripts/page.py fill` (never `sed` or shell substitution: a failed substitution produced an empty page once), and run the prose cleanup. State assumptions.
4. Revise until the confirm gate is met.
5. Publish. On a GitLab wiki use `scripts/page.py gitlab put`. It always sends the title, so an update cannot move the page to the wiki root, and it refuses an empty body. On other targets follow `references/publishing.md`.
6. Verify after every write. On a GitLab wiki, a page write is not done until `page.py` reports `ok: true`: the slug is the one you intended, the body read back is not empty and matches, and the page is in the wiki listing. On a GitHub wiki, fetch each page and image after the push and expect HTTP 200. For issues, link the `web_url` that the API returns, not a URL you assembled.
7. Report the link, what was created, and anything left undone (index row, linked issues, failed images). Say plainly what was not checked. For example, uploaded images on a private GitLab project need a sign-in, so confirm they render by opening the page in a browser, or tell the user you did not.

## Delegation to a smaller model

Both agents run on Haiku with a narrow brief and a fixed output shape. They never edit prose.

- Use `scribeline-publisher` when a page has **5 or more attachments**. Below that, run the uploads yourself.
- Use `scribeline-evidence` when an evidence folder has **10 or more files**.

- `agents/scribeline-evidence.md`: map screenshots and JSON files to finding IDs. Input: the folder, the list of finding IDs. Output: a table plus orphans on both sides.
- `agents/scribeline-publisher.md`: upload attachments, create or update the page, read back the slug, check every link. Input: page file, attachment folder, resolver JSON. Output: `RESULT: ok | fail` plus URLs.

Install them by symlinking into `~/.claude/agents/`.

Everything deterministic (platform, account, access) is the resolver script, not a model.
