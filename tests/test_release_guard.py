"""scripts/release_guard.py: which versions the release workflow accepts."""
import importlib.util
import json
import subprocess
import sys

from pathlib import Path

SCRIPT = Path(__file__).resolve().parent.parent / "scripts" / "release_guard.py"
spec = importlib.util.spec_from_file_location("release_guard", SCRIPT)
guard = importlib.util.module_from_spec(spec)
spec.loader.exec_module(guard)


def rel(tag, draft=False):
    return {"tagName": tag, "isDraft": draft, "isPrerelease": "-" in tag}


RELEASES = [rel("update-feed"), rel("v2.0.0"), rel("v2.1.0"), rel("v2.1.1"),
            rel("v2.1.2-beta.1"), rel("v2.1.2-beta.2")]


def ok(version, releases=RELEASES):
    return guard.check(version, releases)[0]


def test_semver_order():
    order = ["2.1.1", "2.1.2-alpha.3", "2.1.2-beta.1", "2.1.2-beta.10", "2.1.2-rc.1", "2.1.2",
             "2.2.0", "10.0.0"]
    assert sorted(order, key=guard.parse) == order


def test_stable_must_be_higher_than_latest_stable():
    assert ok("2.2.0") and ok("2.1.2") and ok("3.0.0")
    assert not ok("2.1.1")        # already released
    assert not ok("2.1.0")        # released, and lower
    assert not ok("2.0.5")        # lower than 2.1.1


def test_stable_may_follow_its_own_betas():
    assert ok("2.1.2")            # 2.1.2 > 2.1.2-beta.2


def test_beta_must_be_higher_than_everything():
    assert ok("2.1.2-beta.3") and ok("2.2.0-beta.1")
    assert not ok("2.1.2-beta.2")     # exists
    assert not ok("2.1.2-beta.1")     # exists, lower
    assert not ok("2.1.1-beta.9")     # lower than the stable 2.1.1


def test_existing_release_and_drafts():
    msgs = guard.check("2.1.1", RELEASES)[1]
    assert "already exists" in msgs[0]
    draft = RELEASES + [rel("v2.2.0", draft=True)]
    good, msgs, _ = guard.check("2.2.0", draft)
    assert good and "draft" in msgs[0]
    # a draft never counts as "the latest": 2.1.5 is still fine next to a draft 2.2.0
    assert ok("2.1.5", draft)


def test_bad_versions_and_first_release():
    assert not ok("2.2")
    assert not ok("latest")
    assert ok("1.0.0", [])
    assert ok("1.0.0", [rel("update-feed")])


def test_command_line(tmp_path):
    f = tmp_path / "releases.json"
    f.write_text(json.dumps(RELEASES), encoding="utf-8")
    run = lambda v: subprocess.run([sys.executable, str(SCRIPT), v, str(f)],
                                   capture_output=True, text=True)
    good, bad = run("2.2.0"), run("2.1.0")
    assert good.returncode == 0 and "higher than v2.1.1" in good.stdout
    assert bad.returncode == 1 and bad.stdout.startswith("::error::")
