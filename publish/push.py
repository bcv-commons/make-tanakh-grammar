#!/usr/bin/env python3
"""Publish a bundle of drafted Tanakh chapters (publish/bundle.py) to the language's text repository. Three modes, the
first the default:

  --check     the gates, and a dry run against the repository: which chapters would be added, proposed (present but
              different), unchanged, skipped. Nothing leaves the box.
  --seed      chapters absent from the repository: added to `main` and `approved`, as the bot. A chapter already there is
              never touched; alternatives of a chapter that has none yet are added with it.
  --propose   chapters present but different: a branch draft/<date> from main with the new text, pushed, and (GitHub) a
              pull request into main. People merge it by verse, or close it. Units of verses whose text did not change
              keep the people's cut; the alternatives of a proposed chapter are replaced as a whole.

    . ./env.sh
    python3 publish/push.py --lang xxx [--bundle DIR] [--repo org/lang | /path/to/bare.git] [--check | --seed | --propose]

The repository is `--repo org/lang` on GitHub (default $GLOBAL_TANAKH_ORG/<lang code>, through `gh`) or a local bare
repository (--propose then pushes the branch and opens no pull request). Every seed or propose run appends a line to
$MAKE_TANAKH_PRIVATE/publish/log.tsv.

The gates, all of them before anything is sent:
  rights      the language's rights table says the drafts may be published ("rights": {"publish": true}, with a note on
              who agreed: a draft made with a team's text among its inputs is published only with the team's consent)
  hold-out    a closed or held-out chapter is never published
  files       every chapter's files agree with each other (publish/chapter_format.py)
  Hebrew      no file holds Hebrew-script text beyond quotation, nor text of a source that is not free (tools/screen.py)
  publisher   the repository's .tanakh/publisher.json on main names this checkout ($MAKE_TANAKH_PUBLISHER)
The verbatim gate has done its work when the bundle was made; a bundle is never edited by hand.

Seeding and proposing on GitHub are outward actions: the person who runs them decides, per run."""
import argparse, collections, datetime, glob, json, os, re, shutil, subprocess, sys, tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.dirname(HERE))
from shared import holdout, paths, rights  # noqa: E402
from publish import chapter_format as CF  # noqa: E402

BOT = ("make-tanakh-review[bot]", "make-tanakh-review@users.noreply.github.com")
EXTS = (".md", ".units", ".notes", ".support")
ALT = ".tanakh/alternatives"
PUBLISHER = ".tanakh/publisher.json"


def die(msg):
    print("refused:", msg); sys.exit(2)


class Repo:
    """what the modes need from a repository: the files on a branch, and clone / commit / push; GitHub through gh + git, or
    a local bare repository"""

    def __init__(self, spec):
        self.local = os.path.isabs(spec) or spec.endswith(".git")
        self.spec = os.path.realpath(spec) if self.local else spec

    def files(self, branch):
        if self.local:
            r = subprocess.run(["git", "--git-dir", self.spec, "ls-tree", "-r", "--name-only", branch], capture_output=True, text=True)
            return set(r.stdout.split("\n")) - {""} if r.returncode == 0 else set()
        r = subprocess.run(["gh", "api", f"repos/{self.spec}/git/trees/{branch}?recursive=1"], capture_output=True, text=True)
        return {t["path"] for t in json.loads(r.stdout).get("tree", []) if t["type"] == "blob"} if r.returncode == 0 else set()

    def read(self, branch, path):
        if self.local:
            r = subprocess.run(["git", "--git-dir", self.spec, "show", f"{branch}:{path}"], capture_output=True, text=True)
        else:
            r = subprocess.run(["gh", "api", f"repos/{self.spec}/contents/{path}?ref={branch}", "-H", "Accept: application/vnd.github.raw+json"],
                               capture_output=True, text=True)
        return r.stdout if r.returncode == 0 else None

    def clone(self, branch, into):
        if self.local:
            subprocess.run(["git", "clone", "-q", "-b", branch, self.spec, into], check=True)
        else:
            subprocess.run(["gh", "repo", "clone", self.spec, into, "--", "-q", "-b", branch], check=True)

    def commit_push(self, w, branch, msg, new_branch=None):
        if new_branch:
            subprocess.run(["git", "-C", w, "checkout", "-q", "-b", new_branch], check=True)
        subprocess.run(["git", "-C", w, "add", "-A"], check=True)
        subprocess.run(["git", "-C", w, "-c", f"user.name={BOT[0]}", "-c", f"user.email={BOT[1]}", "commit", "-q", "-m", msg], check=True)
        subprocess.run(["git", "-C", w, "push", "-q", "origin", new_branch or branch], check=True)
        return subprocess.run(["git", "-C", w, "rev-parse", "--short", "HEAD"], capture_output=True, text=True).stdout.strip()

    def pull_request(self, branch, title, body):
        if self.local:
            return "(local repository: branch pushed, no pull request)"
        r = subprocess.run(["gh", "pr", "create", "-R", self.spec, "--base", "main", "--head", branch, "--title", title, "--body", body],
                           capture_output=True, text=True, check=True)
        return r.stdout.strip()


