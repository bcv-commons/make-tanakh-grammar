#!/usr/bin/env python3
"""The published chapter format of a language's text repository (the make-tanakh-review template's FORMAT.md). Per chapter:

  <book>/<book>_<ccc>.md       YAML front matter (status), `# title`, `## headings`, then one verse per line `c:v<TAB>text`
                               (translatable text only: the invariant every other file refers to)
  <book>/<book>_<ccc>.units    per verse the clause units: `c:v<TAB>key:a-b key:c-d ...` (token ranges; `key:=` = no words of
                               its own; `key/2` = the Hebrew's own second segment of a discontinuous clause)
  <book>/<book>_<ccc>.notes    inline notes: `c:v<TAB>kind<TAB>anchor token<TAB>text`
  <book>/<book>_<ccc>.support  per token of the main draft: how many alternatives have the token in the same clause
  <book>/<book>_<ccc>.align    the draft's alignment to the source (written by the alignment step, not here)

Every sidecar's header carries `# text <sha256>`, the hash of the .md's verse lines, so each is checked against the text
alone; a mismatch is a stale sidecar and the publish gate refuses it. Tokens everywhere are the standard tokeniser's (the
toolkit's full_align.tokenize), 0-based within the verse; an anchor `a` means "before token a". A clause key is the span
`<first word>-<last word>` of the pinned Hebrew clause layout.

    . ./env.sh; python3 publish/chapter_format.py check DIR/GEN/GEN_002        (the files of one chapter against each other)"""
import collections, json, os, re, sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from shared import paths  # noqa: E402
import full_align as FA  # noqa: E402  (the toolkit: env.sh puts its scripts on the path)

STATUS_KEYS = ["maturity", "translation", "exegesis", "literary", "date"]
LAYOUT_DS = "bcv-commons/hebrew-clause-layout"


def layout_revision():
    """the pinned revision of the clause layout the units refer to"""
    try:
        d = json.load(open(paths.aligner_data("inputs.json")))["files"]
        for k, v in d.items():
            if k.startswith("hebrew-clause-layout/"):
                return v["url"].split("/resolve/")[1].split("/")[0]
    except (OSError, ValueError, KeyError, IndexError):
        pass
    return "unknown"


def layout_keys(book, ch):
    """{verse: ([unit key per segment, in layout order; a repeated clause gets key/2, key/3], [the layout rows])}"""
    import pyarrow.parquet as pq
    t = pq.read_table(paths.aligner_data("hebrew-clause-layout", f"clauses-{book}.parquet"), columns=["chapter", "verse", "seg", "clause_key", "words"])
    out = collections.defaultdict(list)
    for r in sorted((r for r in t.to_pylist() if r["chapter"] == ch), key=lambda r: r["seg"]):
        out[r["verse"]].append(r)
    keys = {}
    for v, rows in out.items():
        seen = collections.Counter(); ks = []; last = {}       # the clause's last word over all its segments
        for r in rows:
            w = list(r["words"]) if not isinstance(r["words"], str) else json.loads(r["words"].replace("'", '"'))
            if w:
                last[r["clause_key"]] = max(last.get(r["clause_key"], ""), w[-1])
        for r in rows:
            seen[r["clause_key"]] += 1
            ks.append(f"{r['clause_key']}-{last.get(r['clause_key'], r['clause_key'])}" + (f"/{seen[r['clause_key']]}" if seen[r["clause_key"]] > 1 else ""))
        keys[v] = (ks, rows)
    return keys


def ranges(ids):
    ids = sorted(set(ids)); out = []; s = None
    for i, p in enumerate(ids):
        if s is None:
            s = p
        if i + 1 == len(ids) or ids[i + 1] != p + 1:
            out.append(f"{s}" if s == p else f"{s}-{p}"); s = None
    return ",".join(out)


def front_matter(status, book, ch, extra=()):
    y = [f"book: {book}", f"chapter: {ch}"] + [f"{k}: {json.dumps(v, ensure_ascii=False)}" for k, v in extra] + ["status:"]
    for i, (lab, val) in enumerate(status):
        key = STATUS_KEYS[i] if i < len(STATUS_KEYS) else re.sub(r"\W+", "_", lab.lower())
        y.append(f"  {key}: {json.dumps(val, ensure_ascii=False)}")
    if status:
        y.append("status_labels: " + json.dumps([l for l, _ in status], ensure_ascii=False))
    return "---\n" + "\n".join(y) + "\n---\n"


def text_hash_of(verses, ch):
    return FA.text_hash(ch, sorted(verses.items()))


