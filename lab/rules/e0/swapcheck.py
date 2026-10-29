import os
"""E0: lexeme-aligner's eng_BSB+manual+bsb-tables layer (orig/grc.sqlite bsb) against the raw BSB tables (bcv-query's copy of
bsb_tables.tsv), NT. Per verse: raw rows in Greek order, matched to MACULA tokens by surface form in order; the raw English
chunk's word positions (tokenizer v2 over the chunks in BSB order) against the layer's positions."""
import collections, csv, difflib, json, re, sqlite3, sys, unicodedata
R = os.environ["MAKE_TANAKH_WORK"]; sys.path.insert(0, R + "/scripts")
from full_align import tokenize
csv.field_size_limit(10**9)
names = {l.split("\t")[1]: l.split("\t")[0].upper() for l in open(R + "/books.tsv", encoding="utf-8").read().splitlines()[1:]}
names.update({"Psalm": "PSA", "Song of Solomon": "SNG"})
def norm(w):
    return "".join(c for c in unicodedata.normalize("NFD", w.lower()) if not unicodedata.combining(c) and c.isalpha())
verses = collections.defaultdict(list); vid = None
for row in csv.reader(open("/home/lgunnars/dev/bcv-commons/bcv-query/example/bsb_tables.tsv", encoding="utf-8"), delimiter="\t"):
    if row[0] == "Heb Sort":
        continue
    if row[12].strip():
        vid = row[12].strip()
    if row[4] != "Greek" or not row[5].strip():
        continue
    verses[vid].append((int(row[1]), int(row[2]), row[5].strip(), row[11].strip(), row[18]))
g = sqlite3.connect(R + "/orig/grc.sqlite")
_bc = {}
def bsb_verse(code, ch, v):
    if (code, ch) not in _bc:
        t = open(R + f"/reference/BSB/{code.lower()}{ch:03d}.txt", encoding="utf-8").read()
        t = re.sub(r"(?m)^==.*$", "", t); t = re.sub(r"\{[^}]*\}", "", t)
        _bc[(code, ch)] = {int(m[1]): m[2] for m in re.finditer(r"\bv(\d+)\s+(.*?)(?=\bv\d+\s|\Z)", t, re.S)}
    return _bc[(code, ch)][v]
cls = collections.Counter(); exk = collections.defaultdict(list); vok = collections.Counter(); st = collections.Counter(); bad = collections.Counter(); ex = []
for vid, rows in verses.items():
    m = re.match(r"(.+) (\d+):(\d+)$", vid)
    code = names.get(m[1])
    if not code:
        st["book?"] += 1; continue
    ch, v = int(m[2]), int(m[3])
    toks = g.execute("select t.key, t.text, t.strong, b.positions from tokens t left join bsb b on b.key = t.key where book=? and ch=? and v=? order by t.key", (code, ch, v)).fetchall()
    if not toks:
        st["verse not in MACULA"] += 1; continue
    # English positions from the raw chunks, BSB order
    pos, k = {}, 0
    for gs, bs, w, s, en in sorted(rows, key=lambda r: r[1]):
        n = len(tokenize(en.replace("vvv", "")))
        pos[gs] = list(range(k, k + n)); k += n
    raw = sorted(rows)
    try:
        bsbv = bsb_verse(code, ch, v)
        recon = [w for _, _, _, _, en in sorted(rows, key=lambda r: r[1]) for w in tokenize(en.replace("vvv", ""))]
        same = [w.lower() for w in tokenize(bsbv)] == [w.lower() for w in recon]
        vok["verse words equal" if same else "verse words differ"] += 1
        if not same: continue
    except Exception as e:
        vok["verse unread"] += 1; continue
    sm = difflib.SequenceMatcher(None, [norm(r[2]) for r in raw], [norm(t[1]) for t in toks], autojunk=False)
    strongs = collections.Counter(r[3] for r in raw)
    for a, b, n in sm.get_matching_blocks():
        for i in range(n):
            r, t = raw[a + i], toks[b + i]
            layer = [int(x) for x in (t[3] or "").split()]
            gold = pos[r[0]]
            rep = strongs[r[3]] > 1
            st["tokens"] += 1; st["rep tokens"] += rep
            if layer == gold or (not layer and not gold):
                st["same"] += 1
            else:
                st["differ"] += 1; bad["repeated strong" if rep else "unique strong"] += 1
                others = [pos[q[0]] for q in raw if q[3] == r[3] and q is not r]
                en = r[4]
                if layer and layer in others: kind = "swapped with a same-Strong's token"
                elif not layer: kind = "layer has no link"
                elif not gold: kind = "layer links a word the table gives none"
                elif set(layer) < set(gold): kind = "layer drops words" + (" (bracketed)" if "[" in en else "")
                elif set(layer) > set(gold): kind = "layer adds words"
                else: kind = "other"
                cls[kind] += 1
                if len(exk[kind]) < 3: exk[kind].append((vid, r[2], en.strip(), gold, layer))
                if rep and len(ex) < 8:
                    ex.append((vid, r[2], r[4].strip(), "gold", gold, "layer", layer))
    st["unmatched raw"] += len(raw) - sum(n for _, _, n in sm.get_matching_blocks())
print(dict(st)); print(dict(bad)); print(dict(vok)); print(dict(cls))
for k, e in exk.items(): print(k, e)
print("differ rate, repeated Strong's:", round(bad["repeated strong"] / max(1, st["rep tokens"]), 4),
      " unique:", round(bad["unique strong"] / max(1, st["tokens"] - st["rep tokens"]), 4))
for e in ex: print(e)
json.dump({"stats": st, "bad": bad, "examples": ex}, open(R + "/scratch/rules/e0/swapcheck.json", "w"), ensure_ascii=False, indent=1, default=str)
