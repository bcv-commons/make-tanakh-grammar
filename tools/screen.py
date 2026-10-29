#!/usr/bin/env python3
"""Screen what goes into git: this repo is public, the texts it learns from are not (RELATIONS.md, section 6).

A file is refused when it holds
  - a corpus or binary: .db, .sqlite, .parquet, .pt, .zip, ...; a NUL byte or text that is not UTF-8; more than 1 MB;
  - Hebrew-script text beyond a few words that is not the WLC (MACULA Hebrew, the work repo's orig/heb.sqlite),
    compared without points and accents: a run of more than HEB_RUN words (one-letter prefixes not counted), or more
    than HEB_TOTAL such words in the file. This also covers HEBM95 (Bible Society in Israel) and the BHSA's text, which
    differs from the WLC only where it is not ours to quote. A file tools/screen_allow.txt admits with `hebrew-ok:`
    (screened by hand) is not checked;
  - Kuni word forms (the Kuni NT's vocabulary, read from the work repo, never stored here): words the BSB does not
    use, not in capitals (book codes, acronyms), of 4 letters or more or with a letter outside ASCII, and not admitted
    on purpose in tools/screen_allow.txt (a name, a form the store publishes anyway; each with its reason). A line
    that is a credited quotation (a reference such as `JON 1:3` and the credit "Kuni NT" or ebible.org/kvg) may carry
    up to MAX_QUOTE of them, in at most MAX_QUOTES lines per file (the work repo's docs/licensing.md: short, few,
    credited);
  - TBTA data: its analysed-verse codes, or a run of TBTA_N words of its English verse text that the BSB does not have;
  - BHSA data: MIN_ETCBC or more lexemes in the ETCBC's transliteration (`BR>[`, `>LHJM/`).
URLs are not read for Kuni forms or TBTA text (an id in a link is no word).

Usage: python3 tools/screen.py [--staged | --all | FILE ...]
    --staged (default; .githooks/pre-commit): the staged content of every added or changed file
    --all: every file git would track (tracked, plus untracked ones .gitignore admits)
    FILE: these files as they are on disk
The sources are found through MAKE_TANAKH_WORK (. ./env.sh); a missing source is reported and its check made strict
(Hebrew: every run of more than HEB_RUN words is refused) or skipped (Kuni, TBTA). Lookup tables are cached, as hashes,
in $MAKE_TANAKH_PRIVATE/.screen-cache/. Exit status 1 when a file is refused."""
import csv, glob, hashlib, os, pickle, re, sqlite3, subprocess, sys, unicodedata

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
WORK = os.environ.get("MAKE_TANAKH_WORK", os.path.expanduser("~/dev/make-tanakh-work"))
PRIVATE = os.environ.get("MAKE_TANAKH_PRIVATE", os.path.join(ROOT, "private"))
CACHE = os.path.join(PRIVATE, ".screen-cache")

BINARY_EXT = {".db", ".sqlite", ".sqlite3", ".parquet", ".pt", ".bin", ".safetensors", ".zip", ".gz", ".xz", ".tar",
              ".pickle", ".pkl", ".npy", ".npz", ".arrow", ".usfm", ".sfm", ".usj", ".usx"}
MAX_BYTES = 1_000_000
HEB_RUN, HEB_TOTAL = 3, 12
MAX_QUOTE, MAX_QUOTES = 15, 5
TBTA_N = 8
MIN_ETCBC = 5
ALLOW = os.path.join(ROOT, "tools", "screen_allow.txt")
SELF = {"tools/screen.py", "tools/screen_allow.txt"}       # not checked for Kuni forms: they name what they admit

HEB_WORD = re.compile(r"[\u05D0-\u05EA\uFB1D-\uFB4F][\u0591-\u05C7\u05D0-\u05EA\uFB1D-\uFB4F]*")
HEB_RUN_RE = re.compile(r"(?:[\u05D0-\u05EA\uFB1D-\uFB4F][\u0591-\u05C7\u05D0-\u05EA\uFB1D-\uFB4F]*"
                        r"[ \t\u05BE\u05C0\u05C3.:\u05F3\u05F4-]*)+")   # a comma, ";", "|" or "/" ends a run: a list is no quotation
WORD = re.compile(r"[^\W\d_](?:[^\W\d_]|[\u0300-\u036F])*")
REF = re.compile(r"\b[1-3A-Z][A-Z]{2} \d+:\d+")
KUNI_CREDIT = re.compile(r"Kuni NT|ebible\.org/kvg", re.I)
TBTA_CODE = re.compile(r"~\\(?:wd|tg|lu)\b|\b[A-Za-z]-[0-9A-Z][0-9A-Za-z]{2,}\.{4,}")
ETCBC_LEX = re.compile(r"(?<![\w>&<#@])[A-Z>&<#@]{2,}[\[/]=?(?![\w])")
URL = re.compile(r"https?://\S+")


def consonants(s):
    """Hebrew without points and accents; maqaf, paseq and sof pasuq as spaces."""
    s = unicodedata.normalize("NFD", s)
    s = re.sub(r"[\u05BE\u05C0\u05C3]", " ", s)
    return re.sub(r"[\u0591-\u05BD\u05BF-\u05C2\u05C4-\u05C7]", "", s)