def publisher_ok(repo):
    """-> (ok, message): the repository names its one publisher in .tanakh/publisher.json on main; this checkout publishes
    as $MAKE_TANAKH_PUBLISHER. A repository without the file is refused."""
    me = os.environ.get("MAKE_TANAKH_PUBLISHER")
    if not me:
        return False, "MAKE_TANAKH_PUBLISHER is not set (env.sh)"
    raw = repo.read("main", PUBLISHER)
    if raw is None:
        return False, f"{PUBLISHER} is not on main (or the repository cannot be read): the language's publisher is named first"
    try:
        who = json.loads(raw).get("publisher")
    except ValueError:
        return False, f"{PUBLISHER} does not parse"
    if who != me:
        return False, f"{PUBLISHER} names {who!r}; this checkout publishes as {me!r}: not ours to publish"
    return True, f"publisher {who} (this checkout) per {PUBLISHER}"


def body(text):
    """the verse lines and headings of a chapter .md (not the front matter: its date changes with every run)"""
    return "\n".join(l for l in text.split("\n") if re.match(r"\d+:\d+\t", l) or l.startswith("## "))


def merge_units(old_units, new_units, old_md, new_md):
    """a proposal re-cuts only the verses whose text changed; the others keep the people's units"""
    vs = lambda t: {l.split("\t", 1)[0]: l for l in t.split("\n") if re.match(r"\d+:\d+\t", l)}
    ov, nv = vs(old_md), vs(new_md)
    old = {l.split("\t", 1)[0]: l for l in old_units.split("\n") if "\t" in l and not l.startswith("#")}
    out = []
    for l in new_units.rstrip("\n").split("\n"):          # header lines (with the new text hash) come from the new file
        k = l.split("\t", 1)[0]
        out.append(old[k] if k in old and ov.get(k) == nv.get(k) else l)
    return "\n".join(out) + "\n"


def chapters_of(bundle, books, chapters, shut):
    """[(book, chapter, status)] of the bundle's main chapters: ok | held out"""
    out = []
    for f in sorted(glob.glob(os.path.join(bundle, "*", "*_[0-9][0-9][0-9].md"))):
        b, ch = os.path.basename(f)[:-7], int(f[-6:-3])
        if (books and b not in books) or (chapters and ch not in chapters):
            continue
        out.append((b, ch, "held out" if shut(b, ch) else "ok"))
    return out


def chapter_files(bundle, b, ch):
    """the bundle's files of one chapter, relative: the main draft's, and each alternative's"""
    main = [f"{b}/{b}_{ch:03d}{e}" for e in EXTS if os.path.exists(os.path.join(bundle, f"{b}/{b}_{ch:03d}{e}"))]
    alt = sorted(os.path.relpath(f, bundle) for f in glob.glob(os.path.join(bundle, ALT, "*", b, f"{b}_{ch:03d}.*")))
    return main, alt


