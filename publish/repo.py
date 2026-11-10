#!/usr/bin/env python3
"""A language's text repository under global-tanakh, created from here: the review tool's template at its pin, filled in for
the language, with `main` and `approved` and the format check required on both.

    . ./env.sh
    python3 publish/repo.py --lang zin                 # the dry run (default): everything is built and checked locally
    python3 publish/repo.py --lang zin --create        # creates global-tanakh/<code> on GitHub (outward: the user's go)

The dry run
  1. fetches the template (bcv-commons/make-tanakh-review, folder template/, at the commit in shared/pins.py) into
     $MAKE_TANAKH_PRIVATE/publish/template/<commit>/ (once);
  2. builds the first commit in $MAKE_TANAKH_PRIVATE/publish/<code>/init/: the template with the language's name and code
     filled in, .tanakh/publisher.json naming this checkout ($MAKE_TANAKH_PUBLISHER) as the language's one publisher, and
     .tanakh/template.json saying which template commit it came from;
  3. runs the template's own format check on it (node .github/check/validate.mjs), as GitHub will;
  4. makes a local bare repository $MAKE_TANAKH_PRIVATE/publish/<code>/remote.git with both branches: a stand-in for the
     GitHub repository, so that publish/push.py can be tried against it (--repo <that path>);
  5. prints what --create would do.

--create does those GitHub steps: the repository (public), the first commit pushed to main and approved, the topics, and a
ruleset on both branches: no deletion, no force push, the format check required. Organisation admins may bypass the ruleset
(the seed pushes straight to main and approved until the review tool's GitHub App takes that role). An existing repository
is never touched."""
import argparse, datetime, glob, io, json, os, shutil, subprocess, sys, tarfile

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.dirname(HERE))
from shared import paths, pins  # noqa: E402

ORG = os.environ.get("GLOBAL_TANAKH_ORG", "global-tanakh")
BOT = ("make-tanakh-review[bot]", "make-tanakh-review@users.noreply.github.com")
PIN = pins.PINS.get("make-tanakh-review")           # the template's repository and commit
CHECK = "format"                                   # the job of the template's .github/workflows/validate.yml


def sh(*cmd, cwd=None, check=True, capture=True):
    r = subprocess.run(cmd, cwd=cwd, capture_output=capture, text=True)
    if check and r.returncode:
        sys.exit(f"failed: {' '.join(cmd)}\n{(r.stderr or '')[-800:]}")
    return r


def template():
    """the template's files at the pinned commit -> their folder"""
    pin = PIN; d = paths.private("publish", "template", pin["commit"][:12])
    if os.path.exists(os.path.join(d, "FORMAT.md")):
        return d
    data = subprocess.run(["gh", "api", f"repos/{pin['gh']}/tarball/{pin['commit']}"], capture_output=True).stdout
    tmp = d + ".part"; shutil.rmtree(tmp, ignore_errors=True); os.makedirs(tmp)
    with tarfile.open(fileobj=io.BytesIO(data), mode="r:gz") as t:
        for m in t.getmembers():
            parts = m.name.split("/", 2)
            if len(parts) == 3 and parts[1] == "template" and m.isfile() and ".." not in parts[2]:
                dst = os.path.join(tmp, parts[2]); os.makedirs(os.path.dirname(dst), exist_ok=True)
                with t.extractfile(m) as src, open(dst, "wb") as out:
                    out.write(src.read())
    if not os.path.exists(os.path.join(tmp, "FORMAT.md")):
        sys.exit("the template was not found at the pinned commit")
    os.replace(tmp, d)
    return d


def validate(root, keys_cache=None):
    """the template's format check on a repository folder -> (ok, last lines). With the clause keys of the pinned layout when
    they can be fetched (layout_keys.py; public data, cached)."""
    cache = keys_cache or paths.private("publish", "template", "hcl-cache"); os.makedirs(cache, exist_ok=True)
    books = [b for b in os.listdir(root) if len(b) == 3 and b.isupper() and os.path.isdir(os.path.join(root, b))]
    args = ["node", os.path.join(root, ".github", "check", "validate.mjs"), root]
    if books:
        kj = os.path.join(cache, "keys.json")
        r = subprocess.run([sys.executable, "-I", os.path.join(root, ".github", "check", "layout_keys.py"), root, kj, "--cache", cache],
                           capture_output=True, text=True)
        if r.returncode == 0:
            args += ["--keys", kj]
    r = subprocess.run(args, capture_output=True, text=True)
    return r.returncode == 0, (r.stdout + r.stderr).strip().splitlines()


def publisher_login():
    """the GitHub login the drafts are pushed from: $MAKE_TANAKH_PUBLISHER_LOGIN (a machine account, option B), else the login
    `gh` is signed in with (option A, the default: each user of the template publishes under their own login)"""
    login = os.environ.get("MAKE_TANAKH_PUBLISHER_LOGIN")
    if login:
        return login
    r = subprocess.run(["gh", "api", "user", "-q", ".login"], capture_output=True, text=True)
    if r.returncode or not r.stdout.strip():
        sys.exit("no GitHub login: sign in with `gh auth login`, or set MAKE_TANAKH_PUBLISHER_LOGIN (a machine account)")
    return r.stdout.strip()