def heb_words(s):
    return re.findall(r"[\u05D0-\u05EA]+", consonants(s))


def h(words):
    return hashlib.blake2b(" ".join(words).encode(), digest_size=8).digest()


def cached(name, sources, build):
    """build() once per state of its source files (path, size, mtime), kept in the private cache."""
    sig = [(p, os.path.getsize(p), int(os.path.getmtime(p))) for p in sources]
    path = os.path.join(CACHE, name + ".pickle")
    try:
        with open(path, "rb") as f:
            old_sig, data = pickle.load(f)
        if old_sig == sig:
            return data
    except (OSError, EOFError, pickle.UnpicklingError, ValueError):
        pass
    data = build()
    os.makedirs(CACHE, exist_ok=True)
    with open(path, "wb") as f:
        pickle.dump((sig, data), f)
    return data


def load_wlc():
    """The WLC as one string of consonantal words, ' ' at both ends; None without orig/heb.sqlite."""
    db = os.path.join(WORK, "orig", "heb.sqlite")
    if not os.path.exists(db):
        return None

    def build():
        words, verse, last = [], [], None
        for b, c, v, t, a in sqlite3.connect(db).execute("select book, ch, v, text, after from tokens order by key"):
            if (b, c, v) != last and verse:
                words += heb_words("".join(verse))
                verse = []
            last = (b, c, v)
            verse.append((t or "") + (a or ""))
        words += heb_words("".join(verse))
        return " " + " ".join(words) + " "
    return cached("wlc", [db], build)


BSB_GLOB = "reference/BSB/*.txt"


def bsb_words():
    """[[word]] per line of the BSB (casefolded); [] without it."""
    out = []
    for f in sorted(glob.glob(os.path.join(WORK, BSB_GLOB))):
        for line in open(f, encoding="utf-8"):
            out.append([w.casefold() for w in WORD.findall(unicodedata.normalize("NFC", line))])
    return out


def load_kuni():
    """Word forms of the Kuni NT (3 letters or more) that the BSB does not use, as hashes; None without the text."""
    kuni = sorted(glob.glob(os.path.join(WORK, "import/non-free/kvg/KVG-KuNT/text/*.txt")))
    if not kuni:
        return None
    bsb = sorted(glob.glob(os.path.join(WORK, BSB_GLOB)))

    def build():
        words = set()
        for f in kuni:
            for line in open(f, encoding="utf-8"):
                if not (line.startswith("!!<") or line.startswith("=")):
                    words |= {w.casefold() for w in WORD.findall(unicodedata.normalize("NFC", line)) if len(w) >= 3}
        words -= {w for ws in bsb_words() for w in ws}
        return {h([w]) for w in words if not re.fullmatch(r"v\d*", w)}
    return cached("kuni", kuni + bsb, build)


def load_tbta():
    """TBTA_N-word runs of TBTA's English verse text (the 'Verse' column of its book tables), as hashes."""
    files = sorted(glob.glob(os.path.join(WORK, "download/tbta/csv/TBTA_csv/*.csv")))
    if not files:
        return None
    bsb = sorted(glob.glob(os.path.join(WORK, BSB_GLOB)))

    def build():
        grams = set()
        csv.field_size_limit(1 << 30)
        for f in files:
            with open(f, encoding="utf-8", errors="replace", newline="") as fh:
                r = csv.DictReader(fh)
                if not r.fieldnames or "Verse" not in r.fieldnames or "AnalyzedVerse" not in r.fieldnames:
                    continue
                for row in r:
                    ws = [w.casefold() for w in WORD.findall(row["Verse"] or "")]
                    grams |= {h(ws[i:i + TBTA_N]) for i in range(len(ws) - TBTA_N + 1)}
        for ws in bsb_words():             # what the BSB says too is common English, not TBTA's
            grams -= {h(ws[i:i + TBTA_N]) for i in range(len(ws) - TBTA_N + 1)}
        return grams
    return cached("tbta", files + bsb, build)


