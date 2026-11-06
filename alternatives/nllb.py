#!/usr/bin/env python3
"""The NLLB alternative: a second draft of the same chapters by a small translation model fine-tuned on the team's text.

It is shown to reviewers beside the main draft and feeds the support marks (alternatives/support.py); it is not the main
draft. A language's configuration names its models, one per source language:

    "nllb": {"grc": {"model": "$PRIVATE/models/nllb/<name>", "src_code": "ell_Grek", "trg_code": "xxx_Latn"},
             "hbo": {"model": "$PRIVATE/models/nllb/<name>", "src_code": "heb_Hebr", "trg_code": "xxx_Latn"}}

<model>/model/ holds the fine-tuned model (alternatives/nllb_train.py writes it); it is converted once to CTranslate2 int8
under <model>/ct2-int8/ and runs on the CPU. The model reads a whole source verse (Greek: the verse as written; Hebrew:
consonants only, maqaf as a space) and writes the verse as the team's parts ("ni@@ ba@@ ku@@ ..."). Per verse: the beam output
and --k samples; the consensus is the output closest to all the others (highest summed sentence chrF); the consensus verse is
cut to the clauses by each clause's share of the verse's source words.

    . ./env.sh
    python3 alternatives/nllb.py draft --lang zin --book JHN --chapters 1-4        # samples, consensus, clauses
    python3 drafting/draft.py text --lang zin --book JHN --label nllb              # the verses of each chapter

The run lives beside the main draft: runs/<lang>/draft/<book>/<label>/ (label: nllb), with samples.json and answers/ in the
main draft's form. Closed and held-out chapters are refused. NLLB's licence is CC BY-NC 4.0: see the README on what that
means for the model and for its drafts.

Needs: ctranslate2, transformers, sacrebleu (requirements-nllb.txt)."""
import argparse, collections, json, os, re, sys, time, unicodedata

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from shared import paths  # noqa: E402
from source import tokens  # noqa: E402
from drafting import draft, evidence, prompt  # noqa: E402

JOIN = "@@ "
MAX_LEN, MAX_OUT = 200, 256


def consonants(t):
    """a Hebrew verse as the models read it: consonants only, maqaf as a space, no punctuation"""
    t = "".join(c for c in unicodedata.normalize("NFD", t) if not unicodedata.combining(c))
    return " ".join(re.sub(r"[^א-ת ]", " ", unicodedata.normalize("NFC", t).replace("־", " ")).split())


def hebrew_verses(refs):
    """ref -> the verse's words with what follows each, unspaced where the text is (the form consonants() expects)"""
    out = collections.defaultdict(str); books = sorted({r.split()[0] for r in refs}); q = ",".join("?" * len(books))
    for b, ch, v, t, a in tokens._db("hbo").execute(f"select book, ch, v, text, coalesce(after, '') from tokens where book in ({q}) order by key", tuple(books)):
        r = f"{b} {ch}:{v}"
        if r in refs:
            out[r] += t + a
    return out


def source_lines(source, refs):
    """ref -> the line the model reads"""
    if source == "grc":
        return tokens.verse_texts("grc", set(refs))
    return {r: consonants(t) for r, t in hebrew_verses(set(refs)).items()}


def model_of(cfg, source):
    m = (cfg.get("nllb") or {}).get(source)
    if not m:
        sys.exit(f"{cfg['iso']}: the configuration names no NLLB model for source '{source}' (\"nllb\": {{\"{source}\": ...}})")
    d = paths.resolve(cfg["iso"], m["model"])
    if not os.path.exists(os.path.join(d, "model", "tokenizer.json")):
        sys.exit(f"no model under {d}/model")
    return d, m


def translator(mdir, src_code, threads):
    import ctranslate2
    from transformers import AutoTokenizer
    cdir = os.path.join(mdir, "ct2-int8")
    if not os.path.exists(os.path.join(cdir, "model.bin")):
        t = time.time(); ctranslate2.converters.TransformersConverter(os.path.join(mdir, "model")).convert(cdir, quantization="int8", force=True)
        print(f"converted the model to CTranslate2 int8 in {time.time() - t:.0f}s -> {cdir}", flush=True)
    tok = AutoTokenizer.from_pretrained(os.path.join(mdir, "model"), src_lang=src_code)
    return ctranslate2.Translator(cdir, device="cpu", inter_threads=1, intra_threads=threads, compute_type="int8"), tok


def sample(cfg, source, lines, k, threads, batch, seed, done=None, save=None):
    """{ref: [{"rank", "kind", "raw"}]}: rank 1 the beam output (beam 2), then k samples (top-k 50, top-p 0.9)"""
    import ctranslate2
    mdir, m = model_of(cfg, source); tr, tok = translator(mdir, m["src_code"], threads)
    dec = lambda toks: tok.decode(tok.convert_tokens_to_ids(toks), skip_special_tokens=True)
    out = dict(done or {}); refs = [r for r in lines if r not in out]; ctranslate2.set_random_seed(seed); t0 = time.time()
    for i in range(0, len(refs), batch):
        rs = refs[i:i + batch]
        S = [tok.convert_ids_to_tokens(tok(lines[r], truncation=True, max_length=MAX_LEN).input_ids) for r in rs]
        P = [[m["trg_code"]]] * len(S)
        beam = tr.translate_batch(S, target_prefix=P, beam_size=2, max_decoding_length=MAX_OUT)
        samp = tr.translate_batch(S, target_prefix=P, beam_size=1, num_hypotheses=k, sampling_topk=50, sampling_topp=0.9,
                                  sampling_temperature=1.0, max_decoding_length=MAX_OUT) if k else [None] * len(S)
        for j, r in enumerate(rs):
            out[r] = [{"rank": 1, "kind": "beam", "raw": dec(beam[j].hypotheses[0][1:])}]
            if k:
                out[r] += [{"rank": n + 2, "kind": "sample", "raw": dec(h[1:])} for n, h in enumerate(samp[j].hypotheses)]
        if save:
            save(out)
        print(f"{min(i + batch, len(refs))}/{len(refs)} verses {time.time() - t0:.0f}s", flush=True)
    return out