def write_chapter(m, book, out_dir, units, method, extra=()):
    """m = {"chapter", "title", "status" [(label, value)], "headings" [(verse, text)], "verses" {v: text}, "notes" [(v, kind, anchor,
    text)]} -> the .md, .units and .notes; returns the files' common stem"""
    stem = os.path.join(out_dir, book, f"{book}_{m['chapter']:03d}"); os.makedirs(os.path.dirname(stem), exist_ok=True)
    ch = m["chapter"]; hv = collections.defaultdict(list)
    for v, h in m["headings"]:
        hv[v].append(h)
    md = [front_matter(m["status"], book, ch, extra), f"# {m['title']}\n" if m["title"] else ""]
    for v in sorted(m["verses"]):
        for h in hv.get(v, []):
            md.append(f"\n## {h}\n")
        md.append(f"{ch}:{v}\t{m['verses'][v]}\n")
    open(stem + ".md", "w", encoding="utf-8").write("".join(md))
    h = f"# text {text_hash_of(m['verses'], ch)}\n"
    open(stem + ".units", "w", encoding="utf-8").write(
        f"# units: {method}; layout {LAYOUT_DS}@{layout_revision()}; token ranges of the standard tokeniser\n" + h
        + "".join(f"{ch}:{v}\t{units.get(v, '')}\n" for v in sorted(m["verses"])))
    open(stem + ".notes", "w", encoding="utf-8").write(
        "# notes: verse, kind, anchor token, text\n" + h + "".join(f"{ch}:{v}\t{k}\t{a}\t{t}\n" for v, k, a, t in m["notes"]))
    return stem


def read_md(path):
    """-> (status [(key, value)], labels, title, headings [(verse, text)], verses {v: text}, chapter)"""
    txt = open(path, encoding="utf-8").read().splitlines()
    status, labels, title, headings, verses, ch = [], [], "", [], {}, None
    i = 0
    if txt and txt[0] == "---":
        i = 1
        while i < len(txt) and txt[i] != "---":
            l = txt[i]; i += 1
            m = re.match(r"  (\w+): (.*)$", l)
            if m:
                status.append((m.group(1), json.loads(m.group(2)))); continue
            m = re.match(r"status_labels: (.*)$", l)
            if m:
                labels = json.loads(m.group(1)); continue
            m = re.match(r"chapter: (\d+)$", l)
            if m:
                ch = int(m.group(1))
        i += 1
    pending = []
    for l in txt[i:]:
        if l.startswith("# "):
            title = l[2:].strip(); continue
        if l.startswith("## "):
            pending.append(l[3:].strip()); continue
        m = re.match(r"(\d+):(\d+)\t(.*)$", l)
        if m:
            v = int(m.group(2)); ch = ch or int(m.group(1))
            headings += [(v, h) for h in pending]; pending = []
            verses[v] = m.group(3)
    return status, labels, title, headings, verses, ch


def check_files(stem):
    """the chapter's files against each other -> list of problems"""
    problems = []
    status, labels, title, headings, verses, ch = read_md(stem + ".md")
    want = text_hash_of(verses, ch)
    for ext in (".align", ".units", ".notes", ".support", ".trace"):
        if os.path.exists(stem + ext):
            head = "".join(open(stem + ext, encoding="utf-8").readlines()[:3])
            m = re.search(r"# text ([0-9a-f]{64})", head)
            if not m or m.group(1) != want:
                problems.append(f"{ext[1:]}: text hash does not match the verses (stale sidecar)")
    ntok = {v: len(FA.tokenize(t)) for v, t in verses.items()}
    for name in (".units", ".notes"):
        if not os.path.exists(stem + name):
            continue
        for n, l in enumerate(open(stem + name, encoding="utf-8"), 1):
            if l.startswith("#") or not l.strip():
                continue
            f = l.rstrip("\n").split("\t"); m = re.match(r"(\d+):(\d+)$", f[0])
            if not m or int(m.group(2)) not in verses:
                problems.append(f"{name} line {n}: unknown verse {f[0]}"); continue
            v = int(m.group(2))
            if name == ".units":
                seen = set()
                for e in f[1].split():
                    k, _, rng = e.partition(":")
                    if k in seen:
                        problems.append(f".units {f[0]}: key {k} twice")
                    seen.add(k); span = k.split("/")[0]
                    if not re.fullmatch(r"\d{11,12}-\d{11,12}", span) or span.split("-")[0] > span.split("-")[1]:
                        problems.append(f".units {f[0]}: key {k} is not a first-last span")
                    for p in FA.ids_of(rng) if rng != "=" else []:
                        if p >= ntok[v]:
                            problems.append(f".units {f[0]}: token {p} beyond the verse ({ntok[v]} tokens)")
            elif int(f[2]) > ntok[v]:
                problems.append(f"{name} {f[0]}: anchor {f[2]} beyond the verse ({ntok[v]} tokens)")
    if os.path.exists(stem + ".support"):                 # one digit per token of the verse
        for l in open(stem + ".support", encoding="utf-8"):
            if l.startswith("#") or not l.strip():
                continue
            f = l.rstrip("\n").split("\t"); v = int(f[0].split(":")[1]) if ":" in f[0] else None
            if v not in verses or len(f) < 2 or not re.fullmatch(r"\d*", f[1]) or len(f[1]) != ntok[v]:
                problems.append(f".support {f[0]}: not one digit per token")
    return problems


if __name__ == "__main__":
    if len(sys.argv) != 3 or sys.argv[1] != "check":
        sys.exit(__doc__)
    bad = check_files(sys.argv[2]); print("\n".join(bad) if bad else "ok"); sys.exit(1 if bad else 0)
