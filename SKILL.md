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

**First run in a repo with no team config**, ask once:

1. Add `.scribeline.json` to the repo so the team shares conventions. Write the file, show it, let the user commit it. Never commit it yourself.
2. Keep it local. Write `.git/info/scribeline.json` instead (or append `.scribeline.json` to `.git/info/exclude` if the user wants a worktree file).
3. Skip.

Agents and non-interactive runs default to 2. Repos the user does not own (client repos) default to 2 as well.

## Profiles

A profile is a Markdown file the user owns. It sets: tone, spelling, severity labels and ID prefixes, page slug conventions, index pages to update, issue shapes, labels and forms, and house rules ("never mention X"). Start from `references/profile-template.md`. Profiles often hold client or team rules, so they stay in `~/.config/scribeline/profiles/` and are never shipped with this skill.

If a profile names a stricter rule than this file, the profile wins.

## Defaults (no profile)

- Product-person tone: full sentences, outcome first, no raw logs.
- Run the user's prose-cleanup skill (for example `stop-slop`) on every draft if one is installed.
- Draft in chat first. Publish only after a clear "create it", "file it" or "publish it". Wikis and issues are visible to the whole team.
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

## Workflow

1. Resolve (step 0). Stop on `blocked`.
2. Read the profile. Gather facts: logs, screenshots, the code or ticket the work refers to.
3. Draft in chat and apply the prose cleanup. State assumptions.
4. Revise until approved.
5. Publish on a clear yes. For more than a few attachments, hand uploads to the `scribeline-publisher` agent. For a big evidence folder, use `scribeline-evidence` first.
6. Verify the result: slug, links, attachments. Report the link, what was created, and anything left undone (index row, linked issues, failed images).

## Delegation to a smaller model

Both agents run on Haiku with a narrow brief and a fixed output shape. They never edit prose.

- `agents/scribeline-evidence.md`: map screenshots and JSON files to finding IDs. Input: the folder, the list of finding IDs. Output: a table plus orphans on both sides.
- `agents/scribeline-publisher.md`: upload attachments, create or update the page, read back the slug, check every link. Input: page file, attachment folder, resolver JSON. Output: `RESULT: ok | fail` plus URLs.

Install them by symlinking into `~/.claude/agents/`.

Everything deterministic (platform, account, access) is the resolver script, not a model.
