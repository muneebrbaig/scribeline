# Publishing commands

Always act as the account the resolver returned. See SKILL.md step 0.

## GitHub issues

```bash
GH_TOKEN=$(gh auth token --hostname github.com -u <login>) \
  gh issue create --repo <owner>/<repo> --title "<title>" --body-file <file> \
  --label <label> [--type <Type>] [--project <Board>]
```

- Write the body to a scratch file first.
- `gh issue create` does not apply issue forms. If the repo has `.github/ISSUE_TEMPLATE/*.yml`, write each form field as a `### <label>` section and add the title prefix, labels and type by hand.
- Board fields need the `project` scope. If a project command fails with a scope error, ask the user to run `gh auth refresh -s project`.
- Report back with a markdown link to the issue.

## GitLab issues

```bash
glab issue create --repo <owner>/<repo> --title "<title>" --description "$(cat <file>)" [--label <label>]
```

Check the project's labels first. Do not invent them.

## GitLab wiki

`glab` has no wiki subcommand. Use `glab api`. `-F` is a JSON field, not a file upload. Uploads need `--form`, which cannot be mixed with `-f` in the same call.

```bash
# Attachment, one call per file. link.url in the response is the path to use in the page.
glab api "projects/<ns>%2F<project>/wikis/attachments" -X POST --form "file=@path/to/file.jpg"

# Create a page. The slug comes from the title's path segments.
glab api "projects/<ns>%2F<project>/wikis" -X POST \
  -f "title=<Section>/<Name>-<YYYYMMDD>" -f "format=markdown" -f "content=$(cat page.md)"

# Update: PUT to the current URL-encoded slug.
glab api "projects/<ns>%2F<project>/wikis/<slug-url-encoded>" -X PUT \
  -f "format=markdown" -f "content=$(cat page.md)"
```

- `content` does not accept `--form "content=@file"`. Pass the raw string through `$(cat …)`.
- Slug paths only group the sidebar. They do not nest pages.
- After creating, read back the returned `slug` and confirm it landed where intended. A page once landed at the wiki root.
- Image cells: `![caption](uploads/<hash>/<file>){width=230}`.
- If multipart misbehaves, fall back to `curl` with the token from the glab config.
- A local clone of the wiki (`<repo>.wiki.git`) is fine for reading and diffing. Prefer the API for writes.

## GitHub wiki

There is no REST API. A GitHub wiki is a git repo.

- The wiki repo does not exist until the first page is created in the web UI. Before that, a clone returns "Repository not found" even when `has_wiki` is true.
- Use the resolver's `wiki_remote`. Its SSH alias selects the right key. Plain `git@github.com:` uses whichever key the machine offers first.
- A page is one `.md` file named after its title (`Page-Name.md`). No folders in the sidebar. Put images in the wiki repo and link them by relative path.
- `{width=230}` is GitLab-only. Use `<img src="…" width="230">`.
- Show the diff and ask before `git push`. Wikis have no PRs.

## After publishing

- Open or fetch the page and check that every image and link resolves.
- Update the index page the profile names (for example a Tracker table), if any.
- Report: the link, what was created, anything left undone.