def screen(files):
    """tools/screen.py on the files: Hebrew beyond quotation and non-free source text refuse. Its test for word forms of a
    protected translation is reported, not applied: a draft in the team's language uses the team's words, and what guards
    the team's text here is the verbatim gate of the bundle."""
    sys.path.insert(0, os.path.join(os.path.dirname(HERE), "tools"))
    import screen as SC
    s = SC.Screen(); bad, forms = 0, 0
    for p in files:
        hard = []
        for x in s.check(p, open(p, "rb").read()):
            if re.match(r"line \d+: Kuni word forms", x):
                forms += 1; continue
            hard.append(x)
        if hard:
            bad += 1; print(f"REFUSED {p}"); [print("    " + x) for x in hard[:10]]
    print(f"screen: {len(files)} files, {bad} refused" + (f"; {forms} lines use words of a protected translation (reported, not applied)" if forms else ""))
    return bad == 0


def plan(repo, bundle, chs):
    """-> {(book, chapter): action}: add | propose | same"""
    have = repo.files("main"); out = {}
    for b, ch, st in chs:
        if st != "ok":
            continue
        rel = f"{b}/{b}_{ch:03d}.md"
        if rel not in have:
            out[(b, ch)] = "add"
        else:
            old = repo.read("main", rel); new = open(os.path.join(bundle, rel), encoding="utf-8").read()
            out[(b, ch)] = "same" if old is not None and body(old) == body(new) else "propose"
    return out, have


def log_line(a, action, items, ref):
    d = paths.private("publish"); os.makedirs(d, exist_ok=True)
    now = datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%dT%H:%MZ")
    line = f"{now}\t{a.lang}\t{a.repo_spec}\t{a.bundle}\t{action}\t{len(items)}\t{' '.join(f'{b}{ch}' for b, ch in items)}\t{ref}\n"
    open(os.path.join(d, "log.tsv"), "a", encoding="utf-8").write(line); print(line.strip())


