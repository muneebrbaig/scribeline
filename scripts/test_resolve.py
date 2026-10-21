import json
import os
import subprocess
import tempfile
import unittest
from unittest import mock

import resolve

SSH = """
Host github.com-alice
   HostName github.com
   User git
Host gitlab.com-bob
   HostName gitlab.com
Host github.com-carol-work
   HostName github.com
Host *
   ServerAliveInterval 30
"""


class Base(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.ssh = os.path.join(self.tmp.name, "ssh_config")
        self.home = os.path.join(self.tmp.name, "home")
        os.makedirs(os.path.join(self.home, "profiles"))
        open(self.ssh, "w").write(SSH)

    def reg(self, data):
        json.dump(data, open(os.path.join(self.home, "accounts.json"), "w"))

    def go(self, remote, **kw):
        return resolve.resolve(self.tmp.name, remote=remote, ssh_config=self.ssh, home=self.home, **kw)


class ParseRemote(unittest.TestCase):
    def test_forms(self):
        for url in ("git@github.com:o/r.git", "https://github.com/o/r", "ssh://git@github.com/o/r.git",
                    "https://tok@github.com/o/r.git"):
            self.assertEqual(resolve.parse_remote(url), ("github.com", "o", "r", False), url)

    def test_wiki_and_alias(self):
        self.assertEqual(resolve.parse_remote("gitlab.com-me:o/r.wiki.git"), ("gitlab.com-me", "o", "r", True))

    def test_nested_gitlab_group(self):
        self.assertEqual(resolve.parse_remote("git@gitlab.com:g/sub/r.git"), ("gitlab.com", "g/sub", "r", False))

    def test_garbage(self):
        self.assertIsNone(resolve.parse_remote("not a url"))


class Resolve(Base):
    def test_alias_gives_login(self):
        r = self.go("git@github.com-alice:acme/app-web.git")
        self.assertEqual((r["platform"], r["host"], r["login"], r["login_source"]),
                         ("github", "github.com", "alice", "ssh-alias"))
        self.assertEqual(r["wiki_remote"], "git@github.com-alice:acme/app-web.wiki.git")
        self.assertEqual(r["status"], "resolved")
        self.assertNotIn("gho_", json.dumps(r))

    def test_alias_label_remapped_by_registry(self):
        self.reg({"aliases": {"github.com-carol-work": "carol-labs"}})
        r = self.go("git@github.com-carol-work:Side/app.git")
        self.assertEqual(r["login"], "carol-labs")

    def test_plain_host_uses_owner_rule(self):
        self.reg({"owners": {"github.com": {"acme": "alice"}}})
        r = self.go("git@github.com:acme/x.git")
        self.assertEqual((r["login"], r["login_source"]), ("alice", "registry-owner"))

    def test_plain_host_no_rule_is_unresolved(self):
        r = self.go("git@github.com:o/r.git")
        self.assertEqual(r["status"], "unresolved")
        self.assertTrue(any("ask the user" in n for n in r["notes"]))

    def test_gitlab_resolves_without_login(self):
        r = self.go("gitlab.com-bob:bob/tool.wiki.git")
        self.assertEqual((r["platform"], r["is_wiki"], r["repo"], r["status"]),
                         ("gitlab", True, "tool", "resolved"))
        self.assertEqual(r["auth"]["cli"], "glab")

    def test_unknown_host_needs_registry(self):
        r = self.go("git@git.corp.example:team/app.git")
        self.assertEqual((r["platform"], r["status"]), ("unknown", "unresolved"))
        self.reg({"hosts": {"git.corp.example": "gitlab"}})
        self.assertEqual(self.go("git@git.corp.example:team/app.git")["platform"], "gitlab")

    def test_profile_rules_and_missing_file(self):
        self.reg({"profiles": {"acme/*": "acmeprofile", "bob/tool": "tool"}})
        r = self.go("git@github.com-alice:acme/a.git")
        self.assertEqual(r["profile"], "acmeprofile")
        self.assertIsNone(r["profile_file"])
        self.assertTrue(any("no file" in n for n in r["notes"]))
        open(os.path.join(self.home, "profiles", "acmeprofile.md"), "w").write("x")
        self.assertTrue(self.go("git@github.com-alice:acme/a.git")["profile_file"].endswith("acmeprofile.md"))

    def test_exact_repo_rule_beats_owner_wildcard(self):
        rules = {"o/*": "wide", "o/r": "narrow"}
        self.assertEqual(resolve.match_rule(rules, "o", "r"), "narrow")

    def test_check_marks_blocked_when_suspended(self):
        with mock.patch.object(resolve, "run") as run:
            def fake(cmd, env=None):
                if cmd[:3] == ["gh", "auth", "token"]:
                    return 0, "SECRET123\n", ""
                return 1, "", "Sorry. Your account was suspended"
            run.side_effect = fake
            r = self.go("git@github.com-alice:o/r.git", check=True)
        self.assertEqual(r["status"], "blocked")
        self.assertEqual(r["access"]["reason"], "account suspended")
        self.assertNotIn("SECRET123", json.dumps(r))


class RepoConfig(Base):
    def make_repo(self, remote):
        d = os.path.join(self.tmp.name, "repo")
        subprocess.run(["git", "init", "-q", d], check=True)
        subprocess.run(["git", "-C", d, "remote", "add", "origin", remote], check=True)
        return d

    def test_personal_config_overrides_alias_and_team_login_ignored(self):
        d = self.make_repo("git@github.com-alice:o/r.git")
        os.makedirs(os.path.join(d, ".git", "info"), exist_ok=True)
        json.dump({"login": "devops-x", "profile": "p"}, open(os.path.join(d, ".git", "info", "scribeline.json"), "w"))
        json.dump({"login": "teammate", "profile": "team"}, open(os.path.join(d, ".scribeline.json"), "w"))
        r = resolve.resolve(d, ssh_config=self.ssh, home=self.home)
        self.assertEqual((r["login"], r["login_source"], r["profile"]), ("devops-x", "repo-personal", "p"))
        self.assertTrue(any("keep them out of the repo" in n for n in r["notes"]))

    def test_team_profile_used_when_no_personal(self):
        d = self.make_repo("git@github.com-alice:o/r.git")
        json.dump({"profile": "team"}, open(os.path.join(d, ".scribeline.json"), "w"))
        self.assertEqual(resolve.resolve(d, ssh_config=self.ssh, home=self.home)["profile"], "team")

    def test_not_a_repo(self):
        r = resolve.resolve(self.tmp.name, ssh_config=self.ssh, home=self.home)
        self.assertEqual(r["status"], "unresolved")

    def test_first_run_until_any_config_exists(self):
        d = self.make_repo("git@github.com-alice:o/r.git")
        self.assertTrue(resolve.resolve(d, ssh_config=self.ssh, home=self.home)["first_run"])
        os.makedirs(os.path.join(d, ".git", "info"), exist_ok=True)
        json.dump({"prompted": True}, open(os.path.join(d, ".git", "info", "scribeline.json"), "w"))
        self.assertFalse(resolve.resolve(d, ssh_config=self.ssh, home=self.home)["first_run"])

    def test_issue_templates_listed(self):
        d = self.make_repo("gitlab.com-bob:o/r.git")
        self.assertEqual(resolve.resolve(d, ssh_config=self.ssh, home=self.home)["issue_templates"], [])
        os.makedirs(os.path.join(d, ".gitlab", "issue_templates"))
        os.makedirs(os.path.join(d, ".github", "ISSUE_TEMPLATE"))
        for p in (".gitlab/issue_templates/Bug.md", ".github/ISSUE_TEMPLATE/bug.yml"):
            open(os.path.join(d, p), "w").write("x")
        got = resolve.resolve(d, ssh_config=self.ssh, home=self.home)["issue_templates"]
        self.assertEqual(got, [".github/ISSUE_TEMPLATE/bug.yml", ".gitlab/issue_templates/Bug.md"])


class ExitCodes(Base):
    def code(self, remote, **kw):
        with mock.patch.object(resolve, "resolve", return_value=kw):
            return resolve.main(["--remote", remote])

    def test_status_maps_to_exit_code(self):
        self.assertEqual(self.code("x", status="resolved"), 0)
        self.assertEqual(self.code("x", status="unresolved"), 2)
        self.assertEqual(self.code("x", status="blocked"), 3)


if __name__ == "__main__":
    unittest.main()
