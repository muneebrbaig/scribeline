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

Check the project's labels first. Do not invent them. If `issue_templates` in the resolver output is not empty, follow those files.

- The create command may print a `/-/work_items/<n>` URL. Link the `web_url` the API returns for that issue (`glab api projects/<ns>%2F<project>/issues/<n> | jq -r .web_url`), not a `/-/issues/<n>` URL you assembled.
- Close a test issue: `glab issue close <n> --repo <owner>/<repo>`.

## GitLab wiki

`glab` has no wiki subcommand. Use `glab api`, or better, `scripts/page.py`, which wraps the calls below and checks the result:

```bash
python3 -I <skill-dir>/scripts/page.py gitlab put    --repo <ns>/<project> --title "<Section>/<Name>" --file page.md
python3 -I <skill-dir>/scripts/page.py gitlab list   --repo <ns>/<project>
python3 -I <skill-dir>/scripts/page.py gitlab delete --repo <ns>/<project> --slug "<Section>/<Name>"
```

`put` exits 0 only when the slug, the stored body and the listing all check out. Fill placeholders with `page.py fill`, not `sed`: a failed substitution once produced an empty page that the API accepted.

Raw calls, if you need them. `-F` is a JSON field, not a file upload. Uploads need `--form`, which cannot be mixed with `-f` in the same call.

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

- On update, always pass `-f "title=<Section>/<Name>"` too. A PUT without `title` re-derives the title from the slug's last segment and moves the page to the wiki root.
- `content` does not accept `--form "content=@file"`. Pass the raw string through `$(cat …)`, and check that it is not empty. The API accepts `content=""`.
- Slug paths only group the sidebar. They do not nest pages.
- After every write, read back the `slug` and the body, and list the wiki (`GET projects/<ns>%2F<project>/wikis`) to confirm placement. Pages have landed at the wiki root twice.
- Delete a page: `glab api "projects/<ns>%2F<project>/wikis/<slug-url-encoded>" -X DELETE`.
- Attachments cannot be deleted through the API. Test uploads stay in the project for good.
- Wiki upload URLs need a sign-in on private projects, so a script cannot confirm that images render. Open the page in a browser, or say you did not check.
- Image cells: `![caption](uploads/<hash>/<file>){width=230}`.
- If multipart misbehaves, fall back to `curl` with the token from the glab config.
- A local clone of the wiki (`<repo>.wiki.git`) is fine for reading and diffing. Prefer the API for writes.

## GitHub wiki

There is no REST API. A GitHub wiki is a git repo.

- The wiki repo does not exist until the first page is created in the web UI. Before that, a clone returns "Repository not found" even when `has_wiki` is true.
- Use the resolver's `wiki_remote`. Its SSH alias selects the right key. Plain `git@github.com:` uses whichever key the machine offers first.
- A page is one `.md` file named after its title (`Page-Name.md`). No folders in the sidebar. `Home.md` is the wiki's landing page (`/wiki`). Link pages with `[text](Page-Name)`.
- Put images in an `images/` folder in the wiki repo and link them as `![alt](images/file.png)`. GitHub redirects that path to the raw file. Verified on a live wiki.
- `{width=230}` is GitLab-only. Use `<img src="images/file.png" width="230">`.
- The default branch is `master`. Push there.
- Show the diff and ask before `git push`. Wikis have no PRs.
- After the push, fetch `https://github.com/<owner>/<repo>/wiki/<Page>` and check for HTTP 200, and check each image path returns 200 after redirects.

## Screenshots on a page

Put screenshots in a collapsed section under the text they support, on both platforms. A caption row on top, one image per cell:

```markdown
<details>
<summary>📷 Screenshots (2)</summary>

| First caption | Second caption |
|---|---|
| ![First caption](uploads/…/a.png){width=230} | ![Second caption](uploads/…/b.png){width=230} |

</details>
```

- Leave a blank line after `<summary>` and before `</details>`, or the table does not render.
- GitLab: `![…](path){width=230}`. GitHub: `<img src="images/a.png" alt="…" width="230">`, because `{width=…}` is not supported there.
- Several screenshots for one finding share one `<details>` and one table. Wrap to a second table for more than four.
- The count in the summary is the number of images inside.

## After publishing

- Open or fetch the page and check that every image and link resolves.
- Update the index page the profile names (for example a Tracker table), if any.
- Report: the link, what was created, anything left undone.