def put(bundle, w, rels):
    for rel in rels:
        os.makedirs(os.path.dirname(os.path.join(w, rel)), exist_ok=True); shutil.copy(os.path.join(bundle, rel), os.path.join(w, rel))


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--lang", required=True); ap.add_argument("--bundle"); ap.add_argument("--repo")
    ap.add_argument("--book", nargs="*"); ap.add_argument("--chapters", type=int, nargs="*"); ap.add_argument("--tag")
    g = ap.add_mutually_exclusive_group()
    for m in ("check", "seed", "propose"):
        g.add_argument("--" + m, dest="mode", action="store_const", const=m)
    ap.set_defaults(mode="check"); a = ap.parse_args()
    cfg = paths.config(a.lang); code = cfg.get("code", cfg["iso"])
    a.bundle = bundle = os.path.realpath(a.bundle or paths.private("publish", a.lang, "bundle"))
    chs = chapters_of(bundle, [b.upper() for b in a.book or []], a.chapters, holdout.shut(cfg))
    if not chs:
        die(f"no chapters in {bundle} for the selection")
    files, problems = [], 0
    for b, ch, st in chs:
        if st != "ok":
            continue
        main_f, alt_f = chapter_files(bundle, b, ch); files += main_f + alt_f
        for stem in [os.path.join(bundle, f"{b}/{b}_{ch:03d}")] + sorted({os.path.join(bundle, f[:-len(os.path.splitext(f)[1])]) for f in alt_f}):
            for p in CF.check_files(stem):
                problems += 1; print(f"PROBLEM {os.path.relpath(stem, bundle)}: {p}")
    if problems:
        die(f"{problems} problems in the bundle's files: make the bundle again")
    if not screen([os.path.join(bundle, f) for f in files]):
        die("the screen refused a file of the bundle")
    repo = Repo(a.repo or f"{os.environ.get('GLOBAL_TANAKH_ORG', 'global-tanakh')}/{code}")
    a.repo_spec = repo.spec; P, have = plan(repo, bundle, chs); counts = collections.Counter(P.values()); skipped = [(b, ch) for b, ch, st in chs if st != "ok"]
    print(f"repository {repo.spec}: add {counts['add']}, propose {counts['propose']}, unchanged {counts['same']}, held out (never published) {len(skipped)}"
          + (" (" + ", ".join(f"{b} {ch}" for b, ch in skipped) + ")" if skipped else ""))
    for (b, ch), act in sorted(P.items()):
        if act != "same":
            print(f"  {act:8s} {b} {ch}")
    may = rights.allowed(cfg, "publish"); ok, msg = publisher_ok(repo)
    print(("" if may else "NOT ALLOWED: ") + ("the rights table allows publishing the drafts" if may else
          "the rights table does not allow publishing the drafts (\"rights\": {\"publish\": true}, with a note on who agreed)"))
    print(("" if ok else "NOT ALLOWED: ") + msg)
    if a.mode == "check":
        print("check only; nothing sent"); return
    rights.check(cfg, "publish")
    if not ok:
        die(msg)
    readme = f"{ALT}/README.md"
    with tempfile.TemporaryDirectory() as tmp:
        if a.mode == "seed":
            items = [k for k, act in P.items() if act == "add"]
            late = [k for k, act in P.items() if act == "same" and any(f not in have for f in chapter_files(bundle, *k)[1])]
            if not items and not late:
                print("nothing to seed"); return
            refs = []
            for br in ("main", "approved"):
                w = os.path.join(tmp, br); repo.clone(br, w)
                for b, ch in items:
                    main_f, alt_f = chapter_files(bundle, b, ch)
                    if not os.path.exists(os.path.join(w, main_f[0])):
                        put(bundle, w, main_f + alt_f)
                for b, ch in late:                                   # a published chapter that has no alternatives yet
                    put(bundle, w, [f for f in chapter_files(bundle, b, ch)[1] if not os.path.exists(os.path.join(w, f))])
                if os.path.exists(os.path.join(bundle, readme)):
                    put(bundle, w, [readme])
                if subprocess.run(["git", "-C", w, "status", "--porcelain"], capture_output=True, text=True).stdout.strip():
                    refs.append(f"{br}@{repo.commit_push(w, br, f'Seed: {len(items)} drafted chapter(s)' + (f', alternatives for {len(late)}' if late else ''))}")
            log_line(a, "seed", items + late, " ".join(refs))
        else:
            items = [k for k, act in P.items() if act == "propose"]
            if not items:
                print("nothing to propose"); return
            w = os.path.join(tmp, "w"); repo.clone("main", w)
            for b, ch in items:
                main_f, alt_f = chapter_files(bundle, b, ch); md = main_f[0]
                old_md = open(os.path.join(w, md), encoding="utf-8").read(); new_md = open(os.path.join(bundle, md), encoding="utf-8").read()
                for rel in main_f:
                    dst = os.path.join(w, rel)
                    if rel.endswith(".units") and os.path.exists(dst):
                        open(dst, "w", encoding="utf-8").write(merge_units(open(dst, encoding="utf-8").read(),
                                                                           open(os.path.join(bundle, rel), encoding="utf-8").read(), old_md, new_md))
                    else:
                        put(bundle, w, [rel])
                for old in glob.glob(os.path.join(w, ALT, "*", b, f"{b}_{ch:03d}.*")):      # alternatives: replaced as a whole
                    os.remove(old)
                put(bundle, w, alt_f)
            if os.path.exists(os.path.join(bundle, readme)):
                put(bundle, w, [readme])
            br = "draft/" + datetime.date.today().isoformat() + (f"-{a.tag}" if a.tag else "")
            sha = repo.commit_push(w, "main", f"Re-draft: {len(items)} chapter(s)", new_branch=br)
            pr = repo.pull_request(br, f"Re-draft of {len(items)} chapter(s): " + " ".join(f"{b} {ch}" for b, ch in items),
                                   "New drafts; merge by verse in the review tool, or close.")
            log_line(a, "propose", items, f"{br}@{sha} {pr}")


if __name__ == "__main__":
    main()