class Screen:
    def __init__(self):
        self.wlc, self.kuni, self.tbta = load_wlc(), load_kuni(), load_tbta()
        self.allow, self.hebrew_ok = set(), set()
        if os.path.exists(ALLOW):
            for line in open(ALLOW, encoding="utf-8"):
                w = line.split("#")[0].strip()
                if w.startswith("hebrew-ok:"):
                    self.hebrew_ok.add(w.split(":", 1)[1].strip())
                elif w:
                    self.allow.add(unicodedata.normalize("NFC", w).casefold())
        self.notes = []
        if self.wlc is None:
            self.notes.append(f"no {WORK}/orig/heb.sqlite: every Hebrew run of more than {HEB_RUN} words is refused")
        if self.kuni is None:
            self.notes.append("no Kuni text in the work repo: Kuni check skipped")
        if self.tbta is None:
            self.notes.append("no TBTA tables in the work repo: TBTA text check skipped")

    def in_wlc(self, words):
        return self.wlc is not None and (" " + " ".join(words) + " ") in self.wlc

    def check(self, path, data):
        """[problem] for one file's bytes."""
        ext = os.path.splitext(path)[1].lower()
        if ext in BINARY_EXT:
            return [f"{ext} files are never committed"]
        if len(data) > MAX_BYTES:
            return [f"{len(data):,} bytes (more than {MAX_BYTES:,}): a corpus or a run output?"]
        if b"\0" in data:
            return ["binary (NUL bytes)"]
        try:
            text = unicodedata.normalize("NFC", data.decode("utf-8"))
        except UnicodeDecodeError:
            return ["not UTF-8 text"]
        out = []
        if path not in self.hebrew_ok:
            out += self.hebrew(text)
        words = URL.sub(" ", text)
        if path not in SELF:
            out += self.kuni_forms(words)
        out += self.tbta_text(words)
        lex = ETCBC_LEX.findall(text)
        if len(lex) >= MIN_ETCBC:
            out.append(f"{len(lex)} ETCBC lexemes (BHSA data?): {', '.join(sorted(set(lex))[:5])}")
        return out

    def hebrew(self, text):
        out, loose, singles = [], 0, set()
        for m in HEB_RUN_RE.finditer(text):
            ws = heb_words(m[0])
            if not ws or self.in_wlc(ws):
                continue
            line = text.count("\n", 0, m.start()) + 1
            long = [w for w in ws if len(w) > 1]          # one-letter prefixes (a list of them) are grammar, not text
            if len(long) > HEB_RUN:
                out.append(f"line {line}: {len(ws)} Hebrew words not in the WLC ({' '.join(ws[:3])} ...)")
            elif len(long) > 1:
                loose += len(long)
            elif long:
                singles.add(long[0])
        if loose + len(singles) > HEB_TOTAL:
            out.append(f"{loose + len(singles)} Hebrew words in short runs or alone that are not the WLC as written")
        return out

    def kuni_form(self, w):
        if w.isupper() or (len(w) < 4 and w.isascii()):
            return False
        w = w.casefold()
        return w not in self.allow and h([w]) in self.kuni

    def kuni_forms(self, text):
        if self.kuni is None:
            return []
        out, quotes = [], 0
        for n, line in enumerate(text.splitlines(), 1):
            hits = [w for w in WORD.findall(line) if self.kuni_form(w)]
            if not hits:
                continue
            if REF.search(line) and KUNI_CREDIT.search(line) and len(hits) <= MAX_QUOTE:
                quotes += 1
                if quotes <= MAX_QUOTES:
                    continue
                out.append(f"line {n}: more than {MAX_QUOTES} credited Kuni quotations in one file")
                continue
            out.append(f"line {n}: Kuni word forms: {', '.join(hits[:6])}{' ...' if len(hits) > 6 else ''}")
        return out

    def tbta_text(self, text):
        out = []
        for n, line in enumerate(text.splitlines(), 1):
            if TBTA_CODE.search(line):
                out.append(f"line {n}: TBTA analysis codes")
        if self.tbta is not None:
            ws = [w.casefold() for w in WORD.findall(text)]
            for i in range(len(ws) - TBTA_N + 1):
                if h(ws[i:i + TBTA_N]) in self.tbta:
                    out.append(f"{TBTA_N} words of TBTA's verse text: \"{' '.join(ws[i:i + TBTA_N])}\"")
                    break
        return out


def git(*args):
    return subprocess.run(["git", "-C", ROOT, *args], check=True, capture_output=True).stdout


def main():
    args = sys.argv[1:]
    if not args or args == ["--staged"]:
        names = [p for p in git("diff", "--cached", "--name-only", "--diff-filter=ACMR", "-z").decode().split("\0") if p]
        # a submodule (mode 160000) is a commit pointer, not a file: named, not screened (its files are not ours)
        subs = {l.split("\t", 1)[1] for l in git("ls-files", "-s", "-z").decode().split("\0") if l.startswith("160000 ")}
        for p in names:
            if p in subs:
                print(f"submodule {p}: a commit pointer, not screened")
        files = [(p, git("show", f":{p}")) for p in names if p not in subs]
    elif args == ["--all"]:
        names = [p for p in git("ls-files", "--cached", "--others", "--exclude-standard", "-z").decode().split("\0")
                 if p and os.path.isfile(os.path.join(ROOT, p))]
        files = [(p, open(os.path.join(ROOT, p), "rb").read()) for p in names]
    else:
        files = [(p, open(p, "rb").read()) for p in args]
    s = Screen()
    for n in s.notes:
        print("screen: " + n, file=sys.stderr)
    bad = 0
    for p, data in files:
        problems = s.check(p, data)
        if problems:
            bad += 1
            print(f"REFUSED {p}")
            for x in problems[:10]:
                print("    " + x)
            if len(problems) > 10:
                print(f"    ... {len(problems) - 10} more")
    print(f"screen: {len(files)} files, {bad} refused")
    sys.exit(1 if bad else 0)


if __name__ == "__main__":
    main()
