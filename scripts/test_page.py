import json
import os
import tempfile
import unittest
from unittest import mock

import page


class FakeWiki:
    """Stands in for glab api. Keeps pages by slug. `move_on_put` mimics the root-landing bug."""

    def __init__(self, pages=None, move_on_put=False, drop_body=False):
        self.pages = dict(pages or {})
        self.move_on_put = move_on_put
        self.drop_body = drop_body
        self.calls = []

    def __call__(self, cmd):
        self.calls.append(cmd)
        path = cmd[2]
        method = cmd[cmd.index("-X") + 1] if "-X" in cmd else "GET"
        fields = {cmd[i + 1].split("=", 1)[0]: cmd[i + 1].split("=", 1)[1]
                  for i, c in enumerate(cmd) if c == "-f"}
        if method in ("POST", "PUT"):
            title = fields.get("title")
            slug = title.split("/")[-1] if (method == "PUT" and "title" not in fields) else title
            if method == "PUT" and self.move_on_put:
                slug = title.split("/")[-1]
                self.pages.pop(path.split("/wikis/")[1].replace("%2F", "/"), None)
            self.pages[slug] = "" if self.drop_body else fields["content"]
            return 0, json.dumps({"slug": slug, "title": title, "content": self.pages[slug]}), ""
        if path.endswith("/wikis"):
            return 0, json.dumps([{"slug": s} for s in self.pages]), ""
        slug = path.split("/wikis/")[1].replace("%2F", "/")
        if method == "DELETE":
            self.pages.pop(slug, None)
            return 0, "", ""
        if slug not in self.pages:
            return 1, "", "404 Not Found"
        return 0, json.dumps({"slug": slug, "content": self.pages[slug]}), ""


class Fill(unittest.TestCase):
    def test_replaces_and_keeps_special_chars(self):
        out = page.fill("Issue {{n}} / {{ url }}", {"n": "#170", "url": "a|b&c"})
        self.assertEqual(out, "Issue #170 / a|b&c")

    def test_missing_key_fails(self):
        with self.assertRaisesRegex(ValueError, "other"):
            page.fill("{{a}} {{other}}", {"a": "1"})

    def test_empty_result_fails(self):
        with self.assertRaisesRegex(ValueError, "empty"):
            page.fill("{{a}}", {"a": "  "})

    def test_cli_fill_writes_file_and_refuses_empty(self):
        d = tempfile.mkdtemp()
        t, m, o = (os.path.join(d, n) for n in ("t.md", "m.json", "o.md"))
        open(t, "w").write("x {{a}}")
        json.dump({"a": "#1"}, open(m, "w"))
        self.assertEqual(page.main(["fill", t, "--map", m, "--out", o]), 0)
        self.assertEqual(open(o).read(), "x #1")
        open(t, "w").write("{{a}}")
        json.dump({"a": ""}, open(m, "w"))
        self.assertEqual(page.main(["fill", t, "--map", m, "--out", o]), 1)


class Put(unittest.TestCase):
    def run_put(self, wiki, title="QA/Test/X", content="# Hi\n"):
        with mock.patch.object(page, "run", wiki):
            return page.put("gitlab.com", "o/r", title, content)

    def test_create_ok(self):
        wiki = FakeWiki()
        r = self.run_put(wiki)
        self.assertTrue(r["ok"], r)
        self.assertEqual((r["action"], r["slug"]), ("created", "QA/Test/X"))

    def test_update_sends_title_and_stays_in_place(self):
        wiki = FakeWiki({"QA/Test/X": "old"})
        r = self.run_put(wiki, content="new body")
        self.assertTrue(r["ok"], r)
        self.assertEqual(r["action"], "updated")
        put_call = [c for c in wiki.calls if "PUT" in c][0]
        self.assertTrue(any(a == "title=QA/Test/X" for a in put_call))
        self.assertEqual(list(wiki.pages), ["QA/Test/X"])

    def test_refuses_empty_body_without_calling_api(self):
        wiki = FakeWiki()
        r = self.run_put(wiki, content="  \n")
        self.assertFalse(r["ok"])
        self.assertEqual(wiki.calls, [])

    def test_detects_page_moved_to_root(self):
        wiki = FakeWiki({"QA/Test/X": "old"}, move_on_put=True)
        r = self.run_put(wiki)
        self.assertFalse(r["ok"])
        self.assertFalse(r["checks"]["slug_as_intended"])

    def test_detects_empty_saved_body(self):
        r = self.run_put(FakeWiki(drop_body=True))
        self.assertFalse(r["ok"])
        self.assertFalse(r["checks"]["body_not_empty"])

    def test_spaces_in_title_become_hyphens(self):
        self.assertEqual(page.slugify("QA/Mobile/My Run 1"), "QA/Mobile/My-Run-1")

    def test_oversize_body_refused(self):
        r = self.run_put(FakeWiki(), content="x" * (page.MAX_ARG_BYTES + 1))
        self.assertFalse(r["ok"])

    def test_delete_checks_listing(self):
        wiki = FakeWiki({"A/B": "x"})
        with mock.patch.object(page, "run", wiki):
            self.assertTrue(page.delete("gitlab.com", "o/r", "A/B")["ok"])


if __name__ == "__main__":
    unittest.main()