def consensus(entries):
    """the output with the highest summed sentence chrF against the others (minimum Bayes risk over the model's own outputs)"""
    import sacrebleu
    ch = sacrebleu.CHRF(word_order=0); raws = [x["raw"] for x in entries]
    if len(raws) == 1:
        return raws[0]
    return max(raws, key=lambda h: sum(ch.sentence_score(h, [o]).score for o in raws if o is not h))


def words_of(raw):
    """a parts string 'a@@ b@@ c d.' -> the words ['abc', 'd.'] (case and punctuation as the model wrote them)"""
    return [w.replace("\x01", "") for w in raw.replace(JOIN, "\x01").replace("@@", "\x01").split()]


def cut(q, cons, keys):
    """a clause's text: per verse of the clause, the stretch of the consensus verse that matches the clause's share of the verse's
    source words (keys: ref -> the verse's source token keys in order)"""
    ws = []
    for ref in sorted({t["sref"] for t in q["tokens"]}, key=prompt.ref_key):
        ks = keys.get(ref, []); pos = [ks.index(t["key"]) for t in q["tokens"] if t["sref"] == ref and t["key"] in ks]
        if ref not in cons or not pos:
            continue
        vw = cons[ref]; m, n = len(vw), len(ks)
        ws += vw[round(m * min(pos) / n): round(m * (max(pos) + 1) / n)]
    return " ".join(ws)


def verse_keys(source, book):
    """ref -> the verse's source keys in text order, as the query clauses name them (Greek: tokens; Hebrew: words)"""
    out = collections.defaultdict(list)
    for k, ch, v in tokens._db(source).execute("select key, ch, v from tokens where book = ? order by key", (book,)):
        k = k if source == "grc" else k[:11]; r = f"{book} {ch}:{v}"
        if not out[r] or out[r][-1] != k:
            out[r].append(k)
    return out


def cmd_draft(a):
    cfg = paths.config(a.lang); src = a.source or draft.source_of(a.book); chs = draft.chapters_arg(a.chapters)
    leave = tuple(x for x in (a.leave_out or "").split(",") if x)
    E = evidence.build(cfg, src, a.book, chs, leave)                 # the same clauses as the main draft; refuses shut chapters
    groups = collections.OrderedDict()
    for qid in E.order:
        q = E.queries[qid]; groups.setdefault(sorted(q["refs"], key=prompt.ref_key)[0], []).append(q)
    refs = sorted({t["sref"] for qid in E.order for t in E.queries[qid]["tokens"]}, key=prompt.ref_key)
    lines = source_lines(src, refs); sp = os.path.join(draft.job_dir(a), "samples.json")
    done = json.load(open(sp, encoding="utf-8")) if os.path.exists(sp) else {}
    save = lambda o: json.dump(o, open(sp, "w", encoding="utf-8"), ensure_ascii=False, indent=0)
    S = sample(cfg, src, {r: lines[r] for r in refs if lines.get(r)}, a.k, a.threads, a.batch, a.seed, done, save)
    cons = {r: words_of(consensus(S[r])) for r in refs if r in S}; keys = verse_keys(src, a.book)
    od = draft.job_dir(a, "answers"); g = {}; empty = 0
    for v, cl in groups.items():
        texts = [cut(q, cons, keys) for q in cl]; empty += sum(not t for t in texts)
        json.dump({"clauses": [{"c": i, "text": t} for i, t in enumerate(texts, 1)]}, open(os.path.join(od, draft.vid(v) + ".json"), "w", encoding="utf-8"),
                  ensure_ascii=False)
        g[draft.vid(v)] = {"refs": sorted({r for q in cl for r in q["refs"]}, key=prompt.ref_key), "clauses": [q["id"] for q in cl]}
    draft.save_groups(a, g); m = draft.load_manifest(a); mdir, mm = model_of(cfg, src)
    m["builds"].append({"when": time.strftime("%Y-%m-%d %H:%M"), "code": draft.commit(), "kind": "nllb", "source": src, "chapters": chs, "verses": len(groups),
                        "clauses": len(E.order), "clauses without text": empty, "model": os.path.basename(mdir), "codes": [mm["src_code"], mm["trg_code"]],
                        "samples": a.k, "seed": a.seed})
    draft.save_manifest(a, m)
    print(f"{a.lang} {a.book} {chs}: {len(groups)} verses, {len(E.order)} clauses ({empty} without text) -> {od}")


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("cmd", choices=("draft",)); ap.add_argument("--lang", required=True); ap.add_argument("--book", required=True)
    ap.add_argument("--chapters", required=True); ap.add_argument("--label", default="nllb"); ap.add_argument("--source", choices=paths.SOURCES)
    ap.add_argument("--leave-out"); ap.add_argument("--k", type=int, default=32); ap.add_argument("--threads", type=int, default=4)
    ap.add_argument("--batch", type=int, default=8); ap.add_argument("--seed", type=int, default=1)
    a = ap.parse_args(); a.book = a.book.upper(); cmd_draft(a)


if __name__ == "__main__":
    main()