def build_init(cfg, code, tdir):
    out = paths.private("publish", code, "init"); shutil.rmtree(out, ignore_errors=True); shutil.copytree(tdir, out)
    name = cfg["name"]
    for f in ("README.md", "CODEOWNERS"):
        p = os.path.join(out, f); s = open(p, encoding="utf-8").read()
        open(p, "w", encoding="utf-8").write(s.replace("LANG_NAME", name).replace("LANG_CODE", code))
    pin = PIN; today = datetime.date.today().isoformat()
    login = publisher_login()                               # the GitHub login our pushes come from: the review CI's derived-files notice
    json.dump({"publisher": os.environ.get("MAKE_TANAKH_PUBLISHER", "make-tanakh-grammar"), "login": login,
               "name": "make-tanakh-grammar", "url": "https://github.com/bcv-commons/make-tanakh-grammar",
               "language": name, "code": code, "named": today},
              open(os.path.join(out, ".tanakh", "publisher.json"), "w", encoding="utf-8"), indent=1, ensure_ascii=False)
    json.dump({"code": code, "name": name, "native": cfg.get("native", name), "bcp47": cfg.get("bcp47", cfg["iso"])},   # FORMAT.md section 11
              open(os.path.join(out, ".tanakh", "language.json"), "w", encoding="utf-8"), indent=1, ensure_ascii=False)
    json.dump({"repo": pin["repo"], "commit": pin["commit"], "copied": today},
              open(os.path.join(out, ".tanakh", "template.json"), "w", encoding="utf-8"), indent=1)
    sh("git", "init", "-q", "-b", "main", out)
    sh("git", "-C", out, "add", "-A")
    sh("git", "-C", out, "-c", f"user.name={BOT[0]}", "-c", f"user.email={BOT[1]}", "commit", "-q", "-m",
       f"The {name} text repository, from the make-tanakh-review template ({pin['commit'][:7]})")
    sh("git", "-C", out, "branch", "approved")
    return out


def stand_in(init, code):
    bare = paths.private("publish", code, "remote.git"); shutil.rmtree(bare, ignore_errors=True)
    sh("git", "clone", "-q", "--bare", init, bare)
    return bare


def ruleset():
    return {"name": "main and approved", "target": "branch", "enforcement": "active",
            "conditions": {"ref_name": {"include": ["refs/heads/main", "refs/heads/approved"], "exclude": []}},
            "bypass_actors": [{"actor_id": 1, "actor_type": "OrganizationAdmin", "bypass_mode": "always"}],
            "rules": [{"type": "deletion"}, {"type": "non_fast_forward"},
                      {"type": "required_status_checks", "parameters": {"strict_required_status_checks_policy": False,
                                                                         "required_status_checks": [{"context": CHECK}]}}]}


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--lang", required=True); ap.add_argument("--create", action="store_true")
    a = ap.parse_args(); cfg = paths.config(a.lang); code = cfg.get("code", cfg["iso"]); full = f"{ORG}/{code}"
    exists = subprocess.run(["gh", "repo", "view", full, "--json", "name"], capture_output=True, text=True).returncode == 0
    tdir = template(); init = build_init(cfg, code, tdir); ok, lines = validate(init)
    print(f"template: {PIN['gh']}@{PIN['commit'][:12]} -> {tdir}")
    n = sum(len(fs) for d, _, fs in os.walk(init) if "/.git" not in d + "/")
    print(f"first commit: {init} ({n} files)")
    print("format check: " + ("passed" if ok else "FAILED") + " | " + (lines[-1] if lines else ""))
    if not ok:
        print("\n".join(lines[-15:])); sys.exit(2)
    bare = stand_in(init, code)
    print(f"local stand-in with main and approved: {bare}   (publish/push.py --lang {a.lang} --repo {bare})")
    print(f"GitHub: {full} " + ("EXISTS: it is never touched" if exists else "does not exist yet"))
    plan = [f"gh repo create {full} --public --description \"Tanakh drafts in {cfg['name']}, CC0: one verse per line, edited clause by clause\"",
            f"git push git@github.com:{full}.git main approved          (from {init})",
            f"gh repo edit {full} --add-topic global-tanakh --add-topic tanakh --add-topic bible-translation --add-topic {code}",
            f"gh api -X POST repos/{full}/rulesets   (main and approved: no deletion, no force push, check '{CHECK}' required; org admins may bypass)"]
    if not a.create:
        print("--create would:\n  " + "\n  ".join(plan) + "\ndry run: nothing sent"); return
    if exists:
        sys.exit(f"{full} exists: nothing done")
    sh("gh", "repo", "create", full, "--public", "--description", f"Tanakh drafts in {cfg['name']}, CC0: one verse per line, edited clause by clause")
    sh("git", "-C", init, "push", "-q", f"git@github.com:{full}.git", "main", "approved")
    sh("gh", "repo", "edit", full, "--add-topic", "global-tanakh", "--add-topic", "tanakh", "--add-topic", "bible-translation", "--add-topic", code)
    r = subprocess.run(["gh", "api", "-X", "POST", f"repos/{full}/rulesets", "--input", "-"], input=json.dumps(ruleset()), capture_output=True, text=True)
    print(f"created {full}: main and approved pushed; ruleset " + ("set" if r.returncode == 0 else "NOT set: " + r.stderr[-300:]))
    log = paths.private("publish", "log.tsv")
    open(log, "a", encoding="utf-8").write(f"{datetime.datetime.now(datetime.timezone.utc).strftime('%Y-%m-%dT%H:%MZ')}\t{a.lang}\t{full}\tcreate\t0\t\t"
                                          f"template {PIN['commit'][:12]}\n")


if __name__ == "__main__":
    main()
