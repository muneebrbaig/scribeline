# scribeline

A [Claude Code](https://docs.anthropic.com/en/docs/claude-code) skill that writes wiki pages, tickets and issues on GitHub or GitLab. It works out which platform and which account a repo uses, loads that team's house style from a profile, and publishes only after you say so.

## Why

Teams write the same few documents again and again: a QA report, a findings page, a ticket. Each repo has its own voice, labels and issue forms. People who work across several repos also juggle several accounts, and one wrong login can fail a push or post as the wrong identity.

scribeline keeps three things out of your head:

- **Which tool and account.** It reads the remote, follows your SSH host alias to the right login and checks that the login can reach the repo.
- **How this team writes.** A profile file holds tone, severity labels, page names and hard rules.
- **How to publish.** It knows the `glab api` calls, `gh issue create` and the GitHub wiki git flow, including their quirks.

## Install

```bash
git clone https://github.com/muneebrbaig/scribeline ~/projects/skills/scribeline
ln -s ~/projects/skills/scribeline ~/.claude/skills/scribeline
ln -s ~/projects/skills/scribeline/agents/scribeline-publisher.md ~/.claude/agents/
ln -s ~/projects/skills/scribeline/agents/scribeline-evidence.md ~/.claude/agents/
```

Needs `python3`, `git`, and `gh` or `glab` signed in for the accounts you use.

## Use

Ask Claude for a page or ticket: "write up this QA run on the wiki", "file this as an issue". The skill:

1. Runs the resolver for the current repo.
2. Reads the repo's profile, if it has one.
3. Drafts in chat. Nothing is published yet.
4. Publishes after a clear "create it", then checks the slug and links.

Run the resolver by hand to see what it decides:

```bash
python3 scripts/resolve.py --path . --check
```

It prints JSON with `platform`, `login`, `login_source`, `profile` and `status` (`resolved`, `unresolved` or `blocked`). It never prints a token.

## Accounts

The resolver finds the login in this order:

1. `.git/info/scribeline.json` in the clone: `{"login": "...", "profile": "..."}`.
2. The SSH host alias in the remote. `git@github.com-alice:org/repo.git` resolves to login `alice` when `~/.ssh/config` has a `Host github.com-alice` entry. Use `aliases` in `accounts.json` when the label and the login differ.
3. Owner rules in `~/.config/scribeline/accounts.json`.

If nothing matches, the skill asks you and offers to save the answer.

`gh` calls run with a per-call `GH_TOKEN`. The skill never runs `gh auth switch`, so other terminals keep their active account.

## Config

| Layer | Path | Holds |
| --- | --- | --- |
| Personal, per clone | `<git-dir>/info/scribeline.json` | login, profile |
| Shared, per repo | `<repo>/.scribeline.json` | profile name and conventions, never a login |
| Per user | `~/.config/scribeline/` | `accounts.json` and `profiles/<name>.md` |

Example `accounts.json`:

```json
{
  "hosts": { "git.example.com": "gitlab" },
  "aliases": { "github.com-carol-work": "carol-labs" },
  "owners": { "github.com": { "acme": "alice" } },
  "profiles": { "acme/*": "acme" }
}
```

## Profiles

A profile is a Markdown file in `~/.config/scribeline/profiles/`. Start from [references/profile-template.md](references/profile-template.md). It covers tone, spelling, severity labels, page names, issue shapes and rules such as "never mention contract scope". Profiles often hold team or client rules, so keep them out of this repo.

## Agents

| Agent | Model | Job |
| --- | --- | --- |
| `scribeline-publisher` | Haiku | Uploads attachments, creates or updates the page, reads back the slug, checks links. |
| `scribeline-evidence` | Haiku | Matches screenshots and JSON files to finding IDs, lists orphans. |

Both leave the prose alone. Drafting stays with the main model.

## Tests

```bash
cd scripts && PYTHONPATH=. python3 -m unittest -q test_resolve
```

## License

[MIT](LICENSE)
