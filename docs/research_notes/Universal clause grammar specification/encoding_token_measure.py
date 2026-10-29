import tiktoken, json, sys
encs = {n: tiktoken.get_encoding(n) for n in ["o200k_base", "cl100k_base"]}
def count(s):
    return {n: len(e.encode(s)) for n, e in encs.items()}
def show(label, s):
    c = count(s); b = len(s.encode("utf-8"))
    print(f"{label:34s} bytes={b:5d} o200k={c['o200k_base']:4d} cl100k={c['cl100k_base']:4d}  bytes/tok(o200k)={b/c['o200k_base']:.2f}")
print("== Clause frame, 8 slots, one clause ==")
frame = dict(id="GEN24:8b", type="cond", rel="prot", act="cmd", pol="NEG", tam="FUT", subj="2s", obj="3p", disc="then")
show("JSON pretty", json.dumps(frame, indent=2))
show("JSON compact", json.dumps(frame, separators=(",", ":")))
show("YAML", "\n".join(f"{k}: {v}" for k, v in frame.items()))
show("TOML", "[clause]\n" + "\n".join(f'{k} = "{v}"' for k, v in frame.items()))
show("TSV row (no header)", "\t".join(frame.values()))
show("CSV row (no header)", ",".join(frame.values()))
show("TSV header line", "\t".join(frame.keys()))
show("Markdown table row", "| " + " | ".join(frame.values()) + " |")
show("Markdown header+sep", "| " + " | ".join(frame.keys()) + " |\n|" + "---|" * len(frame))
show("key=val line", " ".join(f"{k}={v}" for k, v in frame.items()))
show("positional line", "GEN24:8b cond/prot cmd NEG FUT 2s>3p then")
show("Penn bracket", "(COND:prot (ACT cmd) (POL NEG) (TAM FUT) (S 2s) (O 3p) (DISC then))")
show("TOON-ish header", "clauses[1]{id,type,rel,act,pol,tam,subj,obj,disc}:")
show("TOON-ish row", "  GEN24:8b,cond,prot,cmd,NEG,FUT,2s,3p,then")
print("\n== Ten clauses, same frame (per-clause marginal cost) ==")
rows = [dict(frame, id=f"GEN24:{i}a") for i in range(1, 11)]
show("JSON pretty x10", json.dumps(rows, indent=2))
show("JSON compact x10", json.dumps(rows, separators=(",", ":")))
show("YAML list x10", "\n".join("- " + "\n  ".join(f"{k}: {v}" for k, v in r.items()) for r in rows))
show("TSV header+10 rows", "\t".join(frame.keys()) + "\n" + "\n".join("\t".join(r.values()) for r in rows))
show("CSV header+10 rows", ",".join(frame.keys()) + "\n" + "\n".join(",".join(r.values()) for r in rows))
show("MD table header+10 rows", "| " + " | ".join(frame.keys()) + " |\n|" + "---|" * len(frame) + "\n" + "\n".join("| " + " | ".join(r.values()) + " |" for r in rows))
show("key=val x10 lines", "\n".join(" ".join(f"{k}={v}" for k, v in r.items()) for r in rows))
show("positional x10 lines", "\n".join(f"GEN24:{i}a cond/prot cmd NEG FUT 2s>3p then" for i in range(1, 11)))
print("\n== Interlinear line layouts (one 5-word clause) ==")
src = "וְאִם־לֹא תֹאבֶה הָאִשָּׁה לָלֶכֶת אַחֲרֶיךָ"
glo = "and=if-NEG be.willing.IPFV.3FS DEF=woman to=go.INF after=2MS"
tgt = "ka wele ka+ dza +ne nqo+ ta +q"
stacked = src + "\n" + glo + "\n" + tgt
show("Hebrew line alone", src)
show("gloss line alone (Leipzig)", glo)
show("target parts line", tgt)
show("stacked 3 lines", stacked)
inline = "וְאִם־לֹא/and=if-NEG תֹאבֶה/be.willing.IPFV.3FS הָאִשָּׁה/DEF=woman לָלֶכֶת/to=go.INF אַחֲרֶיךָ/after=2MS"
show("inline word/gloss", inline)
translit = "wə-ʾim-lō tōḇe hā-ʾiššā lāleḵeṯ ʾaḥăreḵā"
show("transliteration line", translit)
show("gloss-only (no Hebrew)", "and=if-NEG be.willing.IPFV.3FS DEF=woman to=go.INF after=2MS")
print("\n== Code pieces: how the tokenizer splits them ==")
for s in ["ku+", "+a", "ku+ lam +a", "~PROH", "~H1", "1SG.PST", "NEG.SBJV", "3FS", "IPFV", "FUT.2s.cond.neg", "V.NEG", "SC3s", "pred=ti-", "got=ta-", "src=agent:r2", "first person singular past", "negative subjunctive", "GEN24:8b", "gen024:8b", "GEN 24:8b"]:
    e = encs["o200k_base"]; toks = [e.decode([t]) for t in e.encode(s)]
    e2 = encs["cl100k_base"]; toks2 = [e2.decode([t]) for t in e2.encode(s)]
    print(f"{s!r:30s} o200k={len(toks)} {toks}   cl100k={len(toks2)} {toks2}")
print("\n== Difference-log line ==")
log = "GEN24:8b V.NEG pred=ti- got=ta- why=SC3s src=agent:r2 feat=FUT.2s.cond.neg"
show("log line (given)", log)
show("log line TSV", "GEN24:8b\tV.NEG\tti-\tta-\tSC3s\tagent:r2\tFUT.2s.cond.neg")
show("log line JSON", json.dumps(dict(ref="GEN24:8b", slot="V.NEG", pred="ti-", got="ta-", why="SC3s", src="agent:r2", feat="FUT.2s.cond.neg"), separators=(",", ":")))
print("\n== Hebrew / Greek script cost (bytes per token) ==")
heb = open("/home/lgunnars/dev/make-tanakh-work/orig/heb/gen001.txt", encoding="utf-8").read()
grc = open("/home/lgunnars/dev/make-tanakh-work/orig/grc/jhn001.txt", encoding="utf-8").read()
import re, unicodedata
heb_lines = [l.split("\t", 1)[-1] if "\t" in l else l for l in heb.splitlines()[1:]]
heb_text = " ".join(l.split(" ", 1)[1] for l in heb_lines if " " in l)
grc_text = " ".join(l.split(" ", 1)[1] for l in grc.splitlines()[1:] if " " in l)
def strip_marks(s): return "".join(ch for ch in unicodedata.normalize("NFD", s) if unicodedata.category(ch) != "Mn")
for label, s in [("Hebrew Gen 1 pointed+accents", heb_text), ("Hebrew Gen 1 consonantal", strip_marks(heb_text)), ("Greek John 1 accented", grc_text), ("Greek John 1 unaccented", strip_marks(grc_text))]:
    c = count(s); w = len(s.split())
    print(f"{label:30s} words={w:5d} bytes={len(s.encode()):6d} o200k={c['o200k_base']:6d} ({c['o200k_base']/w:.2f} tok/word) cl100k={c['cl100k_base']:6d} ({c['cl100k_base']/w:.2f} tok/word)")
eng = "In the beginning God created the heavens and the earth. Now the earth was formless and void, and darkness was over the surface of the deep. And the Spirit of God was hovering over the surface of the waters."
c = count(eng); print(f"{'English BSB Gen 1:1-2':30s} words={len(eng.split()):5d} bytes={len(eng.encode()):6d} o200k={c['o200k_base']:6d} ({c['o200k_base']/len(eng.split()):.2f} tok/word)")
print("\n== Real Kuni pack ==")
for p in ["/home/lgunnars/dev/make-tanakh-work/export/kvg/kvg_BSB/_learn/packs/gen001.md", "/home/lgunnars/dev/make-tanakh-work/export/kvg/kvg_BSB/_learn/packs/gen046.pkg.md"]:
    try:
        s = open(p, encoding="utf-8").read(); c = count(s)
        print(f"{p.split('/')[-1]:20s} bytes={len(s.encode()):7d} o200k={c['o200k_base']:6d} cl100k={c['cl100k_base']:6d} bytes/tok={len(s.encode())/c['o200k_base']:.2f}")
    except Exception as ex: print(p, ex)
